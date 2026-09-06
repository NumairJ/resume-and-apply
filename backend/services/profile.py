import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.profile import Experience, Project, User
from schemas.profile import Profile


def get_profile(session: Session, user_id: uuid.UUID) -> Profile | None:
    """The user's whole profile as one object, or None if there is no such user.

    Every collection is eager-loaded in one go. Beyond avoiding an N+1, this is what
    makes the result safe to use away from the session: Phase 4's guardrail chain and
    the tailoring prompt both consume this outside any request, where a lazy-loading
    ORM instance would either re-query or raise depending on session state.

    Returns the Pydantic model rather than the ORM `User` for the same reason, and
    returns None rather than raising an HTTP error — the router owns HTTP concerns,
    and the guardrails will call this with no request in scope.
    """
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.education),
            selectinload(User.experiences).selectinload(Experience.bullets),
            selectinload(User.skills),
            selectinload(User.projects).selectinload(Project.bullets),
            selectinload(User.links),
        )
    )
    user = session.scalars(stmt).first()
    return Profile.model_validate(user) if user else None
