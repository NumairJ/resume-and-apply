"""Route tests for the profile API.

The routes are written out explicitly, but their behaviour is uniform across the four
identical collections, so the CRUD and reorder tests are parametrized. Experiences,
bullets and personal info get explicit tests because they genuinely differ.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.profile import Education, Link, Project, Skill, User

# (url path, create payload, patch payload, field to assert the patch landed on)
COLLECTIONS = [
    pytest.param(
        "education",
        {"school": "State University", "degree": "BSc"},
        {"degree": "MSc"},
        "degree",
        id="education",
    ),
    pytest.param(
        "skills",
        {"name": "Python", "category": "Languages"},
        {"category": "Backend"},
        "category",
        id="skills",
    ),
    pytest.param(
        "projects",
        {"name": "Portfolio site"},
        {"name": "Personal site"},
        "name",
        id="projects",
    ),
    pytest.param(
        "links",
        {"label": "GitHub", "url": "https://github.com/example"},
        {"url": "https://github.com/renamed"},
        "url",
        id="links",
    ),
]


@pytest.mark.parametrize("path, create, patch, field", COLLECTIONS)
def test_collection_crud(
    client: TestClient, path: str, create: dict, patch: dict, field: str
) -> None:
    assert client.get(f"/profile/{path}").json() == []

    created = client.post(f"/profile/{path}", json=create)
    assert created.status_code == 201
    item_id = created.json()["id"]

    listed = client.get(f"/profile/{path}").json()
    assert [item["id"] for item in listed] == [item_id]

    updated = client.patch(f"/profile/{path}/{item_id}", json=patch)
    assert updated.status_code == 200
    assert updated.json()[field] == patch[field]

    assert client.delete(f"/profile/{path}/{item_id}").status_code == 204
    assert client.get(f"/profile/{path}").json() == []


@pytest.mark.parametrize("path, create, _patch, _field", COLLECTIONS)
def test_collection_reorder(
    client: TestClient, path: str, create: dict, _patch: dict, _field: str
) -> None:
    ids = [
        client.post(f"/profile/{path}", json={**create, "position": index}).json()["id"]
        for index in range(3)
    ]
    shuffled = [ids[2], ids[0], ids[1]]

    reordered = client.put(f"/profile/{path}/order", json={"ids": shuffled})
    assert reordered.status_code == 200
    assert [item["id"] for item in reordered.json()] == shuffled
    assert [item["position"] for item in reordered.json()] == [0, 1, 2]

    # The new order has to survive a fresh read, not just come back from the write.
    assert [item["id"] for item in client.get(f"/profile/{path}").json()] == shuffled


@pytest.mark.parametrize("path, create, patch, _field", COLLECTIONS)
def test_another_users_row_is_not_reachable(
    client: TestClient,
    session: Session,
    other_user: User,
    path: str,
    create: dict,
    patch: dict,
    _field: str,
) -> None:
    """404, not 403 — a 403 would confirm the row exists."""
    model = {
        "education": Education,
        "skills": Skill,
        "projects": Project,
        "links": Link,
    }[path]
    theirs = model(user_id=other_user.id, **create)
    session.add(theirs)
    session.flush()

    assert client.patch(f"/profile/{path}/{theirs.id}", json=patch).status_code == 404
    assert client.delete(f"/profile/{path}/{theirs.id}").status_code == 404
    # And it must not leak into this user's list either.
    assert client.get(f"/profile/{path}").json() == []


@pytest.mark.parametrize("path", ["education", "skills", "projects", "links"])
def test_unknown_id_is_404(client: TestClient, path: str) -> None:
    missing = uuid.uuid4()
    assert client.patch(f"/profile/{path}/{missing}", json={}).status_code == 404
    assert client.delete(f"/profile/{path}/{missing}").status_code == 404


# --- personal info ----------------------------------------------------------


def test_patch_personal_info(client: TestClient) -> None:
    response = client.patch(
        "/profile", json={"full_name": "Renamed", "location": "Toronto"}
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed"
    # Unset fields are left alone rather than nulled.
    assert response.json()["email"] == "test@example.com"

    assert client.get("/profile").json()["location"] == "Toronto"


def test_patch_personal_info_rejects_bad_email(client: TestClient) -> None:
    assert client.patch("/profile", json={"email": "not-an-email"}).status_code == 422


# --- experiences and bullets ------------------------------------------------


def test_create_experience_with_nested_bullets(client: TestClient) -> None:
    response = client.post(
        "/profile/experiences",
        json={
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2020-01-01",
            "bullets": [{"text": "first"}, {"text": "second"}],
        },
    )
    assert response.status_code == 201
    assert [b["text"] for b in response.json()["bullets"]] == ["first", "second"]


def test_bullets_stay_with_their_own_experience(client: TestClient) -> None:
    """The nesting guarantee: bullets never cross between experiences."""
    acme = client.post(
        "/profile/experiences",
        json={
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2020-01-01",
            "bullets": [{"text": "ACME first"}, {"text": "ACME second"}],
        },
    ).json()
    globex = client.post(
        "/profile/experiences",
        json={
            "company": "Globex",
            "title": "Engineer",
            "start_date": "2022-01-01",
            "bullets": [{"text": "GLOBEX first"}],
        },
    ).json()

    listed = {e["company"]: e for e in client.get("/profile/experiences").json()}
    assert [b["text"] for b in listed["Acme"]["bullets"]] == [
        "ACME first",
        "ACME second",
    ]
    assert [b["text"] for b in listed["Globex"]["bullets"]] == ["GLOBEX first"]
    assert acme["id"] != globex["id"]


def test_bullet_crud_and_reorder(client: TestClient) -> None:
    experience = client.post(
        "/profile/experiences",
        json={"company": "Acme", "title": "Engineer", "start_date": "2020-01-01"},
    ).json()
    base = f"/profile/experiences/{experience['id']}/bullets"

    first = client.post(base, json={"text": "one", "position": 0})
    assert first.status_code == 201
    second = client.post(base, json={"text": "two", "position": 1}).json()
    first_id = first.json()["id"]

    updated = client.patch(f"{base}/{first_id}", json={"text": "one, rewritten"})
    assert updated.json()["text"] == "one, rewritten"

    reordered = client.put(base + "/order", json={"ids": [second["id"], first_id]})
    assert [b["text"] for b in reordered.json()] == ["two", "one, rewritten"]

    assert client.delete(f"{base}/{second['id']}").status_code == 204
    remaining = client.get("/profile/experiences").json()[0]["bullets"]
    assert [b["text"] for b in remaining] == ["one, rewritten"]


def test_bullet_of_another_experience_is_404(client: TestClient) -> None:
    """A bullet id alone is not enough — it has to belong to the experience in the path."""
    first = client.post(
        "/profile/experiences",
        json={
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2020-01-01",
            "bullets": [{"text": "belongs to Acme"}],
        },
    ).json()
    second = client.post(
        "/profile/experiences",
        json={"company": "Globex", "title": "Engineer", "start_date": "2022-01-01"},
    ).json()

    bullet_id = first["bullets"][0]["id"]
    wrong = f"/profile/experiences/{second['id']}/bullets/{bullet_id}"
    assert client.patch(wrong, json={"text": "hijacked"}).status_code == 404
    assert client.delete(wrong).status_code == 404


def test_bullets_on_another_users_experience_are_404(
    client: TestClient, session: Session, other_user: User
) -> None:
    from datetime import date

    from models.profile import Experience

    theirs = Experience(
        user_id=other_user.id,
        company="Acme",
        title="Engineer",
        start_date=date(2020, 1, 1),
    )
    session.add(theirs)
    session.flush()

    response = client.post(
        f"/profile/experiences/{theirs.id}/bullets", json={"text": "sneaky"}
    )
    assert response.status_code == 404


# --- chronology -------------------------------------------------------------


@pytest.mark.parametrize(
    "path, payload",
    [
        (
            "education",
            {"school": "S", "degree": "D", "start_date": "2022-01-01", "end_date": "2020-01-01"},
        ),
        (
            "experiences",
            {"company": "C", "title": "T", "start_date": "2022-01-01", "end_date": "2020-01-01"},
        ),
        (
            "projects",
            {"name": "P", "start_date": "2022-01-01", "end_date": "2020-01-01"},
        ),
    ],
)
def test_create_rejects_end_before_start(
    client: TestClient, path: str, payload: dict
) -> None:
    assert client.post(f"/profile/{path}", json=payload).status_code == 422


@pytest.mark.parametrize(
    "path, create",
    [
        ("education", {"school": "S", "degree": "D", "start_date": "2022-01-01"}),
        ("experiences", {"company": "C", "title": "T", "start_date": "2022-01-01"}),
        ("projects", {"name": "P", "start_date": "2022-01-01"}),
    ],
)
def test_partial_patch_rejects_end_before_stored_start(
    client: TestClient, path: str, create: dict
) -> None:
    """The case the schema validator can't see: only end_date is sent."""
    item_id = client.post(f"/profile/{path}", json=create).json()["id"]

    response = client.patch(f"/profile/{path}/{item_id}", json={"end_date": "2020-01-01"})
    assert response.status_code == 422

    # And the bad value must not have been persisted.
    stored = client.get(f"/profile/{path}").json()[0]
    assert stored["end_date"] is None


