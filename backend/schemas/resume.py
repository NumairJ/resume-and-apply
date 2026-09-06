"""Resume generation schemas.

Two distinct shapes live here, and the split is the point.

`Tailored*` is what the **model** is constrained to return. It contains no company,
title, school, degree or date — only short reference labels naming which profile entries
to include, plus rewritten bullet text. The model literally cannot fabricate an employer
in this schema, because there is no field to put one in.

`Resume*` is what the **server assembles** afterwards, filling every factual field from
the profile rows the labels resolved to. So the facts on the finished resume come from
the database by construction, and the guardrails only have to police the free text that
is left: the bullets and the summary.
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


class TailoredProject(BaseModel):
    """A project selected by label, with its own bullets rewritten for the posting.

    Note what is *not* here: no name, no URL, no technology list. Those are filled from
    the project row, which is why a résumé cannot claim a project or a stack the user
    never recorded.
    """

    source: str = Field(description="Label of the project, e.g. P1")
    bullets: list[TailoredBullet] = []


class TailoredResume(BaseModel):
    """Labels rather than UUIDs on purpose.

    Models copy short tokens like `E1B2` reliably and 36-character hex strings
    unreliably, and a mis-copied UUID would surface as an unresolvable reference —
    reading as fabrication when it was really a transcription slip.
    """

    # There is no `rationale` field, and its absence is deliberate. It once asked for
    # three to five sentences explaining the selection, on every attempt including every
    # retry, as a "reason before you answer" scaffold. The provider runs with adaptive
    # thinking, so the model reasons regardless, and the retry loop already tells it
    # exactly what a rejected draft got wrong. It was output tokens spent on prose that
    # was never printed on the resume.
    summary: str = Field(description="A short professional summary for this posting")
    experiences: list[TailoredExperience] = []
    projects: list[TailoredProject] = []
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


class ResumeProject(BaseModel):
    name: str
    url: str | None = None
    # Copied from the profile row verbatim. The model is shown it but has no field in
    # which to return it, so a stack cannot be paraphrased into tools nobody uses.
    tech_stack: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    bullets: list[str] = []


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
    projects: list[ResumeProject] = []
    education: list[ResumeEducation] = []
    skills: list[str] = []
    links: list[ResumeLink] = []


class GenerateResumeRequest(BaseModel):
    job_posting_id: uuid.UUID


class GenerateResumeResponse(BaseModel):
    # The generation is persisted, so these two identify what was written: the PDF to
    # preview or download, and the application it now belongs to.
    resume_id: uuid.UUID
    application_id: uuid.UUID
    resume: Resume
    provider: str
    model: str
    prompt_version: str
    attempts: int
