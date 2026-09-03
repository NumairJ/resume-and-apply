"""Resume generation, preview and download.

Nothing is namespaced under `/api` — the Next.js rewrite strips that prefix, so the
browser's `/api/resumes/generate` arrives here as `/resumes/generate`.
"""

import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from core.db import get_db
from core.deps import get_current_user_id, get_llm_provider
from models.application import Resume as ResumeRow
from repositories.application import JobPostingRepository, ResumeRepository
from schemas.resume import GenerateResumeRequest, GenerateResumeResponse
from services import render, resumes as resume_service, tailoring
from services.guardrails import GuardrailFailure
from services.llm.base import LLMError, LLMProvider
from services.profile import get_profile

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/generate", response_model=GenerateResumeResponse)
def generate_resume(
    payload: GenerateResumeRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    provider: LLMProvider = Depends(get_llm_provider),
) -> Any:
    posting = JobPostingRepository(session).get(payload.job_posting_id)
    if posting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job posting not found")

    profile = get_profile(session, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    if not profile.experiences:
        # Tailoring selects from real experience. With none recorded there is nothing
        # to select, and the model would be under pressure to invent.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Add at least one experience to your profile before generating a resume.",
        )

    try:
        generated = resume_service.generate(
            session, profile, posting, user_id, provider
        )
    except GuardrailFailure as exc:
        # The generation was refused rather than silently returned. Name the violations
        # so the failure is diagnosable instead of mysterious.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "message": str(exc),
                "violations": [str(violation) for violation in exc.violations],
            },
        ) from exc
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    session.commit()
    return GenerateResumeResponse(
        resume_id=generated.row.id,
        application_id=generated.row.application_id,
        resume=generated.result.resume,
        rationale=generated.result.rationale,
        provider=provider.name,
        model=getattr(provider, "model", ""),
        prompt_version=tailoring.PROMPT_VERSION,
        attempts=generated.result.attempts,
    )


@router.get("/{resume_id}/preview", response_class=HTMLResponse)
def preview_resume(
    resume_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    """The exact HTML WeasyPrint turned into the PDF, so the two cannot disagree."""
    _owned(session, resume_id, user_id)
    return HTMLResponse(_read(render.html_path(resume_id)).decode("utf-8"))


@router.get("/{resume_id}/download")
def download_resume(
    resume_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    resume = _owned(session, resume_id, user_id)
    path = Path(resume.file_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The PDF is no longer on disk")

    company = resume.application.job_posting.company
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"resume-{_slug(company)}.pdf",
    )


def _owned(session: Session, resume_id: uuid.UUID, user_id: uuid.UUID) -> ResumeRow:
    """404 rather than 403 for another user's resume, as everywhere else in this API."""
    resume = ResumeRepository(session).get(resume_id)
    if resume is None or resume.application.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return resume


def _read(path: Path) -> bytes:
    """A row whose file is gone is a 404, not a 500.

    The PDFs live on a named volume the database knows nothing about, so a wiped volume
    under a live database is a real state to be in. An honest "not there" beats a
    traceback.
    """
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The file is no longer on disk")
    return path.read_bytes()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "resume"
