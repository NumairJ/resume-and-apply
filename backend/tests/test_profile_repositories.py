"""Round-trip tests for the profile repositories."""

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from models.profile import User
from repositories.profile import (
    EducationRepository,
    ExperienceBulletRepository,
    ExperienceRepository,
    LinkRepository,
    ProjectRepository,
    SkillRepository,
    UserRepository,
)


def test_user_round_trip(session: Session, user: User) -> None:
    repo = UserRepository(session)

    fetched = repo.get(user.id)
    assert fetched is not None
    assert fetched.email == "test@example.com"

    repo.update(fetched, full_name="Renamed", location="Toronto")
    assert repo.get(user.id).full_name == "Renamed"

    repo.delete(fetched)
    assert repo.get(user.id) is None


# Each entry is (repository, required fields, a field to update and its new value).
OWNED_REPOSITORIES = [
    pytest.param(
        EducationRepository,
        {"school": "State University", "degree": "BSc"},
        ("degree", "MSc"),
        id="education",
    ),
    pytest.param(
        ExperienceRepository,
        {"company": "Acme", "title": "Engineer", "start_date": date(2020, 1, 1)},
        ("title", "Senior Engineer"),
        id="experience",
    ),
    pytest.param(
        SkillRepository,
        {"name": "Python", "category": "Languages"},
        ("category", "Backend"),
        id="skill",
    ),
    pytest.param(
        ProjectRepository,
        {"name": "Portfolio site"},
        ("name", "Personal site"),
        id="project",
    ),
    pytest.param(
        LinkRepository,
        {"label": "GitHub", "url": "https://github.com/example"},
        ("url", "https://github.com/renamed"),
        id="link",
    ),
]


@pytest.mark.parametrize("repo_class, fields, update", OWNED_REPOSITORIES)
def test_owned_repository_round_trip(
    session: Session,
    user: User,
    repo_class: type,
    fields: dict,
    update: tuple[str, str],
) -> None:
    repo = repo_class(session)

    created = repo.create(user_id=user.id, **fields)
    assert created.id is not None
    assert repo.get(created.id) is not None

    field, new_value = update
    repo.update(created, **{field: new_value})
    assert getattr(repo.get(created.id), field) == new_value

    repo.delete(created)
    assert repo.get(created.id) is None


@pytest.mark.parametrize("repo_class, fields, _update", OWNED_REPOSITORIES)
def test_list_for_user_filters_by_owner(
    session: Session,
    user: User,
    other_user: User,
    repo_class: type,
    fields: dict,
    _update: tuple[str, str],
) -> None:
    repo = repo_class(session)
    mine = repo.create(user_id=user.id, **fields)
    repo.create(user_id=other_user.id, **fields)

    assert [item.id for item in repo.list_for_user(user.id)] == [mine.id]


@pytest.mark.parametrize("repo_class, fields, _update", OWNED_REPOSITORIES)
def test_reorder_rewrites_positions(
    session: Session,
    user: User,
    repo_class: type,
    fields: dict,
    _update: tuple[str, str],
) -> None:
    repo = repo_class(session)
    first = repo.create(user_id=user.id, position=0, **fields)
    second = repo.create(user_id=user.id, position=1, **fields)
    third = repo.create(user_id=user.id, position=2, **fields)

    reordered = repo.reorder(user.id, [third.id, first.id, second.id])

    assert [item.id for item in reordered] == [third.id, first.id, second.id]
    assert [item.position for item in reordered] == [0, 1, 2]


def test_reorder_ignores_unknown_ids(session: Session, user: User) -> None:
    repo = SkillRepository(session)
    first = repo.create(user_id=user.id, name="Python", position=0)
    second = repo.create(user_id=user.id, name="SQL", position=1)

    reordered = repo.reorder(user.id, [second.id, uuid.uuid4(), first.id])

    assert [item.id for item in reordered] == [second.id, first.id]


def test_bullets_come_back_in_position_order(session: Session, user: User) -> None:
    """The ordering guarantee tailoring depends on — bullets are a sequence, not a set."""
    experiences = ExperienceRepository(session)
    bullets = ExperienceBulletRepository(session)

    experience = experiences.create(
        user_id=user.id,
        company="Acme",
        title="Engineer",
        start_date=date(2020, 1, 1),
    )
    # Deliberately inserted out of order.
    bullets.create(experience_id=experience.id, text="third", position=2)
    bullets.create(experience_id=experience.id, text="first", position=0)
    bullets.create(experience_id=experience.id, text="second", position=1)

    listed = bullets.list_for_experience(experience.id)
    assert [b.text for b in listed] == ["first", "second", "third"]

    session.refresh(experience)
    assert [b.text for b in experience.bullets] == ["first", "second", "third"]


def test_bullet_round_trip_and_reorder(session: Session, user: User) -> None:
    experiences = ExperienceRepository(session)
    bullets = ExperienceBulletRepository(session)

    experience = experiences.create(
        user_id=user.id,
        company="Acme",
        title="Engineer",
        start_date=date(2020, 1, 1),
    )
    one = bullets.create(experience_id=experience.id, text="one", position=0)
    two = bullets.create(experience_id=experience.id, text="two", position=1)

    bullets.update(one, text="one, rewritten")
    assert bullets.get(one.id).text == "one, rewritten"

    reordered = bullets.reorder(experience.id, [two.id, one.id])
    assert [b.text for b in reordered] == ["two", "one, rewritten"]

    bullets.delete(two)
    assert [b.id for b in bullets.list_for_experience(experience.id)] == [one.id]


def test_deleting_experience_cascades_to_bullets(
    session: Session, user: User
) -> None:
    experiences = ExperienceRepository(session)
    bullets = ExperienceBulletRepository(session)

    experience = experiences.create(
        user_id=user.id,
        company="Acme",
        title="Engineer",
        start_date=date(2020, 1, 1),
    )
    bullets.create(experience_id=experience.id, text="a bullet", position=0)

    experiences.delete(experience)

    assert bullets.list_for_experience(experience.id) == []
