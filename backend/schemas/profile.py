"""Request/response schemas for the profile side.

Each resource follows the same shape: a `Base` holding the writable fields, a `Create`
that adds nothing, an `Update` with every field optional so PATCH can be partial
(apply with `model_dump(exclude_unset=True)`), and a `Read` that adds the id.
"""

import uuid
from datetime import date

from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def ensure_chronological(start: date | None, end: date | None) -> None:
    """Reject a date range that ends before it starts.

    Applied at write time so the profile can never hold something that is guaranteed
    to fail Phase 4's chronology guardrail. Catching it later would surface as a
    generation error, pointing at the wrong culprit.
    """
    if start and end and end < start:
        raise ValueError("end_date must not precede start_date")


class ChronologyCheck:
    """Mixin applying `ensure_chronological` to a schema's own two date fields.

    This covers every create, and any partial update that happens to carry both
    dates. An update sending only one of them cannot be checked here — the schema
    can't see the stored value — so the PATCH routes re-check the merged result.
    """

    @model_validator(mode="after")
    def _validate_dates(self) -> Self:
        ensure_chronological(self.start_date, self.end_date)
        return self


# --- User -------------------------------------------------------------------


class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    summary: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None


class UserRead(ORMModel, UserBase):
    id: uuid.UUID


# --- Education --------------------------------------------------------------


class EducationBase(ChronologyCheck, BaseModel):
    school: str
    degree: str
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    position: int = 0


class EducationCreate(EducationBase):
    pass


class EducationUpdate(BaseModel):
    school: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    position: int | None = None


class EducationRead(ORMModel, EducationBase):
    id: uuid.UUID


# --- Experience bullets -----------------------------------------------------


class ExperienceBulletBase(BaseModel):
    text: str
    position: int = 0


class ExperienceBulletCreate(ExperienceBulletBase):
    pass


class ExperienceBulletUpdate(BaseModel):
    text: str | None = None
    position: int | None = None


class ExperienceBulletRead(ORMModel, ExperienceBulletBase):
    id: uuid.UUID


# --- Experience -------------------------------------------------------------


class ExperienceBase(ChronologyCheck, BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: date
    end_date: date | None = None
    position: int = 0


class ExperienceCreate(ExperienceBase):
    bullets: list[ExperienceBulletCreate] = []


class ExperienceUpdate(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    position: int | None = None


class ExperienceRead(ORMModel, ExperienceBase):
    id: uuid.UUID
    bullets: list[ExperienceBulletRead] = []


# --- Skill ------------------------------------------------------------------


class SkillBase(BaseModel):
    name: str
    category: str | None = None
    position: int = 0


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    position: int | None = None


class SkillRead(ORMModel, SkillBase):
    id: uuid.UUID


# --- Project bullets --------------------------------------------------------


class ProjectBulletBase(BaseModel):
    text: str
    position: int = 0


class ProjectBulletCreate(ProjectBulletBase):
    pass


class ProjectBulletUpdate(BaseModel):
    text: str | None = None
    position: int | None = None


class ProjectBulletRead(ORMModel, ProjectBulletBase):
    id: uuid.UUID


# --- Project ----------------------------------------------------------------


class ProjectBase(ChronologyCheck, BaseModel):
    name: str
    tech_stack: str | None = None
    url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    position: int = 0


class ProjectCreate(ProjectBase):
    bullets: list[ProjectBulletCreate] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    tech_stack: str | None = None
    url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    position: int | None = None


class ProjectRead(ORMModel, ProjectBase):
    id: uuid.UUID
    bullets: list[ProjectBulletRead] = []


# --- Link -------------------------------------------------------------------


class LinkBase(BaseModel):
    label: str
    url: str
    position: int = 0


class LinkCreate(LinkBase):
    pass


class LinkUpdate(BaseModel):
    label: str | None = None
    url: str | None = None
    position: int | None = None


class LinkRead(ORMModel, LinkBase):
    id: uuid.UUID


# --- Assembled profile ------------------------------------------------------


class Profile(ORMModel):
    """The whole profile in one object.

    Both the tailoring prompt and the guardrail chain consume this, so there is one
    definition of "the user's data" rather than two that drift apart.
    """

    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    education: list[EducationRead] = []
    experiences: list[ExperienceRead] = []
    skills: list[SkillRead] = []
    projects: list[ProjectRead] = []
    links: list[LinkRead] = []


class ReorderRequest(BaseModel):
    """Reorder a collection by sending its ids in the desired order.

    One request rewriting every position beats per-item position updates, which race
    each other and don't match how a drag-and-drop UI actually behaves.
    """

    ids: list[uuid.UUID]
