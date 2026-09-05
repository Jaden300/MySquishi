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
#
# The pool choice matters and is easy to get wrong. StaticPool hands every
# caller the *same* connection, so two requests arriving together interleave
# on one sqlite cursor and fail with "bad parameter or other API misuse" or an
# IndexError from deep inside the result proxy. The dashboard fires half a
# dozen requests at once, so that is not a rare race. A file backed database
# gets a normal pool, one connection per thread.
#
# An in memory database is the exception: there, separate connections would
# each see their own empty database, so the shared connection is the point.
_in_memory = ":memory:" in settings.db_url

_engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool if _in_memory else None,
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
