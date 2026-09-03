"""Application tracking routes, and what saving does to the posting's lifetime."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.application import Application, JobPosting
from models.enums import ApplicationStatus, ExtractionMethod
from models.profile import User
from repositories.application import (
    ApplicationRepository,
    JobPostingRepository,
    ResumeRepository,
)
from services import render
from services.tailoring import assemble
from tests.factories import sample_profile, valid_resume


def a_posting(session: Session, **overrides) -> JobPosting:
    values = {
        "company": "Globex",
        "title": "Senior Backend Engineer",
        "source_url": f"https://example.com/jobs/{uuid.uuid4()}",
        "fingerprint": uuid.uuid4().hex,
        "extraction_method": ExtractionMethod.LLM,
        # As a freshly extracted posting would be: provisional until something tracks it.
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return JobPostingRepository(session).create(**{**values, **overrides})


@pytest.fixture
def posting(session: Session) -> JobPosting:
    created = a_posting(session)
    session.commit()
    return created


# --- saving -----------------------------------------------------------------


def test_saving_creates_an_application_and_makes_the_posting_permanent(
    client: TestClient, session: Session, posting: JobPosting
) -> None:
    """A tracked posting must outlive the 24h TTL — that is what saving means."""
    response = client.post("/applications", json={"job_posting_id": str(posting.id)})

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert response.json()["job_posting"]["company"] == "Globex"

    session.refresh(posting)
    assert posting.expires_at is None


def test_a_saved_posting_survives_the_sweep(
    client: TestClient, session: Session
) -> None:
    """The TTL sweep must not delete a posting out from under an application."""
    saved = a_posting(session, expires_at=datetime.now(timezone.utc) - timedelta(days=2))
    abandoned = a_posting(
        session, expires_at=datetime.now(timezone.utc) - timedelta(days=2)
    )
    session.commit()

    client.post("/applications", json={"job_posting_id": str(saved.id)})
    JobPostingRepository(session).sweep_expired()
    session.commit()

    assert session.get(JobPosting, saved.id) is not None
    assert session.get(JobPosting, abandoned.id) is None


def test_saving_twice_returns_the_same_application(
    client: TestClient, posting: JobPosting
) -> None:
    """Generating already creates the application, so "Save" must not duplicate it."""
    first = client.post("/applications", json={"job_posting_id": str(posting.id)})
    second = client.post(
        "/applications",
        json={"job_posting_id": str(posting.id), "notes": "worth a follow-up"},
    )

    assert first.json()["id"] == second.json()["id"]
    assert second.json()["notes"] == "worth a follow-up"
    assert len(client.get("/applications").json()) == 1


def test_saving_an_unknown_posting_is_404(client: TestClient) -> None:
    response = client.post(
        "/applications", json={"job_posting_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


# --- listing and updating ---------------------------------------------------


def test_list_is_newest_first_with_the_posting_attached(
    client: TestClient, session: Session
) -> None:
    """Timestamps are set explicitly rather than relying on creation order.

    `created_at` defaults to `func.now()`, which Postgres evaluates as
    *transaction* start time. The whole suite runs inside one transaction, so two rows
    created in the same test are born with an identical timestamp and the ordering
    would be an arbitrary tie-break rather than the behaviour under test.
    """
    older = a_posting(session, company="Initech")
    newer = a_posting(session, company="Umbrella")
    session.commit()

    for posting_id, age in ((older.id, 3), (newer.id, 1)):
        created = client.post(
            "/applications", json={"job_posting_id": str(posting_id)}
        ).json()["id"]
        session.get(Application, uuid.UUID(created)).created_at = datetime.now(
            timezone.utc
        ) - timedelta(days=age)
    session.commit()

    listed = client.get("/applications").json()
    assert [entry["job_posting"]["company"] for entry in listed] == [
        "Umbrella",
        "Initech",
    ]


def test_status_notes_and_date_are_editable(
    client: TestClient, posting: JobPosting
) -> None:
    application_id = client.post(
        "/applications", json={"job_posting_id": str(posting.id)}
    ).json()["id"]

    response = client.patch(
        f"/applications/{application_id}",
        json={"status": "interviewing", "notes": "phone screen went well"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "interviewing"
    assert response.json()["notes"] == "phone screen went well"


def test_marking_applied_fills_in_todays_date(
    client: TestClient, posting: JobPosting
) -> None:
    application_id = client.post(
        "/applications", json={"job_posting_id": str(posting.id)}
    ).json()["id"]

    response = client.patch(
        f"/applications/{application_id}", json={"status": "applied"}
    )
    assert response.json()["applied_at"] == date.today().isoformat()


def test_an_existing_applied_date_is_not_overwritten(
    client: TestClient, posting: JobPosting
) -> None:
    """Correcting the date must survive a later status edit."""
    application_id = client.post(
        "/applications", json={"job_posting_id": str(posting.id)}
    ).json()["id"]
    client.patch(
        f"/applications/{application_id}",
        json={"status": "applied", "applied_at": "2026-01-15"},
    )

    response = client.patch(
        f"/applications/{application_id}", json={"status": "applied"}
    )
    assert response.json()["applied_at"] == "2026-01-15"


def test_any_status_may_follow_any_other(
    client: TestClient, posting: JobPosting
) -> None:
    """No transition graph on purpose — undoing a mistaken status is ordinary use."""
    application_id = client.post(
        "/applications", json={"job_posting_id": str(posting.id)}
    ).json()["id"]

    for status_value in ("offer", "saved", "rejected", "applied"):
        response = client.patch(
            f"/applications/{application_id}", json={"status": status_value}
        )
        assert response.status_code == 200
        assert response.json()["status"] == status_value


# --- deleting ---------------------------------------------------------------


def test_deleting_removes_the_resume_rows_and_their_files(
    client: TestClient, session: Session, user: User, posting: JobPosting
) -> None:
    """The database cascade knows nothing about the PDFs, so the service unlinks them."""
    application = ApplicationRepository(session).create(
        user_id=user.id,
        job_posting_id=posting.id,
        status=ApplicationStatus.SAVED,
    )
    resume_id = uuid.uuid4()
    rendered = render.render(assemble(valid_resume(), sample_profile()), resume_id)
    ResumeRepository(session).create(
        id=resume_id,
        application_id=application.id,
        file_path=str(rendered.pdf_path),
        content_hash=rendered.content_hash,
        provider="fake",
        model="fake",
        prompt_version="tailor_resume.v1",
    )
    session.commit()

    response = client.delete(f"/applications/{application.id}")

    assert response.status_code == 204
    assert session.get(Application, application.id) is None
    assert ResumeRepository(session).get(resume_id) is None
    assert not rendered.pdf_path.exists()
    assert not rendered.html_path.exists()


def test_deleting_lets_the_posting_expire_again(
    client: TestClient, session: Session, posting: JobPosting
) -> None:
    """Otherwise every abandoned experiment would pin a posting row forever."""
    application_id = client.post(
        "/applications", json={"job_posting_id": str(posting.id)}
    ).json()["id"]
    session.refresh(posting)
    assert posting.expires_at is None

    client.delete(f"/applications/{application_id}")

    session.refresh(posting)
    assert posting.expires_at is not None
    assert posting.expires_at > datetime.now(timezone.utc)


def test_another_users_application_is_404_not_403(
    client: TestClient, session: Session, other_user: User, posting: JobPosting
) -> None:
    """A 403 would confirm the row exists."""
    theirs = ApplicationRepository(session).create(
        user_id=other_user.id,
        job_posting_id=posting.id,
        status=ApplicationStatus.SAVED,
    )
    session.commit()

    assert client.get("/applications").json() == []
    assert client.patch(
        f"/applications/{theirs.id}", json={"status": "applied"}
    ).status_code == 404
    assert client.delete(f"/applications/{theirs.id}").status_code == 404


def test_deleting_an_unknown_application_is_404(client: TestClient) -> None:
    assert client.delete(f"/applications/{uuid.uuid4()}").status_code == 404
