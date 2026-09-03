"""Prompt rendering, the retry loop, and assembly."""

import uuid
from datetime import date

import pytest

from models.application import JobPosting
from models.enums import ExtractionMethod
from schemas.resume import TailoredBullet, TailoredExperience, TailoredResume
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
