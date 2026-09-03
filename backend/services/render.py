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
class Rendered:
    pdf_path: Path
    html_path: Path
    # sha256 of the PDF bytes that were actually written.
    content_hash: str


def _month_year(value: date | None, empty: str = "") -> str:
    return value.strftime("%b %Y") if value else empty


def _date_range(start: date | None, end: date | None) -> str:
    """A displayable range, tolerating either end being absent.

    Education rows may carry an end date with no start; rendering that as " – May 2019"
    reads as a bug, so the leading separator is dropped rather than left dangling.
    """
    if not start and not end:
        return ""
    if not start:
        return _month_year(end)
    return f"{_month_year(start)} – {_month_year(end, 'Present')}"


def _environment() -> Environment:
    # autoescape=True explicitly. `select_autoescape` keys off the file extension and
    # this template ends in .j2, so it would default to *off* — and a profile containing
    # "R&D" or "<script>" would then produce broken or dangerous markup.
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    env.globals["date_range"] = _date_range
    return env


def render_html(resume: Resume) -> str:
    template = _environment().get_template(f"{TEMPLATE_VERSION}.html.j2")
    return template.render(resume=resume)


def html_path(resume_id: uuid.UUID) -> Path:
    return settings.resume_dir / f"{resume_id}.html"


def pdf_path(resume_id: uuid.UUID) -> Path:
    return settings.resume_dir / f"{resume_id}.pdf"


def render(resume: Resume, resume_id: uuid.UUID) -> Rendered:
    """Write both files and return their paths plus the PDF's hash.

    The id is passed in rather than generated here so the filenames and the `resumes`
    row's primary key are the same value by construction.

    The hash is taken over the bytes written, never over a re-render. WeasyPrint output
    is *not* reliably byte-stable: there is no /CreationDate in it, but the embedded
    font subset varies with wall-clock time, so two renders of identical HTML a second
    apart differ. Verifying a stored resume by re-rendering and comparing hashes would
    therefore report intact files as corrupt.
    """
    settings.resume_dir.mkdir(parents=True, exist_ok=True)

    html = render_html(resume)
    target_html = html_path(resume_id)
    target_html.write_text(html, encoding="utf-8")

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    target_pdf = pdf_path(resume_id)
    target_pdf.write_bytes(pdf_bytes)

    return Rendered(
        pdf_path=target_pdf,
        html_path=target_html,
        content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
    )


def remove_files(resume_id: uuid.UUID) -> None:
    """Best effort: a missing file is the desired end state, not an error."""
    html_path(resume_id).unlink(missing_ok=True)
    pdf_path(resume_id).unlink(missing_ok=True)
