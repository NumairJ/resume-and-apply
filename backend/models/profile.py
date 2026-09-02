"""The user's own data — the set the guardrails validate generated resumes against.

Every company, title, school, degree and date that may appear in a generated resume
has to exist somewhere in these tables. That is what makes the anti-fabrication check
a set-membership test rather than a judgement call.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)

    education: Mapped[list["Education"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Education.position",
    )
    experiences: Mapped[list["Experience"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Experience.position",
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Skill.position",
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Project.position",
    )
    links: Mapped[list["Link"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Link.position",
    )


class Education(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "education"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    school: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str] = mapped_column(String(200))
    field_of_study: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    # NULL end_date means in progress.
    end_date: Mapped[date | None] = mapped_column(Date)
    gpa: Mapped[str | None] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="education")


class Experience(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "experiences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    # NULL end_date means current role.
    end_date: Mapped[date | None] = mapped_column(Date)
    position: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="experiences")
    bullets: Mapped[list["ExperienceBullet"]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="ExperienceBullet.position",
    )


class ExperienceBullet(UUIDPrimaryKey, Timestamps, Base):
    """One accomplishment line, stored individually rather than as prose.

    This table is load-bearing for the whole project: because bullets are rows, the
    LLM selects and rephrases from a pool of real accomplishments instead of writing
    free-form paragraphs, and every generated bullet can be traced back to the source
    row it came from.
    """

    __tablename__ = "experience_bullets"

    experience_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(default=0)

    experience: Mapped[Experience] = relationship(back_populates="bullets")


class Skill(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "skills"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="skills")


class Project(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    position: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="projects")


class Link(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "links"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="links")