@pytest.mark.parametrize(
    "path, create",
    [
        ("education", {"school": "S", "degree": "D", "start_date": "2020-01-01"}),
        ("experiences", {"company": "C", "title": "T", "start_date": "2020-01-01"}),
        ("projects", {"name": "P", "start_date": "2020-01-01"}),
    ],
)
def test_partial_patch_accepts_valid_end_date(
    client: TestClient, path: str, create: dict
) -> None:
    """The rule must not be rejecting everything."""
    item_id = client.post(f"/profile/{path}", json=create).json()["id"]
    response = client.patch(f"/profile/{path}/{item_id}", json={"end_date": "2023-01-01"})
    assert response.status_code == 200
    assert response.json()["end_date"] == "2023-01-01"


# --- assembled profile ------------------------------------------------------


def test_get_profile_returns_every_collection(client: TestClient) -> None:
    client.post("/profile/education", json={"school": "State U", "degree": "BSc"})
    client.post("/profile/skills", json={"name": "Python", "category": "Languages"})
    client.post("/profile/projects", json={"name": "Portfolio"})
    client.post("/profile/links", json={"label": "GitHub", "url": "https://gh/x"})
    client.post(
        "/profile/experiences",
        json={
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2020-01-01",
            "bullets": [{"text": "shipped a thing"}],
        },
    )

    profile = client.get("/profile").json()

    assert profile["full_name"] == "Test User"
    assert [e["school"] for e in profile["education"]] == ["State U"]
    assert [s["name"] for s in profile["skills"]] == ["Python"]
    assert [p["name"] for p in profile["projects"]] == ["Portfolio"]
    assert [link["label"] for link in profile["links"]] == ["GitHub"]
    assert [b["text"] for b in profile["experiences"][0]["bullets"]] == [
        "shipped a thing"
    ]


def test_get_profile_reflects_reordering(client: TestClient) -> None:
    ids = [
        client.post("/profile/skills", json={"name": name, "position": index}).json()[
            "id"
        ]
        for index, name in enumerate(["first", "second", "third"])
    ]
    client.put("/profile/skills/order", json={"ids": [ids[2], ids[1], ids[0]]})

    profile = client.get("/profile").json()
    assert [s["name"] for s in profile["skills"]] == ["third", "second", "first"]
