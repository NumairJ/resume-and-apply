"""Rendering a resume to HTML and PDF.

These run against real WeasyPrint and real Jinja2 — there is nothing worth mocking here,
and a mocked renderer would prove only that the mock was called.
"""

import hashlib
import uuid
from datetime import date
from pathlib import Path

from schemas.resume import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeProject,
)
from services import render
from services.tailoring import assemble
from tests.factories import sample_profile, valid_resume


def a_resume() -> Resume:
    """The same assembled resume the tailoring suite produces, rendered for real."""
    return assemble(valid_resume(), sample_profile())


# --- HTML -------------------------------------------------------------------


def test_html_carries_the_resume_facts() -> None:
    html = render.render_html(a_resume())

    assert "Dana Reed" in html
    assert "Northwind Systems" in html
    assert "Software Engineer" in html
    assert "Mar 2021 - Jun 2024" in html
    assert "State University" in html
    assert "Migrated the billing database to Postgres with zero downtime" in html


def test_an_open_ended_role_reads_as_present() -> None:
    resume = a_resume()
    resume.experiences[0].end_date = None
    assert "Mar 2021 - Present" in render.render_html(resume)


def test_a_date_range_missing_its_start_has_no_dangling_separator() -> None:
    """Education start dates are nullable; " - May 2019" would read as a bug.

    Asserted on `_date_range` directly. Going through the HTML made this vacuous: the row
    it built had *neither* date, so the range was the empty string and a dangling
    separator could never have appeared however broken the formatter was.
    """
    assert render._date_range(None, date(2019, 5, 1)) == "May 2019"
    assert render._date_range(None, None) == ""


def test_dates_use_a_plain_hyphen() -> None:
    """An en dash is one more character for a resume date parser to get wrong."""
    assert render._date_range(date(2021, 3, 1), date(2024, 6, 1)) == (
        "Mar 2021 - Jun 2024"
    )
    assert "–" not in render.render_html(a_resume())


def test_profile_text_is_escaped() -> None:
    """Autoescaping is set explicitly, and this is why.

    `select_autoescape` keys off the file extension and the template ends in `.j2`, so
    the default would be *off* — and a company legitimately called "Smith & Co" would
    produce invalid markup, while a pasted `<script>` would produce worse.
    """
    resume = a_resume()
    resume.summary = "Worked in R&D on <script>alert(1)</script> tooling"
    resume.experiences = [
        ResumeExperience(
            company="Smith & Co",
            title="Engineer",
            start_date=resume.experiences[0].start_date,
        )
    ]
    html = render.render_html(resume)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "Smith &amp; Co" in html


def test_print_stylesheet_survives() -> None:
    """Losing these rules costs a page and breaks entries across page boundaries,
    neither of which any other assertion here would notice."""
    html = render.render_html(a_resume())
    assert "@page" in html
    assert "break-inside: avoid" in html


# --- projects ---------------------------------------------------------------


def test_projects_reach_the_page() -> None:
    """The gap this whole change exists to close: projects rendered nowhere."""
    html = render.render_html(a_resume())

    assert "<h2>Projects</h2>" in html
    assert "Portfolio Site" in html
    # The model's rewrite, as a bullet.
    assert "<li>Personal site built with Next.js" in html
    # Verbatim from the profile row, never rewritten.
    assert "Next.js, Postgres, Docker" in html


def test_the_project_name_carries_the_link() -> None:
    """Asked for directly, and the reason the address moved to the right-hand slot."""
    html = render.render_html(a_resume())

    assert (
        '<a href="https://dana.example/portfolio">Portfolio Site</a>' in html
    )
    # Still present as *text*, because an extractor reads visible text, never the href.
    assert "dana.example/portfolio" in html


