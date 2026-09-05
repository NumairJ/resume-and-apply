"""Routes for /providers and /resumes/generate."""

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.deps import DEFAULT_USER_ID, get_llm_provider
from models.enums import ApplicationStatus, ExtractionMethod
from models.profile import User
from repositories.application import (
    ApplicationRepository,
    JobPostingRepository,
    ResumeRepository,
)
from repositories.profile import (
    ExperienceBulletRepository,
    ExperienceRepository,
    ProjectRepository,
    SkillRepository,
)
from services import render, tailoring
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
    # As a freshly extracted posting is: provisional until something tracks it. Without
    # this the "generating makes the posting permanent" assertions would pass vacuously.
    "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
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

    projects = ProjectRepository(session)
    projects.create(
        user_id=user.id,
        name="Portfolio Site",
        description=(
            "Personal site built with Next.js and a typed API layer, "
            "deployed on a single container"
        ),
        url="https://dana.example/portfolio",
        start_date=date(2022, 4, 1),
        end_date=date(2022, 9, 1),
        position=0,
    )
    projects.create(user_id=user.id, name="Crossword Solver", position=1)

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


def generate(client: TestClient, seeded: dict, responses=None) -> dict:
    provider = FakeLLMProvider(responses or [valid_resume()])
    response = with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_generate_returns_resume_and_rationale(client: TestClient, seeded: dict) -> None:
    body = generate(client, seeded)

    assert body["rationale"]
    assert body["attempts"] == 1
    # The version in force, not a literal: what matters is that the response reports the
    # prompt the resume was actually made with, so a bump doesn't make this a lie.
    assert body["prompt_version"] == tailoring.PROMPT_VERSION

    resume = body["resume"]
    assert resume["full_name"] == "Dana Reed"
    # Facts came from the database, not the model.
    assert resume["experiences"][0]["company"] == "Northwind Systems"
    assert resume["experiences"][0]["start_date"] == "2021-03-01"
    assert resume["skills"] == ["Python", "Postgres"]


def test_generate_returns_projects_resolved_from_the_database(
    client: TestClient, seeded: dict
) -> None:
    """End to end for the whole point of this change: the model cited P1, and every
    factual field came back from the row rather than from the model."""
    project = generate(client, seeded)["resume"]["projects"][0]

    assert project["name"] == "Portfolio Site"
    assert project["url"] == "https://dana.example/portfolio"
    assert project["start_date"] == "2022-04-01"
    # Only the description is the model's.
    assert project["description"].endswith("deployed as a single container")


def test_generate_sends_the_posting_into_the_prompt(
    client: TestClient, seeded: dict
) -> None:
    provider = FakeLLMProvider([valid_resume()])
    with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )
    assert "Globex" in provider.prompts[0]
    assert "[E1B1]" in provider.prompts[0]
    assert "[P1]" in provider.prompts[0]


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


# --- what generation persists -----------------------------------------------


def test_generate_writes_a_row_and_both_files(
    client: TestClient, session: Session, seeded: dict, resume_dir: Path
) -> None:
    body = generate(client, seeded)
    resume_id = uuid.UUID(body["resume_id"])

    row = ResumeRepository(session).get(resume_id)
    assert row is not None
    assert row.application_id == uuid.UUID(body["application_id"])
    assert row.provider == "fake"
    assert row.prompt_version == tailoring.PROMPT_VERSION

    assert (resume_dir / f"{resume_id}.pdf").is_file()
    assert (resume_dir / f"{resume_id}.html").is_file()
    assert row.file_path == str(resume_dir / f"{resume_id}.pdf")


def test_stored_hash_matches_the_pdf_on_disk(
    client: TestClient, session: Session, seeded: dict
) -> None:
    """The whole point of storing a hash instead of the bytes."""
    body = generate(client, seeded)
    row = ResumeRepository(session).get(uuid.UUID(body["resume_id"]))

    on_disk = hashlib.sha256(Path(row.file_path).read_bytes()).hexdigest()
    assert row.content_hash == on_disk


def test_generate_creates_a_saved_application_and_pins_the_posting(
    client: TestClient, session: Session, seeded: dict
) -> None:
    """A generated resume needs a parent, so generation is also a save."""
    body = generate(client, seeded)

    application = ApplicationRepository(session).get(
        uuid.UUID(body["application_id"])
    )
    assert application.status == ApplicationStatus.SAVED

    posting = JobPostingRepository(session).get(uuid.UUID(seeded["posting_id"]))
    assert posting.expires_at is None


def test_regenerating_adds_a_second_resume_to_the_same_application(
    client: TestClient, session: Session, seeded: dict
) -> None:
    """Regenerating is a feature; keeping the earlier attempt costs nothing."""
    first = generate(client, seeded)
    second = generate(client, seeded)

    assert first["resume_id"] != second["resume_id"]
    assert first["application_id"] == second["application_id"]
    assert len(
        ResumeRepository(session).list_for_application(
            uuid.UUID(first["application_id"])
        )
    ) == 2


def test_a_rejected_generation_leaves_nothing_behind(
    client: TestClient, session: Session, seeded: dict, resume_dir: Path
) -> None:
    """Tailoring runs before anything is persisted, so a refusal creates no
    application, no row, and no orphan PDF."""
    provider = FakeLLMProvider([broken_resume()] * 3)
    response = with_provider(client, provider).post(
        "/resumes/generate", json={"job_posting_id": seeded["posting_id"]}
    )

    assert response.status_code == 422
    assert ApplicationRepository(session).list_for_user(DEFAULT_USER_ID) == []
    assert not resume_dir.exists() or list(resume_dir.iterdir()) == []

    posting = JobPostingRepository(session).get(uuid.UUID(seeded["posting_id"]))
    assert posting.expires_at is not None


# --- preview and download ---------------------------------------------------


def test_preview_returns_the_html_the_pdf_was_made_from(
    client: TestClient, seeded: dict, resume_dir: Path
) -> None:
    body = generate(client, seeded)
    response = client.get(f"/resumes/{body['resume_id']}/preview")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == (resume_dir / f"{body['resume_id']}.html").read_text(
        encoding="utf-8"
    )
    assert "Northwind Systems" in response.text


def test_download_returns_the_pdf(client: TestClient, seeded: dict) -> None:
    body = generate(client, seeded)
    response = client.get(f"/resumes/{body['resume_id']}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    # Named after the employer, not after a UUID the user has never seen.
    assert "resume-globex.pdf" in response.headers["content-disposition"]


def test_a_missing_file_is_404_not_500(client: TestClient, seeded: dict) -> None:
    """The PDFs live on a volume the database knows nothing about, so a row whose file
    has gone is a real state to be in."""
    body = generate(client, seeded)
    render.remove_files(uuid.UUID(body["resume_id"]))

    assert client.get(f"/resumes/{body['resume_id']}/preview").status_code == 404
    assert client.get(f"/resumes/{body['resume_id']}/download").status_code == 404


def test_unknown_resume_is_404(client: TestClient) -> None:
    assert client.get(f"/resumes/{uuid.uuid4()}/preview").status_code == 404
    assert client.get(f"/resumes/{uuid.uuid4()}/download").status_code == 404


def test_another_users_resume_is_404_not_403(
    client: TestClient, session: Session, other_user: User, seeded: dict
) -> None:
    body = generate(client, seeded)
    application = ApplicationRepository(session).get(
        uuid.UUID(body["application_id"])
    )
    application.user_id = other_user.id
    session.commit()

    assert client.get(f"/resumes/{body['resume_id']}/preview").status_code == 404
    assert client.get(f"/resumes/{body['resume_id']}/download").status_code == 404
