"""Prompt rendering, the retry loop, and assembly."""

import uuid
from datetime import date

import pytest

from models.application import JobPosting
from models.enums import ExtractionMethod
from schemas.resume import (
    TailoredBullet,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
)
from services import tailoring
from services.guardrails import GuardrailFailure
from services.llm.fake import FakeLLMProvider
from tests.factories import broken_resume, valid_resume


@pytest.fixture
def posting() -> JobPosting:
    return JobPosting(
        id=uuid.uuid4(),
        company="Globex",
        title="Senior Backend Engineer",
        location="Remote",
        description="We need payment reliability and Postgres depth.",
        requirements="Five years of backend work.",
        source_url="https://example.com/jobs/1",
        fingerprint="fp",
        extraction_method=ExtractionMethod.LLM,
    )


# --- prompt rendering -------------------------------------------------------


def test_prompt_labels_match_what_the_guardrails_resolve(profile) -> None:
    """The single most important invariant in this phase.

    If the labels shown to the model ever diverged from the labels the checks resolve,
    every generation would be rejected as fabricated.
    """
    rendered = tailoring.render_profile(profile)

    assert "[E1]" in rendered and "[E1B1]" in rendered and "[E1B2]" in rendered
    assert "[E2]" in rendered and "[E2B1]" in rendered
    # No E3: the profile has two experiences.
    assert "[E3]" not in rendered

    assert "[P1]" in rendered and "[P2]" in rendered
    assert "[P3]" not in rendered


def test_projects_are_labelled_and_carry_their_description(profile) -> None:
    """Before v2 projects were listed unlabelled, so the model could read about one and
    had no way to put it on the resume — prompt cost with no possible output. The
    description has to be here too: it is the source a rewrite must be traceable to.
    """
    rendered = tailoring.render_profile(profile)

    assert "[P1] Portfolio Site: Personal site built with Next.js" in rendered
    # P2 has no description recorded, and inventing a colon and nothing after it would
    # read to the model as an empty one.
    assert "[P2] Crossword Solver" in rendered
    assert "[P2] Crossword Solver:" not in rendered


def test_prompt_includes_the_posting_and_the_profile(profile, posting) -> None:
    prompt = tailoring.build_prompt(profile, posting)

    assert "Globex" in prompt and "Senior Backend Engineer" in prompt
    assert "Northwind Systems" in prompt
    assert "Python" in prompt
    # The template's own instructions survived formatting.
    assert "rationale" in prompt


def test_prompt_lists_each_skill_on_its_own_line(profile, posting) -> None:
    """Regression: a live run copied a whole grouped line back as one skill.

    The profile was rendered as "Languages: Python, SQL", and the model returned a
    skill literally named "Languages: Python, SQL" — caught by the guardrails, but a
    wasted generation. Each skill now stands alone with its category parenthesised.
    """
    rendered = tailoring.render_profile(profile)

    assert "- Python  (Languages)" in rendered
    assert "- Postgres  (Databases)" in rendered
    # The grouped form that caused it must not reappear.
    assert "Languages: Python" not in rendered

    for line in rendered.splitlines():
        if line.strip().startswith("- "):
            name = line.strip()[2:].split("  (")[0]
            assert ":" not in name and "," not in name


# --- the retry loop ---------------------------------------------------------


def test_clean_first_attempt_returns_immediately(profile, posting) -> None:
    provider = FakeLLMProvider([valid_resume()])
    result = tailoring.generate(profile, posting, provider)

    assert result.attempts == 1
    assert len(provider.prompts) == 1
    assert result.rationale


def test_violations_are_fed_back_and_a_clean_retry_succeeds(profile, posting) -> None:
    provider = FakeLLMProvider([broken_resume(), valid_resume()])
    result = tailoring.generate(profile, posting, provider)

    assert result.attempts == 2
    # The retry has to name the problem; "try again" produces the same output.
    assert "Kubernetes" in provider.prompts[1]
    assert "rejected by automated validation" in provider.prompts[1]


def test_persistent_violations_stop_after_two_retries(profile, posting) -> None:
    provider = FakeLLMProvider([broken_resume(), broken_resume(), broken_resume()])

    with pytest.raises(GuardrailFailure) as raised:
        tailoring.generate(profile, posting, provider)

    assert len(provider.prompts) == 3, "one attempt plus MAX_RETRIES"
    assert raised.value.attempts == 3
    assert any("Kubernetes" in str(v) for v in raised.value.violations)


def test_bad_output_is_never_returned(profile, posting) -> None:
    """The one outcome this phase exists to prevent."""
    provider = FakeLLMProvider([broken_resume()] * 3)
    with pytest.raises(GuardrailFailure):
        tailoring.generate(profile, posting, provider)


# --- assembly ---------------------------------------------------------------


def test_assembly_takes_facts_from_the_profile_not_the_model(profile) -> None:
    resume = tailoring.assemble(valid_resume(), profile)

    experience = resume.experiences[0]
    assert experience.company == "Northwind Systems"
    assert experience.title == "Software Engineer"
    assert experience.start_date == date(2021, 3, 1)
    assert experience.end_date == date(2024, 6, 1)
    # Only the bullet wording came from the model.
    assert experience.bullets[0].startswith("Hardened the payment service")


