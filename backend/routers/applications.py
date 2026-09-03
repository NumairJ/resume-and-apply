"""Application tracking: the saved jobs and where each one stands.

No `/api` prefix — the Next.js rewrite strips it before the request reaches FastAPI.
"""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.db import get_db
from core.deps import get_current_user_id
from models.application import Application
from models.enums import ApplicationStatus
from repositories.application import ApplicationRepository, JobPostingRepository
from schemas.application import ApplicationCreate, ApplicationRead, ApplicationUpdate
from services import applications as application_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    return ApplicationRepository(session).list_for_user(user_id)


@router.post("", response_model=ApplicationRead)
def save_application(
    payload: ApplicationCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    """Track a job posting, whether or not a resume has been generated for it.

    Returns the existing application when there already is one for this posting rather
    than creating a second: generating a resume creates the application, so the Apply
    page's "Save" would otherwise duplicate the row it is trying to update.
    """
    posting = JobPostingRepository(session).get(payload.job_posting_id)
    if posting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job posting not found")

    application = application_service.find_or_create(session, user_id, posting)
    ApplicationRepository(session).update(
        application,
        **payload.model_dump(exclude_unset=True, exclude={"job_posting_id"}),
    )
    session.commit()
    return application


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    """Change status, notes, or the date applied.

    Any status may follow any other. There is no transition graph on purpose: marking
    something `applied` by mistake and setting it back is ordinary use, and a state
    machine here would obstruct the user without protecting anything.
    """
    application = _owned(session, application_id, user_id)
    values = payload.model_dump(exclude_unset=True)

    # Moving to `applied` without saying when means "today". Only filled if empty, so
    # correcting the date later isn't undone by a subsequent status edit.
    if (
        values.get("status") == ApplicationStatus.APPLIED
        and values.get("applied_at") is None
        and application.applied_at is None
    ):
        values["applied_at"] = date.today()

    ApplicationRepository(session).update(application, **values)
    session.commit()
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    application = _owned(session, application_id, user_id)
    application_service.delete(session, application)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _owned(
    session: Session, application_id: uuid.UUID, user_id: uuid.UUID
) -> Application:
    """404, never 403 — a 403 would confirm the row exists."""
    application = ApplicationRepository(session).get(application_id)
    if application is None or application.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return application
