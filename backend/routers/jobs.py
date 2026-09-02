"""Job extraction routes.

As with the profile router, nothing here is namespaced under `/api` — the Next.js
rewrite strips that prefix, so the browser's `/api/jobs/extract` arrives as
`/jobs/extract`.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.db import get_db
from core.deps import NO_PROVIDER_MESSAGE, get_current_user_id
from models.application import Application
from repositories.application import JobPostingRepository
from schemas.application import (
    DuplicateWarning,
    ExtractionResponse,
    ExtractRequest,
    JobPostingRead,
    JobPostingUpdate,
)
from services import extraction
from services.extraction.fetch import FetchError, build_client
from services.llm.base import LLMError, LLMProvider

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_http_client() -> Iterator[httpx.Client]:
    """One outbound client per request, closed when it finishes.

    A dependency rather than something the service builds for itself, so tests can
    supply an `httpx.MockTransport` and never touch the network.
    """
    with build_client() as client:
        yield client


def get_optional_provider() -> LLMProvider | None:
    """The provider injection point for extraction.

    Returns None in production, which lets the pipeline run every free stage and only
    fail at the one that actually needs a model — so supported job boards keep working
    with no provider configured. Tests override this dependency with a fake.
    """
    return None


@router.post("/extract", response_model=ExtractionResponse)
def extract_job(
    payload: ExtractRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    provider: LLMProvider | None = Depends(get_optional_provider),
    client: httpx.Client = Depends(get_http_client),
) -> Any:
    try:
        result = extraction.extract(
            session, payload.url, user_id, provider=provider, client=client
        )
    except extraction.NotAJobPosting as exc:
        # 422: the page was retrieved fine, it just isn't a posting. Name what was
        # missing so the user isn't left guessing.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": str(exc), "reasons": exc.reasons},
        ) from exc
    except extraction.LLMUnavailable as exc:
        # A real page that only the model could read, with no model available. Not a
        # failure of extraction, so it gets its own status rather than a 422 or 502.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, NO_PROVIDER_MESSAGE
        ) from exc
    except FetchError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    session.commit()
    return ExtractionResponse(
        job=result.posting,
        duplicate=_warning(result.duplicate),
        cached=result.cached,
    )


@router.patch("/{job_id}", response_model=JobPostingRead)
def update_job(
    job_id: uuid.UUID,
    payload: JobPostingUpdate,
    session: Session = Depends(get_db),
) -> Any:
    """Let the user correct a mis-parsed field before it becomes a resume."""
    repo = JobPostingRepository(session)
    posting = repo.get(job_id)
    if posting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    repo.update(posting, **payload.model_dump(exclude_unset=True))
    session.commit()
    return posting


def _warning(application: Application | None) -> DuplicateWarning | None:
    if application is None:
        return None
    return DuplicateWarning(
        application_id=application.id,
        status=application.status,
        applied_at=application.applied_at,
        first_seen=application.created_at,
        company=application.job_posting.company,
        title=application.job_posting.title,
    )
