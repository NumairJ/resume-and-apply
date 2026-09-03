"""Routes for /providers and /resumes/generate."""

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.deps import get_llm_provider
from models.enums import ExtractionMethod
from models.profile import User
from repositories.application import JobPostingRepository
from repositories.profile import ExperienceBulletRepository, ExperienceRepository, SkillRepository
from services.llm.anthropic_provider import DEFAULT_MODEL
from services.llm.base import LLMError
from services.llm.fake import FakeLLMProvider
from tests.factories import broken_resume, valid_resume

POSTING = {
    "company": "Globex",
    "title": "Senior Backend Engineer",
    "description": "Payment reliability and Postgres depth.",
    "source_url": "https://example.com/jobs/1",
    "fingerprint": "fp",
    "extraction_method": ExtractionMethod.LLM,
}


@pytest.fixture
def seeded(session: Session, user: User) -> dict:
    """A profile mirroring tests.factories, written to the database.

    The route reads the profile through `services.profile.get_profile`, so the labels
    the guardrails resolve have to come from real rows, not the in-memory fixture.
    """
    user.full_name = "Dana Reed"
    user.email = "dana@example.com"

    experiences = ExperienceRepository(session)
    bullets = ExperienceBulletRepository(session)
    skills = SkillRepository(session)

    first = experiences.create(
        user_id=user.id,
        company="Northwind Systems",
        title="Software Engineer",
        start_date=date(2021, 3, 1),
        end_date=date(2024, 6, 1),
        position=0,
    )
    bullets.create(
        experience_id=first.id,
        position=0,
        text="Reduced payment service error rates by hardening the retry path",
    )
    bullets.create(
        experience_id=first.id,
        position=1,
        text="Migrated the billing database to Postgres with no downtime",
    )
    second = experiences.create(
        user_id=user.id,
        company="Contoso",
        title="Junior Developer",
        start_date=date(2019, 1, 1),
        end_date=date(2021, 2, 1),
        position=1,
    )
    bullets.create(
        experience_id=second.id,
        position=0,
        text="Built internal React dashboards for the support team",
    )
    skills.create(user_id=user.id, name="Python", category="Languages", position=0)
    skills.create(user_id=user.id, name="Postgres", category="Databases", position=1)

    posting = JobPostingRepository(session).create(**POSTING)
    session.commit()
    return {"posting_id": str(posting.id)}


def with_provider(client: TestClient, provider) -> TestClient:
    client.app.dependency_overrides[get_llm_provider] = lambda: provider
    return client


# --- /providers -------------------------------------------------------------


def test_list_providers(client: TestClient) -> None:
    response = client.get("/providers")
    assert response.status_code == 200

    names = [entry["name"] for entry in response.json()]
    assert "anthropic" in names
    # A fake reachable in production would serve invented resumes as real ones.
    assert "fake" not in names


def test_providers_lists_models_and_leaks_nothing(client: TestClient) -> None:
    entry = client.get("/providers").json()[0]
    assert DEFAULT_MODEL in entry["available_models"]
    assert "api_key" not in str(entry).lower()


# --- /resumes/generate ------------------------------------------------------


def test_generate_returns_resume_and_rationale(client: TestClient, seeded: dict) -> None:
    provider = FakeLLMProvider([valid_resume()])
    response = with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rationale"]
    assert body["attempts"] == 1
    assert body["prompt_version"] == "tailor_resume.v1"

    resume = body["resume"]
    assert resume["full_name"] == "Dana Reed"
    # Facts came from the database, not the model.
    assert resume["experiences"][0]["company"] == "Northwind Systems"
    assert resume["experiences"][0]["start_date"] == "2021-03-01"
    assert resume["skills"] == ["Python", "Postgres"]


def test_generate_sends_the_posting_into_the_prompt(
    client: TestClient, seeded: dict
) -> None:
    provider = FakeLLMProvider([valid_resume()])
    with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )
    assert "Globex" in provider.prompts[0]
    assert "[E1B1]" in provider.prompts[0]


def test_guardrail_failure_is_422_naming_the_violations(
    client: TestClient, seeded: dict
) -> None:
    """A rejected generation must say why, not fail opaquely."""
    provider = FakeLLMProvider([broken_resume()] * 3)
    response = with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Kubernetes" in violation for violation in detail["violations"])


def test_provider_failure_is_502(client: TestClient, seeded: dict) -> None:
    class Failing(FakeLLMProvider):
        def generate_structured(self, prompt, response_model):
            raise LLMError("the key was rejected")

    response = with_provider(client, Failing()).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )
    assert response.status_code == 502
    assert "rejected" in response.json()["detail"]


def test_unknown_posting_is_404(client: TestClient, seeded: dict) -> None:
    response = with_provider(client, FakeLLMProvider([valid_resume()])).post(
        "/resumes/generate", json={"job_posting_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_empty_profile_is_refused_before_calling_the_model(
    client: TestClient, session: Session, user: User
) -> None:
    """With no experience to select from, the model would be under pressure to invent."""
    posting = JobPostingRepository(session).create(**POSTING)
    session.commit()

    provider = FakeLLMProvider([valid_resume()])
    response = with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": str(posting.id)}
    )

    assert response.status_code == 422
    assert "experience" in response.json()["detail"].lower()
    assert provider.prompts == [], "no tokens should be spent"


def test_no_provider_configured_is_503(
    client: TestClient, seeded: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real dependency, with no key from a header or the environment."""
    from core import deps

    monkeypatch.setattr(deps.settings, "anthropic_api_key", None)
    response = client.post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )
    assert response.status_code == 503


def test_unknown_provider_header_is_400(
    client: TestClient, seeded: dict
) -> None:
    response = client.post(
        "/resumes/generate",
        json={"job_posting_id": seeded["posting_id"]},
        headers={"X-LLM-Provider": "not-a-provider", "X-LLM-Api-Key": "sk-test"},
    )
    assert response.status_code == 400
    assert "not-a-provider" in response.json()["detail"]
