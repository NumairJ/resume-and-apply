import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from models.application import Application, JobPosting, Resume
from repositories.base import BaseRepository


class JobPostingRepository(BaseRepository[JobPosting]):
    model = JobPosting

    def get_by_source_url(self, source_url: str) -> JobPosting | None:
        stmt = select(JobPosting).where(JobPosting.source_url == source_url)
        return self.session.scalars(stmt).first()

    def find_duplicates_for_user(
        self, user_id: uuid.UUID, fingerprint: str
    ) -> list[Application]:
        """Applications this user already has against a matching posting.

        Duplicate detection deliberately joins through applications rather than
        looking at postings alone: an abandoned extraction is not something the user
        "already applied to".
        """
        stmt = (
            select(Application)
            .join(JobPosting)
            .where(
                Application.user_id == user_id,
                JobPosting.fingerprint == fingerprint,
            )
            .order_by(Application.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def sweep_expired(self) -> int:
        """Delete expired postings that nothing references. Returns the row count.

        Called opportunistically on extraction rather than from a scheduler — this
        runs a few times a day at most, and sweep-on-write has no background
        machinery that can fail silently.
        """
        referenced = select(Application.job_posting_id)
        stmt = delete(JobPosting).where(
            JobPosting.expires_at.is_not(None),
            JobPosting.expires_at < datetime.now(timezone.utc),
            JobPosting.id.not_in(referenced),
        )
        return self.session.execute(stmt).rowcount


class ApplicationRepository(BaseRepository[Application]):
    model = Application

    def list_for_user(self, user_id: uuid.UUID) -> list[Application]:
        """Newest first, with the posting and resumes loaded.

        Eager-loaded because `ApplicationRead` serialises both: without this the
        applications table costs two extra queries per row.
        """
        stmt = (
            select(Application)
            .where(Application.user_id == user_id)
            .options(
                selectinload(Application.job_posting),
                selectinload(Application.resumes),
            )
            .order_by(Application.created_at.desc())
        )
        return list(self.session.scalars(stmt))


class ResumeRepository(BaseRepository[Resume]):
    model = Resume

    def list_for_application(self, application_id: uuid.UUID) -> list[Resume]:
        stmt = (
            select(Resume)
            .where(Resume.application_id == application_id)
            .order_by(Resume.created_at)
        )
        return list(self.session.scalars(stmt))
