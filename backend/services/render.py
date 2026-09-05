"""Resume → HTML → PDF.

    Resume (Pydantic, every field already factual)
       | Jinja2, autoescaped
       v
    {id}.html   <- served by GET /resumes/{id}/preview
       | WeasyPrint
       v
    {id}.pdf    <- /data/resumes/, the DB stores this path and its sha256

Both files are written. The HTML is kept rather than re-rendered on demand because the
`resumes` row stores no resume JSON — there would be nothing to re-render *from* — and
keeping the exact bytes WeasyPrint consumed is what makes "preview and download cannot
drift" true by construction instead of by convention.

This module owns the filename convention, so nothing else has to know it.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import weasyprint
from jinja2 import Environment, FileSystemLoader

from core.config import settings
from schemas.resume import Resume

TEMPLATE_VERSION = "resume.v1"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class Density:
    """One rung of the typographic ladder `render` walks to reach a single page."""

    font: float
    small: float
    line_height: float
    section_gap: float
    entry_gap: float


# Loosest first. The last rung is the floor: below roughly 9pt a resume stops being
# comfortable to read, and a second page is a better outcome than type nobody wants to
# look at. Content is never dropped to make it fit — the selection budget in
# `tailoring.assemble` is what does the actual shortening, and in practice a budgeted
# resume fits at the first rung.
DENSITIES = (
    Density(font=10.5, small=9.5, line_height=1.4, section_gap=12, entry_gap=9),
    Density(font=10, small=9, line_height=1.32, section_gap=10, entry_gap=7),
    Density(font=9.5, small=8.5, line_height=1.26, section_gap=8, entry_gap=5.5),
    Density(font=9, small=8, line_height=1.2, section_gap=6.5, entry_gap=4),
)


@dataclass(frozen=True)
class Rendered:
    pdf_path: Path
    html_path: Path
    # sha256 of the PDF bytes that were actually written.
    content_hash: str
    pages: int


def _month_year(value: date | None, empty: str = "") -> str:
    return value.strftime("%b %Y") if value else empty


def _date_range(start: date | None, end: date | None) -> str:
    """A displayable range, tolerating either end being absent.

    Education rows may carry an end date with no start; rendering that as " - May 2019"
    reads as a bug, so the leading separator is dropped rather than left dangling.

    A plain hyphen rather than an en dash: resume date parsers are written against
    "Jan 2021 - Jun 2024", and "–" is one more character for them to get wrong.
    """
    if not start and not end:
        return ""
    if not start:
        return _month_year(end)
    return f"{_month_year(start)} - {_month_year(end, 'Present')}"


def _bare_url(url: str) -> str:
    """A URL as a human writes it on a resume: no scheme, no trailing slash.

    The visible text is what a PDF text extractor gets — the href is invisible to it — so
    this string is the only form of the address that reaches an ATS.
    """
    trimmed = url.strip().removeprefix("https://").removeprefix("http://")
    return trimmed.removeprefix("www.").rstrip("/")


def _environment() -> Environment:
    # autoescape=True explicitly. `select_autoescape` keys off the file extension and
    # this template ends in .j2, so it would default to *off* — and a profile containing
    # "R&D" or "<script>" would then produce broken or dangerous markup.
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    env.globals["date_range"] = _date_range
    env.globals["bare_url"] = _bare_url
    return env


def render_html(resume: Resume, density: Density = DENSITIES[0]) -> str:
    template = _environment().get_template(f"{TEMPLATE_VERSION}.html.j2")
    return template.render(resume=resume, density=density)


def html_path(resume_id: uuid.UUID) -> Path:
    return settings.resume_dir / f"{resume_id}.html"


def pdf_path(resume_id: uuid.UUID) -> Path:
    return settings.resume_dir / f"{resume_id}.pdf"


def fit(resume: Resume) -> tuple[str, "weasyprint.Document"]:
    """The loosest density that comes to one page, and the document it produced.

    Laying the resume out is the only way to know how long it is — line wrapping and
    widow control mean you cannot count it from the data — so this simply lays it out at
    each rung and stops at the first that fits.

    Returns the *document*, not just the density, so the caller writes the PDF for the
    exact layout that was measured. Re-rendering to produce the bytes would open a gap
    between what was checked and what was written.

    If nothing fits, the last rung is returned and the resume runs to two pages. That is
    deliberate: silently deleting a bullet the user wrote is a worse failure than a
    second page.
    """
    html = ""
    document = None
    for density in DENSITIES:
        html = render_html(resume, density)
        document = weasyprint.HTML(string=html).render()
        if len(document.pages) == 1:
            break
    assert document is not None  # DENSITIES is never empty
    return html, document


def render(resume: Resume, resume_id: uuid.UUID) -> Rendered:
    """Write both files and return their paths plus the PDF's hash.

    The id is passed in rather than generated here so the filenames and the `resumes`
    row's primary key are the same value by construction.

    The HTML written is the one that produced this exact PDF, at whichever density `fit`
    settled on — which is what keeps "preview and download cannot drift" true across the
    fit loop rather than only when there is one layout.

    The hash is taken over the bytes written, never over a re-render. WeasyPrint output
    is *not* reliably byte-stable: there is no /CreationDate in it, but the embedded
    font subset varies with wall-clock time, so two renders of identical HTML a second
    apart differ. Verifying a stored resume by re-rendering and comparing hashes would
    therefore report intact files as corrupt.
    """
    settings.resume_dir.mkdir(parents=True, exist_ok=True)

    html, document = fit(resume)
    target_html = html_path(resume_id)
    target_html.write_text(html, encoding="utf-8")

    # pdf/ua-1 emits a tagged PDF: a real structure tree plus /Marked true, so an
    # extractor reads headings as headings and list items as list items instead of
    # inferring structure from coordinates. Verified against WeasyPrint 69 — the tags
    # live inside compressed object streams, so grepping the default output for
    # "StructTreeRoot" finds nothing and proves nothing.
    pdf_bytes = document.write_pdf(pdf_variant="pdf/ua-1")
    target_pdf = pdf_path(resume_id)
    target_pdf.write_bytes(pdf_bytes)

    return Rendered(
        pdf_path=target_pdf,
        html_path=target_html,
        content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
        pages=len(document.pages),
    )


def remove_files(resume_id: uuid.UUID) -> None:
    """Best effort: a missing file is the desired end state, not an error."""
    html_path(resume_id).unlink(missing_ok=True)
    pdf_path(resume_id).unlink(missing_ok=True)
