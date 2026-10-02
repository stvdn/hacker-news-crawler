"""Database configuration shared by application startup and migrations."""

import os

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def _optional_setting(name: str) -> str | None:
    value = os.environ.get(name)
    if value is not None and not value.strip():
        raise RuntimeError(f"{name} must not be blank when set")
    return value


def database_url() -> URL:
    value = os.environ.get("DATABASE_URL")
    if value is None or not value.strip():
        raise RuntimeError(
            "DATABASE_URL must be set before starting the API or Alembic"
        )
    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise RuntimeError("DATABASE_URL must be a valid SQLAlchemy URL") from None
    if url.drivername != "postgresql+asyncpg":
        raise RuntimeError("DATABASE_URL must use the postgresql+asyncpg driver")
    if url.port is not None and not 1 <= url.port <= 65535:
        raise RuntimeError("DATABASE_URL port must be between 1 and 65535")

    # Raw settings avoid interpreting reserved characters as URL syntax.
    return url.set(
        username=_optional_setting("DATABASE_USER"),
        database=_optional_setting("DATABASE_NAME"),
        password=_optional_setting("DATABASE_PASSWORD"),
    )