def test_dates_yield_the_right_hand_slot_to_the_address() -> None:
    """Both exist on this fixture. A project is identified by its link far more than by
    when it was built, so the address keeps the slot and the dates move to the meta line.
    """
    html = render.render_html(a_resume())
    projects = html.split("Projects")[1].split("Education")[0]

    assert "dana.example/portfolio</a></span>" not in projects  # not inside the <h3>
    assert '<span class="dates">dana.example/portfolio</span>' in projects
    assert "Apr 2022 - Sep 2022" in projects


def test_a_project_with_nothing_but_a_name_still_renders() -> None:
    """Name alone is the whole record for some projects, and that is a resume entry —
    not a reason to drop it, and not a reason to invent filler."""
    resume = a_resume()
    resume.projects = [ResumeProject(name="Crossword Solver")]
    html = render.render_html(resume)
    projects = html.split("Projects")[1].split("Education")[0]

    assert "Crossword Solver" in projects
    assert "None" not in projects
    assert "<ul>" not in projects


def test_project_text_is_escaped() -> None:
    resume = a_resume()
    resume.projects = [
        ResumeProject(
            name="Smith & Co",
            tech_stack="R&D tooling",
            bullets=["<script>alert(1)</script>"],
        )
    ]
    html = render.render_html(resume)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "Smith &amp; Co" in html
    assert "R&amp;D tooling" in html


# --- ATS legibility ---------------------------------------------------------


def test_a_link_shows_its_address_not_only_its_label() -> None:
    """A text extractor reads visible text, never the href. "GitHub" alone threw the
    address away — the parser saw a word, not a profile."""
    html = render.render_html(a_resume())
    assert "gh/dana" in html


def test_skills_are_comma_separated() -> None:
    """Keyword extractors split on commas; a middle dot is a character to guess at."""
    html = render.render_html(a_resume())
    assert "Python, Postgres" in html


def test_headings_are_not_widely_tracked() -> None:
    """1pt tracking is the classic reason an extractor reads "E X P E R I E N C E"."""
    assert "letter-spacing: 1pt" not in render.render_html(a_resume())


def test_bullet_markers_are_inside_the_line_box() -> None:
    """Found by extracting the PDF's text and reading it.

    With the default `list-style-position: outside`, WeasyPrint puts the bullet glyphs
    outside the line box and an extractor emits them *after* the entire list — the text
    came out as the two bullet lines followed by a bare "• • ". Nothing on screen shows
    this; only reading the extracted text does.
    """
    assert "list-style-position: inside" in render.render_html(a_resume())


def test_no_space_before_the_comma_in_an_education_line() -> None:
    """Also found by extraction: "BSc, Computer Science , State University".

    Jinja turned the newline before the school's span into a real space. Invisible in the
    browser, which collapses it against the comma; not invisible to a parser.
    """
    education = render.render_html(a_resume()).split("Education")[1]
    assert " , " not in education


def test_the_pdf_is_tagged() -> None:
    """pdf/ua-1 gives the PDF a structure tree, so headings extract as headings.

    Checked on an uncompressed render: the default output packs these objects into
    compressed streams, where grepping for the marker finds nothing and proves nothing.
    """
    _, document = render.fit(a_resume())
    pdf = document.write_pdf(pdf_variant="pdf/ua-1", uncompressed_pdf=True)

    assert b"StructTreeRoot" in pdf
    assert b"/Marked" in pdf


# --- fitting to one page ----------------------------------------------------


def test_a_budgeted_resume_fits_one_page_at_full_size() -> None:
    """The selection caps do the shortening; the ladder should not need to be climbed."""
    html, document = render.fit(a_resume())

    assert len(document.pages) == 1
    assert f"font-size: {render.DENSITIES[0].font}pt" in html


def test_an_oversized_resume_is_tightened_rather_than_truncated() -> None:
    """Far more content than the caps would ever allow. Every bullet must survive."""
    resume = a_resume()
    resume.experiences = [
        ResumeExperience(
            company=f"Company {index}",
            title="Software Engineer",
            start_date=date(2015, 1, 1),
            end_date=date(2020, 1, 1),
            bullets=[f"Did a substantial and quite wordy thing number {n}" for n in range(6)],
        )
        for index in range(6)
    ]
    html, document = render.fit(resume)

    assert f"font-size: {render.DENSITIES[0].font}pt" not in html
    for index in range(6):
        assert f"Company {index}" in html


