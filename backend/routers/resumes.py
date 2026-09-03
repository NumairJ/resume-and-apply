"""Resume generation.

Phase 5 will add rendering and persistence on top of this route — an HTML preview, a
PDF on the shared volume, and a `resumes` row. Until then it returns the tailored resume
as JSON so the whole chain is exercisable.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.db import get_db
from core.deps import get_current_user_id, get_llm_provider
from repositories.application import JobPostingRepository
from schemas.resume import GenerateResumeRequest, GenerateResumeResponse
from services import tailoring
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
        result = tailoring.generate(profile, posting, provider)
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

    return GenerateResumeResponse(
        resume=result.resume,
        rationale=result.rationale,
        provider=provider.name,
        model=getattr(provider, "model", ""),
        prompt_version=tailoring.PROMPT_VERSION,
        attempts=result.attempts,
    )
