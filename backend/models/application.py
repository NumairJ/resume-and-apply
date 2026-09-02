"""Extracted job postings, the applications that track them, and generated resumes."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, Timestamps, UUIDPrimaryKey
from models.enums import ApplicationStatus, ExtractionMethod
from models.profile import User


class JobPosting(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "job_postings"

    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(200))
    employment_type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    # Kept as free text: postings state compensation in wildly inconsistent forms and
    # nothing in this project does arithmetic on it.
    salary_range: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(2000))
    raw_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(
            ExtractionMethod,
            name="extraction_method",
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    # Normalized company + title + location, hashed. Indexed but deliberately NOT
    # unique: duplicate detection is a soft warning, and a false positive on a unique
    # constraint would block a legitimate reapplication after a rejection.
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    # NULL means permanent. A freshly extracted posting expires in 24h so abandoned
    # rows clean themselves up; saving an application clears this.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    applications: Mapped[list["Application"]] = relationship(
        back_populates="job_posting"
    )


class Application(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "applications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT rather than CASCADE: a tracked application is the thing that makes its
    # posting permanent, so deleting the posting out from under it should be an error.
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ApplicationStatus.SAVED,
    )
    applied_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship()
    job_posting: Mapped[JobPosting] = relationship(back_populates="applications")
    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="Resume.created_at",
    )


class Resume(UUIDPrimaryKey, Timestamps, Base):
    """A generated resume. The PDF lives on disk; only its path and hash live here.

    Storing bytes in Postgres would bloat the database and make backups painful for
    no gain — the path plus a content hash gives the same integrity guarantee.

    Not unique per application: regenerating is an explicit feature, and keeping the
    earlier attempts costs nothing.
    """

    __tablename__ = "resumes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    # Recorded so a resume can be reproduced later against the same prompt text.
    prompt_version: Mapped[str] = mapped_column(String(50))

    application: Mapped[Application] = relationship(back_populates="resumes")
