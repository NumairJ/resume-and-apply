"""What saving, and un-saving, an application actually does.

Both operations reach across aggregates — they change the job posting's lifetime and,
on delete, files on disk — so they live here rather than on the repository, which is
deliberately CRUD-only.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.application import Application, JobPosting
from models.enums import ApplicationStatus
from repositories.application import ApplicationRepository
from services import render
from services.extraction import TTL


def find_or_create(
    session: Session, user_id: uuid.UUID, posting: JobPosting
) -> Application:
    """The application tracking this posting for this user, creating one if needed.

    Find-*or*-create rather than create: generating a resume already makes an
    application, so a later "Save" from the Apply page must land on that same row
    instead of producing a second one for the same job.

    Either way the posting's TTL is cleared. That is the spec's meaning of saving —
    an extraction becomes permanent once something tracks it.
    """
    stmt = (
        select(Application)
        .where(
            Application.user_id == user_id,
            Application.job_posting_id == posting.id,
        )
        .order_by(Application.created_at.desc())
    )
    application = session.scalars(stmt).first()

    if application is None:
        application = ApplicationRepository(session).create(
            user_id=user_id,
            job_posting_id=posting.id,
            status=ApplicationStatus.SAVED,
        )

    posting.expires_at = None
    session.flush()
    return application


def delete(session: Session, application: Application) -> None:
    """Delete the application, its resumes' files, and the posting's claim to permanence.

    The database cascade takes the `resumes` rows; it knows nothing about the PDFs, so
    those are unlinked here first.

    Restoring `expires_at` matters because generation clears it. Without this, every
    abandoned experiment would pin a job posting row forever — the exact leak the TTL
    sweep exists to prevent.
    """
    posting = application.job_posting
    for resume in application.resumes:
        render.remove_files(resume.id)

    ApplicationRepository(session).delete(application)

    still_tracked = session.scalars(
        select(Application.id).where(Application.job_posting_id == posting.id)
    ).first()
    if still_tracked is None:
        posting.expires_at = datetime.now(timezone.utc) + TTL
        session.flush()
