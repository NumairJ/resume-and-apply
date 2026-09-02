"""Profile CRUD.

Note the paths: nothing here is namespaced under `/api`. The Next.js rewrite strips
that prefix, so the browser's `/api/profile/skills` arrives as `/profile/skills`.

Every route is written out explicitly rather than generated from a factory. Four of
these collections are byte-identical, so a factory would be shorter — but this file is
meant to be openable by someone who has never seen the repo, and a list of endpoints
reads better than a thing that manufactures endpoints.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.db import get_db
from core.deps import get_current_user_id
from models.profile import Experience, ExperienceBullet
from repositories.profile import (
    EducationRepository,
    ExperienceBulletRepository,
    ExperienceRepository,
    LinkRepository,
    ProjectRepository,
    SkillRepository,
    UserRepository,
)
from schemas.profile import (
    EducationCreate,
    EducationRead,
    EducationUpdate,
    ExperienceBulletCreate,
    ExperienceBulletRead,
    ExperienceBulletUpdate,
    ExperienceCreate,
    ExperienceRead,
    ExperienceUpdate,
    LinkCreate,
    LinkRead,
    LinkUpdate,
    Profile,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ReorderRequest,
    SkillCreate,
    SkillRead,
    SkillUpdate,
    UserRead,
    UserUpdate,
    ensure_chronological,
)
from services import profile as profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


# --- helpers ----------------------------------------------------------------


def _get_owned(repo: Any, item_id: uuid.UUID, user_id: uuid.UUID) -> Any:
    """Fetch a row, or 404 if it is missing *or* belongs to someone else.

    404 rather than 403 on the ownership failure: a 403 would confirm the row exists.
    """
    item = repo.get(item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return item


def _merged_dates(payload: Any, item: Any) -> None:
    """Re-check chronology against the stored row before a partial update.

    The schema validator only sees what the request sent. A PATCH carrying just
    `end_date` needs the stored `start_date` to be checkable, which is only available
    here. Same rule, applied where the full picture exists.
    """
    data = payload.model_dump(exclude_unset=True)
    try:
        ensure_chronological(
            data.get("start_date", item.start_date),
            data.get("end_date", item.end_date),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


def _get_experience(
    session: Session, experience_id: uuid.UUID, user_id: uuid.UUID
) -> Experience:
    return _get_owned(ExperienceRepository(session), experience_id, user_id)


def _get_bullet(
    session: Session,
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ExperienceBullet:
    """Resolve a bullet through its experience, so ownership is checked on the way."""
    _get_experience(session, experience_id, user_id)
    repo = ExperienceBulletRepository(session)
    bullet = repo.get(bullet_id)
    if bullet is None or bullet.experience_id != experience_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return bullet


# --- personal info ----------------------------------------------------------


@router.get("", response_model=Profile)
def read_profile(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Profile:
    profile = profile_service.get_profile(session, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


@router.patch("", response_model=UserRead)
def update_personal_info(
    payload: UserUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    repo = UserRepository(session)
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    repo.update(user, **payload.model_dump(exclude_unset=True))
    session.commit()
    return user


# --- education --------------------------------------------------------------


@router.get("/education", response_model=list[EducationRead])
def list_education(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    return EducationRepository(session).list_for_user(user_id)


@router.post(
    "/education", response_model=EducationRead, status_code=status.HTTP_201_CREATED
)
def create_education(
    payload: EducationCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    item = EducationRepository(session).create(user_id=user_id, **payload.model_dump())
    session.commit()
    return item


@router.put("/education/order", response_model=list[EducationRead])
def reorder_education(
    payload: ReorderRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    items = EducationRepository(session).reorder(user_id, payload.ids)
    session.commit()
    return items


@router.patch("/education/{item_id}", response_model=EducationRead)
def update_education(
    item_id: uuid.UUID,
    payload: EducationUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    repo = EducationRepository(session)
    item = _get_owned(repo, item_id, user_id)
    _merged_dates(payload, item)
    repo.update(item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return item


@router.delete("/education/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    item_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    repo = EducationRepository(session)
    repo.delete(_get_owned(repo, item_id, user_id))
    session.commit()


# --- experiences ------------------------------------------------------------


@router.get("/experiences", response_model=list[ExperienceRead])
def list_experiences(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    return ExperienceRepository(session).list_for_user(user_id)


@router.post(
    "/experiences", response_model=ExperienceRead, status_code=status.HTTP_201_CREATED
)
def create_experience(
    payload: ExperienceCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    """Create an experience and, optionally, its bullets in one transaction."""
    data = payload.model_dump()
    bullets = data.pop("bullets")
    experience = ExperienceRepository(session).create(user_id=user_id, **data)

    bullet_repo = ExperienceBulletRepository(session)
    for index, bullet in enumerate(bullets):
        # Fall back to request order when the caller didn't set positions itself.
        bullet.setdefault("position", index)
        bullet_repo.create(experience_id=experience.id, **bullet)

    session.commit()
    session.refresh(experience)
    return experience


@router.put("/experiences/order", response_model=list[ExperienceRead])
def reorder_experiences(
    payload: ReorderRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    items = ExperienceRepository(session).reorder(user_id, payload.ids)
    session.commit()
    return items


@router.patch("/experiences/{item_id}", response_model=ExperienceRead)
def update_experience(
    item_id: uuid.UUID,
    payload: ExperienceUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    repo = ExperienceRepository(session)
    item = _get_owned(repo, item_id, user_id)
    _merged_dates(payload, item)
    repo.update(item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return item


@router.delete("/experiences/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    item_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    repo = ExperienceRepository(session)
    repo.delete(_get_owned(repo, item_id, user_id))
    session.commit()


# --- experience bullets -----------------------------------------------------


@router.post(
    "/experiences/{experience_id}/bullets",
    response_model=ExperienceBulletRead,
    status_code=status.HTTP_201_CREATED,
)
def create_bullet(
    experience_id: uuid.UUID,
    payload: ExperienceBulletCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    _get_experience(session, experience_id, user_id)
    bullet = ExperienceBulletRepository(session).create(
        experience_id=experience_id, **payload.model_dump()
    )
    session.commit()
    return bullet


@router.put(
    "/experiences/{experience_id}/bullets/order",
    response_model=list[ExperienceBulletRead],
)
def reorder_bullets(
    experience_id: uuid.UUID,
    payload: ReorderRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    _get_experience(session, experience_id, user_id)
    bullets = ExperienceBulletRepository(session).reorder(experience_id, payload.ids)
    session.commit()
    return bullets


@router.patch(
    "/experiences/{experience_id}/bullets/{bullet_id}",
    response_model=ExperienceBulletRead,
)
def update_bullet(
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
    payload: ExperienceBulletUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    bullet = _get_bullet(session, experience_id, bullet_id, user_id)
    ExperienceBulletRepository(session).update(
        bullet, **payload.model_dump(exclude_unset=True)
    )
    session.commit()
    return bullet


@router.delete(
    "/experiences/{experience_id}/bullets/{bullet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_bullet(
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    bullet = _get_bullet(session, experience_id, bullet_id, user_id)
    ExperienceBulletRepository(session).delete(bullet)
    session.commit()


# --- skills -----------------------------------------------------------------


@router.get("/skills", response_model=list[SkillRead])
def list_skills(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    return SkillRepository(session).list_for_user(user_id)


@router.post("/skills", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: SkillCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    item = SkillRepository(session).create(user_id=user_id, **payload.model_dump())
    session.commit()
    return item


@router.put("/skills/order", response_model=list[SkillRead])
def reorder_skills(
    payload: ReorderRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    items = SkillRepository(session).reorder(user_id, payload.ids)
    session.commit()
    return items


@router.patch("/skills/{item_id}", response_model=SkillRead)
def update_skill(
    item_id: uuid.UUID,
    payload: SkillUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    repo = SkillRepository(session)
    item = _get_owned(repo, item_id, user_id)
    repo.update(item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return item


@router.delete("/skills/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    item_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    repo = SkillRepository(session)
    repo.delete(_get_owned(repo, item_id, user_id))
    session.commit()


# --- projects ---------------------------------------------------------------


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    return ProjectRepository(session).list_for_user(user_id)


@router.post(
    "/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED
)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    item = ProjectRepository(session).create(user_id=user_id, **payload.model_dump())
    session.commit()
    return item


@router.put("/projects/order", response_model=list[ProjectRead])
def reorder_projects(
    payload: ReorderRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    items = ProjectRepository(session).reorder(user_id, payload.ids)
    session.commit()
    return items


@router.patch("/projects/{item_id}", response_model=ProjectRead)
def update_project(
    item_id: uuid.UUID,
    payload: ProjectUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    repo = ProjectRepository(session)
    item = _get_owned(repo, item_id, user_id)
    _merged_dates(payload, item)
    repo.update(item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return item


@router.delete("/projects/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    item_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    repo = ProjectRepository(session)
    repo.delete(_get_owned(repo, item_id, user_id))
    session.commit()


# --- links ------------------------------------------------------------------


@router.get("/links", response_model=list[LinkRead])
def list_links(
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    return LinkRepository(session).list_for_user(user_id)


@router.post("/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: LinkCreate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    item = LinkRepository(session).create(user_id=user_id, **payload.model_dump())
    session.commit()
    return item


@router.put("/links/order", response_model=list[LinkRead])
def reorder_links(
    payload: ReorderRequest,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    items = LinkRepository(session).reorder(user_id, payload.ids)
    session.commit()
    return items


@router.patch("/links/{item_id}", response_model=LinkRead)
def update_link(
    item_id: uuid.UUID,
    payload: LinkUpdate,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Any:
    repo = LinkRepository(session)
    item = _get_owned(repo, item_id, user_id)
    repo.update(item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return item


@router.delete("/links/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    item_id: uuid.UUID,
    session: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    repo = LinkRepository(session)
    repo.delete(_get_owned(repo, item_id, user_id))
    session.commit()
