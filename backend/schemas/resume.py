"""Resume generation schemas.

Two distinct shapes live here, and the split is the point.

`Tailored*` is what the **model** is constrained to return. It contains no company,
title, school, degree or date — only short reference labels naming which profile entries
to include, plus rewritten bullet text. The model literally cannot fabricate an employer
in this schema, because there is no field to put one in.

`Resume*` is what the **server assembles** afterwards, filling every factual field from
the profile rows the labels resolved to. So the facts on the finished resume come from
the database by construction, and the guardrails only have to police the free text that
is left: bullets, the summary, and the rationale.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

# --- what the model returns -------------------------------------------------


class TailoredBullet(BaseModel):
    source: str = Field(
        description="Label of the bullet this was rewritten from, e.g. E1B2"
    )
    text: str = Field(description="The rewritten bullet")


class TailoredExperience(BaseModel):
    source: str = Field(description="Label of the experience, e.g. E1")
    bullets: list[TailoredBullet] = []


class TailoredResume(BaseModel):
    """Labels rather than UUIDs on purpose.

    Models copy short tokens like `E1B2` reliably and 36-character hex strings
    unreliably, and a mis-copied UUID would surface as an unresolvable reference —
    reading as fabrication when it was really a transcription slip.
    """

    rationale: str = Field(
        description=(
            "Which of the candidate's experience overlaps the posting's requirements, "
            "and why these bullets were chosen. Written before the resume itself."
        )
    )
    summary: str = Field(description="A short professional summary for this posting")
    experiences: list[TailoredExperience] = []
    skills: list[str] = Field(
        default=[], description="Skills to feature, copied exactly from the profile"
    )


# --- what the server assembles ----------------------------------------------


class ResumeExperience(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: date
    end_date: date | None = None
    bullets: list[str] = []


class ResumeEducation(BaseModel):
    school: str
    degree: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ResumeLink(BaseModel):
    label: str
    url: str


class Resume(BaseModel):
    """The finished resume. Every factual field came from the profile, not the model."""

    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    summary: str
    experiences: list[ResumeExperience] = []
    education: list[ResumeEducation] = []
    skills: list[str] = []
    links: list[ResumeLink] = []


class GenerateResumeRequest(BaseModel):
    job_posting_id: uuid.UUID


class GenerateResumeResponse(BaseModel):
    resume: Resume
    # Surfaced on the Apply page as "why these bullets".
    rationale: str
    provider: str
    model: str
    prompt_version: str
    attempts: int
