"""Round-trip tests for job postings, applications and resumes."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.enums import ApplicationStatus, ExtractionMethod
from models.profile import User
from repositories.application import (
    ApplicationRepository,
    JobPostingRepository,
    ResumeRepository,
)

POSTING = {
    "company": "Acme",
    "title": "Backend Engineer",
    "source_url": "https://boards.greenhouse.io/acme/jobs/1",
    "extraction_method": ExtractionMethod.ATS_GREENHOUSE,
    "fingerprint": "abc123",
}


def test_job_posting_round_trip(session: Session) -> None:
    repo = JobPostingRepository(session)

    posting = repo.create(**POSTING)
    assert repo.get(posting.id) is not None
    assert posting.extraction_method is ExtractionMethod.ATS_GREENHOUSE
    # The column defaults to permanent; the 24h TTL on abandoned extractions is set by
    # the extraction service, not the model.
    assert posting.expires_at is None

    repo.update(posting, title="Senior Backend Engineer")
    assert repo.get(posting.id).title == "Senior Backend Engineer"

    assert repo.get_by_source_url(POSTING["source_url"]).id == posting.id

    repo.delete(posting)
    assert repo.get(posting.id) is None


def test_application_round_trip(session: Session, user: User) -> None:
    postings = JobPostingRepository(session)
    applications = ApplicationRepository(session)

    posting = postings.create(**POSTING)
    application = applications.create(user_id=user.id, job_posting_id=posting.id)

    assert application.status is ApplicationStatus.SAVED
    assert application.job_posting.company == "Acme"

    applications.update(
        application,
        status=ApplicationStatus.INTERVIEWING,
        applied_at=date(2026, 3, 4),
        notes="Phone screen booked",
    )
    fetched = applications.get(application.id)
    assert fetched.status is ApplicationStatus.INTERVIEWING
    assert fetched.applied_at == date(2026, 3, 4)

    applications.delete(fetched)
    assert applications.get(application.id) is None


def test_list_for_user_filters_by_owner(
    session: Session, user: User, other_user: User
) -> None:
    postings = JobPostingRepository(session)
    applications = ApplicationRepository(session)
    posting = postings.create(**POSTING)

    mine = applications.create(user_id=user.id, job_posting_id=posting.id)
    applications.create(user_id=other_user.id, job_posting_id=posting.id)

    assert [a.id for a in applications.list_for_user(user.id)] == [mine.id]


def test_resume_round_trip_and_ordering(session: Session, user: User) -> None:
    postings = JobPostingRepository(session)
    applications = ApplicationRepository(session)
    resumes = ResumeRepository(session)

    posting = postings.create(**POSTING)
    application = applications.create(user_id=user.id, job_posting_id=posting.id)

    common = {
        "application_id": application.id,
        "file_path": "/data/resumes/a.pdf",
        "content_hash": "0" * 64,
        "provider": "anthropic",
        "model": "claude-opus-5",
        "prompt_version": "tailor_resume.v1",
    }
    first = resumes.create(**common)
    # Regenerating is an explicit feature, so an application keeps several resumes.
    second = resumes.create(**{**common, "file_path": "/data/resumes/b.pdf"})

    listed = resumes.list_for_application(application.id)
    assert [r.id for r in listed] == [first.id, second.id]

    resumes.delete(first)
    assert [r.id for r in resumes.list_for_application(application.id)] == [second.id]


def test_deleting_application_cascades_to_resumes(
    session: Session, user: User
) -> None:
    postings = JobPostingRepository(session)
    applications = ApplicationRepository(session)
    resumes = ResumeRepository(session)

    posting = postings.create(**POSTING)
    application = applications.create(user_id=user.id, job_posting_id=posting.id)
    resumes.create(
        application_id=application.id,
        file_path="/data/resumes/a.pdf",
        content_hash="0" * 64,
        provider="anthropic",
        model="claude-opus-5",
        prompt_version="tailor_resume.v1",
    )

    applications.delete(application)

    assert resumes.list_for_application(application.id) == []


def test_find_duplicates_matches_only_this_users_applications(
    session: Session, user: User, other_user: User
) -> None:
    postings = JobPostingRepository(session)
    applications = ApplicationRepository(session)

    posting = postings.create(**POSTING)
    # An extracted-but-never-saved posting must not count as a duplicate.
    postings.create(**{**POSTING, "source_url": "https://example.com/other"})

    assert postings.find_duplicates_for_user(user.id, "abc123") == []

    mine = applications.create(user_id=user.id, job_posting_id=posting.id)
    applications.create(user_id=other_user.id, job_posting_id=posting.id)

    duplicates = postings.find_duplicates_for_user(user.id, "abc123")
    assert [a.id for a in duplicates] == [mine.id]

    assert postings.find_duplicates_for_user(user.id, "does-not-match") == []


def test_sweep_deletes_only_expired_unreferenced_postings(
    session: Session, user: User
) -> None:
    postings = JobPostingRepository(session)
    applications = ApplicationRepository(session)

    now = datetime.now(timezone.utc)

    permanent = postings.create(**POSTING, expires_at=None)
    fresh = postings.create(
        **{**POSTING, "source_url": "https://example.com/fresh"},
        expires_at=now + timedelta(hours=24),
    )
    abandoned = postings.create(
        **{**POSTING, "source_url": "https://example.com/abandoned"},
        expires_at=now - timedelta(hours=1),
    )
    # Expired, but saved into an application — must survive.
    expired_but_saved = postings.create(
        **{**POSTING, "source_url": "https://example.com/saved"},
        expires_at=now - timedelta(hours=1),
    )
    applications.create(user_id=user.id, job_posting_id=expired_but_saved.id)

    assert postings.sweep_expired() == 1

    session.expire_all()
    assert postings.get(abandoned.id) is None
    assert postings.get(permanent.id) is not None
    assert postings.get(fresh.id) is not None
    assert postings.get(expired_but_saved.id) is not None
