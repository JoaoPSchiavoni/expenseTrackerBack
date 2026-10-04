"""
Database Connection and Session Management with SQLAlchemy.

Why: Isolates engine initialization and sessions within the infrastructure layer,
enabling the application to run against PostgreSQL in production and SQLite in-memory for testing.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Why: pool_pre_ping automatically discards broken or stale pool connections
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=settings.DEBUG)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for typed SQLAlchemy models."""


def get_db_session() -> Generator[Session, None, None]:
    """Provides a database session within the request context.

    Why: Guarantees each HTTP request operates within its own isolated session
    and cleans up connections in the finally block regardless of errors.

    Yields:
        Session: Active SQLAlchemy Session instance.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