def test_assembly_carries_identity_and_education_through(profile) -> None:
    resume = tailoring.assemble(valid_resume(), profile)

    assert resume.full_name == "Dana Reed"
    assert resume.email == "dana@example.com"
    assert [e.school for e in resume.education] == ["State University"]
    assert [link.label for link in resume.links] == ["GitHub"]


def test_assembly_omits_unselected_experiences(profile) -> None:
    """A shorter, sharper resume is the point — E2 was not selected."""
    resume = tailoring.assemble(valid_resume(), profile)
    assert [e.company for e in resume.experiences] == ["Northwind Systems"]


def test_assembly_ignores_an_unresolvable_reference(profile) -> None:
    """Belt and braces: guardrails reject this first, but assembly must not invent."""
    tailored = valid_resume()
    tailored.experiences.append(TailoredExperience(source="E9", bullets=[]))

    resume = tailoring.assemble(tailored, profile)
    assert len(resume.experiences) == 1


def test_bullet_order_follows_the_model_not_the_profile(profile) -> None:
    """Selection includes ordering — that's part of tailoring."""
    tailored = valid_resume()
    tailored.experiences[0].bullets = [
        TailoredBullet(source="E1B2", text="Migrated the billing database to Postgres"),
        TailoredBullet(source="E1B1", text="Hardened the payment retry path"),
    ]
    resume = tailoring.assemble(tailored, profile)
    assert resume.experiences[0].bullets[0].startswith("Migrated")


# --- assembling projects ----------------------------------------------------


def test_project_facts_come_from_the_profile_and_only_the_text_from_the_model(
    profile,
) -> None:
    resume = tailoring.assemble(valid_resume(), profile)

    project = resume.projects[0]
    assert project.name == "Portfolio Site"
    assert project.url == "https://dana.example/portfolio"
    assert project.start_date == date(2022, 4, 1)
    assert project.end_date == date(2022, 9, 1)
    assert project.description.endswith("deployed as a single container")


def test_an_unselected_project_stays_off_the_resume(profile) -> None:
    """P2 exists in the profile and was not chosen. Projects are tailored, not appended
    wholesale the way education is."""
    resume = tailoring.assemble(valid_resume(), profile)
    assert [p.name for p in resume.projects] == ["Portfolio Site"]


def test_an_omitted_project_description_is_not_backfilled(profile) -> None:
    """The model saw the profile's own wording and chose to leave it out. Reinstating it
    would put untailored text on a tailored resume."""
    tailored = valid_resume()
    tailored.projects[0].text = ""

    resume = tailoring.assemble(tailored, profile)
    assert resume.projects[0].name == "Portfolio Site"
    assert resume.projects[0].description is None


def test_assembly_ignores_an_unresolvable_project_reference(profile) -> None:
    tailored = valid_resume()
    tailored.projects.append(TailoredProject(source="P9", text=""))

    resume = tailoring.assemble(tailored, profile)
    assert len(resume.projects) == 1


# --- the one-page budget ----------------------------------------------------


def test_selection_is_capped_at_what_fits_one_page(profile) -> None:
    """The prompt asks for these limits; assembly is the backstop that makes them true.

    Enforcing them as a guardrail instead would spend a whole extra generation to obtain
    output the server can produce by slicing.
    """
    tailored = valid_resume()
    tailored.experiences = [
        TailoredExperience(
            source="E1",
            bullets=[
                TailoredBullet(source="E1B1", text="Hardened the payment retry path")
                for _ in range(9)
            ],
        )
    ]
    tailored.skills = ["Python"] * 30

    resume = tailoring.assemble(tailored, profile)

    assert len(resume.experiences[0].bullets) == tailoring.MAX_BULLETS
    assert len(resume.skills) == tailoring.MAX_SKILLS


def test_the_experience_and_project_caps_hold_too(profile) -> None:
    """Separated because the fixture profile has only two of each, so exceeding these
    caps needs repeated labels — which assembly resolves happily even though the
    guardrails would have rejected them."""
    tailored = valid_resume()
    tailored.experiences = [TailoredExperience(source="E1", bullets=[])] * 9
    tailored.projects = [TailoredProject(source="P1", text="")] * 9

    resume = tailoring.assemble(tailored, profile)

    assert len(resume.experiences) == tailoring.MAX_EXPERIENCES
    assert len(resume.projects) == tailoring.MAX_PROJECTS


def test_the_cap_keeps_what_the_model_ranked_highest(profile) -> None:
    """Slicing is only defensible because the model was told to order by relevance —
    so the first N are the most relevant N, not an arbitrary N."""
    tailored = valid_resume()
    tailored.experiences[0].bullets = [
        TailoredBullet(source="E1B1", text=f"Hardened the payment retry path {n}")
        for n in range(9)
    ]

    resume = tailoring.assemble(tailored, profile)
    assert resume.experiences[0].bullets[0].endswith("0")
    assert resume.experiences[0].bullets[-1].endswith(str(tailoring.MAX_BULLETS - 1))