def test_content_is_never_dropped_to_fit() -> None:
    """Past the floor a second page is the right answer. Deleting a bullet the user
    wrote is not, so this pins that nothing is silently lost."""
    resume = a_resume()
    resume.experiences = [
        ResumeExperience(
            company=f"Company {index}",
            title="Software Engineer",
            start_date=date(2015, 1, 1),
            bullets=["A deliberately long bullet " * 12] * 8,
        )
        for index in range(12)
    ]
    html, _ = render.fit(resume)

    for index in range(12):
        assert f"Company {index}" in html


# --- files ------------------------------------------------------------------


def test_writes_both_files_named_by_the_resume_id(resume_dir: Path) -> None:
    resume_id = uuid.uuid4()
    result = render.render(a_resume(), resume_id)

    assert result.pdf_path == resume_dir / f"{resume_id}.pdf"
    assert result.html_path == resume_dir / f"{resume_id}.html"
    assert result.pdf_path.is_file() and result.html_path.is_file()


def test_the_stored_html_is_what_the_pdf_was_made_from() -> None:
    """Preview and download cannot drift, because they come from the same bytes."""
    resume = a_resume()
    result = render.render(resume, uuid.uuid4())
    assert result.html_path.read_text(encoding="utf-8") == render.render_html(resume)


def test_the_stored_html_is_the_density_the_pdf_was_made_at() -> None:
    """The fit loop is where preview and download could most easily drift apart: the
    HTML written must be the rung that was measured, not a fresh render at the default.
    """
    resume = a_resume()
    resume.experiences = [
        ResumeExperience(
            company=f"Company {index}",
            title="Software Engineer",
            start_date=date(2015, 1, 1),
            bullets=[f"Did a substantial and quite wordy thing number {n}" for n in range(6)],
        )
        for index in range(6)
    ]
    result = render.render(resume, uuid.uuid4())
    fitted, _ = render.fit(resume)

    stored = result.html_path.read_text(encoding="utf-8")
    assert stored == fitted
    assert stored != render.render_html(resume)  # i.e. not the default density


def test_the_pdf_is_a_pdf() -> None:
    result = render.render(a_resume(), uuid.uuid4())
    assert result.pdf_path.read_bytes().startswith(b"%PDF-")


def test_hash_matches_the_file_on_disk() -> None:
    result = render.render(a_resume(), uuid.uuid4())
    on_disk = hashlib.sha256(result.pdf_path.read_bytes()).hexdigest()
    assert result.content_hash == on_disk


def test_each_render_hashes_its_own_bytes() -> None:
    """Pins why the hash is taken over the bytes written, not over a re-render.

    WeasyPrint output is not reliably byte-stable — it carries no /CreationDate, but the
    embedded font subset varies with wall-clock time, so two renders of identical HTML a
    second apart differ. Integrity must therefore be checked against the stored bytes;
    re-rendering and comparing would report intact files as corrupt. (Not asserted by
    timing here on purpose: a test that has to straddle a second boundary is a flaky
    test.)
    """
    resume = a_resume()
    for result in (render.render(resume, uuid.uuid4()) for _ in range(2)):
        assert (
            hashlib.sha256(result.pdf_path.read_bytes()).hexdigest()
            == result.content_hash
        )


def test_remove_files_tolerates_missing_files() -> None:
    """A file already gone is the desired end state, not a failure."""
    resume_id = uuid.uuid4()
    render.render(a_resume(), resume_id)

    render.remove_files(resume_id)
    render.remove_files(resume_id)

    assert not render.pdf_path(resume_id).exists()
    assert not render.html_path(resume_id).exists()
