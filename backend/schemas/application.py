"""Request/response schemas for job postings, applications and generated resumes."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from models.enums import ApplicationStatus, ExtractionMethod


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Job postings -----------------------------------------------------------


class JobPostingBase(BaseModel):
    company: str
    title: str
    location: str | None = None
    employment_type: str | None = None
    description: str | None = None
    requirements: str | None = None
    salary_range: str | None = None


class JobPostingCreate(JobPostingBase):
    """Built by the extraction pipeline, not accepted from the browser."""

    source_url: str
    raw_text: str | None = None
    extraction_method: ExtractionMethod


class JobPostingUpdate(BaseModel):
    """User corrections to a mis-parsed posting, before it becomes a resume.

    Only the human-meaningful fields are editable — source_url, extraction_method and
    the fingerprint are records of how the row came to exist, not user content.
    """

    company: str | None = None
    title: str | None = None
    location: str | None = None
    employment_type: str | None = None
    description: str | None = None
    requirements: str | None = None
    salary_range: str | None = None


class JobPostingRead(ORMModel, JobPostingBase):
    id: uuid.UUID
    source_url: str
    extraction_method: ExtractionMethod
    expires_at: datetime | None = None
    created_at: datetime


# --- Applications -----------------------------------------------------------


class ApplicationCreate(BaseModel):
    job_posting_id: uuid.UUID
    status: ApplicationStatus = ApplicationStatus.SAVED
    applied_at: date | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    applied_at: date | None = None
    notes: str | None = None


class ResumeRead(ORMModel):
    id: uuid.UUID
    application_id: uuid.UUID
    file_path: str
    content_hash: str
    provider: str
    model: str
    prompt_version: str
    created_at: datetime


class ApplicationRead(ORMModel):
    id: uuid.UUID
    status: ApplicationStatus
    applied_at: date | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    job_posting: JobPostingRead
    resumes: list[ResumeRead] = []
