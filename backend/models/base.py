import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every model. Alembic autogenerate reads Base.metadata."""


class UUIDPrimaryKey:
    """UUID primary key, generated client-side.

    UUIDs throughout rather than serial ints: job posting IDs are handed to the
    browser before the user has committed to anything, and an opaque identifier
    avoids leaking row counts or letting one user's URL guess at another's row.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
