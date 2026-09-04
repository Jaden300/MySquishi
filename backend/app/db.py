"""Database engine and session management.

SQLite with SQLModel. There is no migration tool: the schema is created with
create_all on startup, which is the right trade for a project of this size.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# check_same_thread is required because FastAPI serves requests from a thread
# pool while the websocket handler holds its own connection.
_engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


def get_engine():
    return _engine


def create_db_and_tables() -> None:
    """Create the schema. Safe to call repeatedly."""
    settings.ensure_dirs()
    # Importing models registers the tables on SQLModel.metadata. The import
    # lives here rather than at module scope to avoid a circular import.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(_engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(_engine) as session:
        yield session
