from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings

# create_engine does not connect, so importing this module with the database down is safe.
# pool_pre_ping discards connections the server has closed underneath us — cheap insurance
# when the db container restarts independently of the backend.
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session scoped to one request."""
    with SessionLocal() as session:
        yield session
