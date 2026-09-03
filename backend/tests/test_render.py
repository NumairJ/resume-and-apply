"""Rendering a resume to HTML and PDF.

These run against real WeasyPrint and real Jinja2 — there is nothing worth mocking here,
and a mocked renderer would prove only that the mock was called.
"""

import hashlib
import uuid
from pathlib import Path

from schemas.resume import Resume, ResumeEducation, ResumeExperience
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
    assert "Mar 2021 – Jun 2024" in html
    assert "State University" in html
    assert "Migrated the billing database to Postgres with zero downtime" in html


def test_an_open_ended_role_reads_as_present() -> None:
    resume = a_resume()
    resume.experiences[0].end_date = None
    assert "Mar 2021 – Present" in render.render_html(resume)


def test_a_date_range_missing_its_start_has_no_dangling_separator() -> None:
    """Education start dates are nullable; " – May 2019" would read as a bug."""
    resume = a_resume()
    resume.education = [
        ResumeEducation(school="State University", degree="BSc", end_date=None)
    ]
    assert "–" not in render.render_html(resume).split("Education")[1]


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
