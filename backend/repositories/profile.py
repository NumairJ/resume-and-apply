import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.profile import (
    Education,
    Experience,
    ExperienceBullet,
    Link,
    Project,
    Skill,
    User,
)
from repositories.base import BaseRepository, ModelT


class UserRepository(BaseRepository[User]):
    model = User


class _OwnedRepository(BaseRepository[ModelT]):
    """Base for the profile collections, which all hang off a user and are ordered."""

    def list_for_user(self, user_id: uuid.UUID) -> list[ModelT]:
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.position)
        )
        return list(self.session.scalars(stmt))

    def reorder(self, user_id: uuid.UUID, ids: list[uuid.UUID]) -> list[ModelT]:
        """Rewrite `position` to match the given order, in one transaction.

        Ids not belonging to this user are ignored rather than raising — the caller
        is reordering a list it just read, and a stale id is not worth a 500.
        """
        items = {item.id: item for item in self.list_for_user(user_id)}
        for index, item_id in enumerate(ids):
            if item := items.get(item_id):
                item.position = index
        self.session.flush()
        return self.list_for_user(user_id)


class EducationRepository(_OwnedRepository[Education]):
    model = Education


class ExperienceRepository(_OwnedRepository[Experience]):
    model = Experience


class SkillRepository(_OwnedRepository[Skill]):
    model = Skill


class ProjectRepository(_OwnedRepository[Project]):
    model = Project


class LinkRepository(_OwnedRepository[Link]):
    model = Link


class ExperienceBulletRepository(BaseRepository[ExperienceBullet]):
    """Bullets hang off an experience rather than a user, so ordering is per-experience."""

    model = ExperienceBullet

    def list_for_experience(self, experience_id: uuid.UUID) -> list[ExperienceBullet]:
        stmt = (
            select(ExperienceBullet)
            .where(ExperienceBullet.experience_id == experience_id)
            .order_by(ExperienceBullet.position)
        )
        return list(self.session.scalars(stmt))

    def reorder(
        self, experience_id: uuid.UUID, ids: list[uuid.UUID]
    ) -> list[ExperienceBullet]:
        bullets = {b.id: b for b in self.list_for_experience(experience_id)}
        for index, bullet_id in enumerate(ids):
            if bullet := bullets.get(bullet_id):
                bullet.position = index
        self.session.flush()
        return self.list_for_experience(experience_id)


def get_profile(session: Session, user_id: uuid.UUID) -> User | None:
    """The user with every collection loaded — the object prompts and guardrails read."""
    return session.get(User, user_id)
