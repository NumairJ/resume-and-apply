"""Model re-exports.

Alembic autogenerate only sees tables whose modules have been imported, and
alembic/env.py imports this package for exactly that reason. A new model must be
re-exported here or migrations will silently miss it.
"""

from models.application import Application, JobPosting, Resume
from models.base import Base
from models.enums import ApplicationStatus, ExtractionMethod
from models.profile import (
    Education,
    Experience,
    ExperienceBullet,
    Link,
    Project,
    Skill,
    User,
)

__all__ = [
    "Application",
    "ApplicationStatus",
    "Base",
    "Education",
    "Experience",
    "ExperienceBullet",
    "ExtractionMethod",
    "JobPosting",
    "Link",
    "Project",
    "Resume",
    "Skill",
    "User",
]
