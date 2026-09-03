"""Generation as a persisted operation: tailor, attach, render, record."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from models.application import JobPosting, Resume
from repositories.application import ResumeRepository
from schemas.profile import Profile
from services import applications, render, tailoring
from services.llm.base import LLMProvider


@dataclass
class GeneratedResume:
    row: Resume
    result: tailoring.TailoringResult


def generate(
    session: Session,
    profile: Profile,
    posting: JobPosting,
    user_id: uuid.UUID,
    provider: LLMProvider,
) -> GeneratedResume:
    """Produce a resume and everything that has to exist alongside it.

    Tailoring runs *first*, so a generation that the guardrails reject leaves no
    application behind and does not silently make the job posting permanent.

    The application is found-or-created rather than optional because `resumes` requires
    a parent: giving every PDF an owner is what lets deleting an application clean up
    both the rows and the files, instead of stranding artifacts on the volume with
    nothing left to sweep them.
    """
    result = tailoring.generate(profile, posting, provider)
    application = applications.find_or_create(session, user_id, posting)

    # Allocated up front so the files and the row's primary key are the same value.
    resume_id = uuid.uuid4()
    rendered = render.render(result.resume, resume_id)

    row = ResumeRepository(session).create(
        id=resume_id,
        application_id=application.id,
        file_path=str(rendered.pdf_path),
        content_hash=rendered.content_hash,
        provider=provider.name,
        model=getattr(provider, "model", ""),
        prompt_version=tailoring.PROMPT_VERSION,
    )
    return GeneratedResume(row=row, result=result)
