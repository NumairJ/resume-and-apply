import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.db import get_db
from core.deps import DEFAULT_USER_ID, get_current_user_id
from main import create_app
from models.base import Base
from models.profile import User
from schemas.profile import Profile
from tests.factories import sample_profile


def _test_database_url() -> str:
    """The configured database with `_test` appended to its name.

    A separate database rather than the dev one: schema is created and dropped
    wholesale here, which would be destructive against real data.
    """
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(
        hide_password=False
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = make_url(_test_database_url())

    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT, and it has to
    # be issued from a different database — "postgres" always exists.
    admin_url = url.set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    test_engine = create_engine(url)
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back when the test ends.

    The session joins an already-open transaction on the connection, so everything it
    does is undone at the end of the test — including the `session.commit()` that every
    mutating route handler performs, which releases a savepoint rather than ending the
    enclosing transaction.

    `join_transaction_mode` is set explicitly rather than left to the default. The
    SQLAlchemy 2.0 default, `conditional_savepoint`, already behaves this way when the
    bound connection has a transaction open, which it always does here — so this pins
    the behaviour we rely on instead of depending on a conditional default staying
    conditional in our favour.
    """
    connection = engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    db = factory()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def user(session: Session) -> User:
    """The single seeded user, as the initial migration would have created it."""
    existing = session.get(User, DEFAULT_USER_ID)
    if existing:
        return existing
    user = User(
        id=DEFAULT_USER_ID, full_name="Test User", email="test@example.com"
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def other_user(session: Session) -> User:
    """A second user, for asserting that per-user queries actually filter."""
    user = User(
        id=uuid.uuid4(), full_name="Other User", email="other@example.com"
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def client(session: Session, user: User) -> Iterator[TestClient]:
    """A test client wired to the rolled-back session and the seeded user.

    Overriding `get_db` is what keeps route tests isolated: handlers commit for real,
    but against a session joined to the outer transaction, so it all unwinds.
    """
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user_id] = lambda: user.id
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def profile() -> Profile:
    """The shared sample profile used by the guardrail and tailoring suites."""
    return sample_profile()


@pytest.fixture(autouse=True)
def resume_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect generated resumes to a per-test directory.

    Autouse deliberately: `/data/resumes` is a real named volume holding the user's
    actual PDFs, and a route test that generates a resume would otherwise write into
    it. Opting in per test would mean remembering to, which is exactly the kind of
    thing that gets forgotten once.
    """
    target = tmp_path / "resumes"
    monkeypatch.setattr(settings, "resume_dir", target)
    return target
