"""Migrate a disposable PostgreSQL database; never modify the configured database."""

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture
def migrated_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL integration tests")
    url = make_url(admin_url)
    if url.drivername != "postgresql+asyncpg":
        pytest.fail("TEST_DATABASE_URL must use postgresql+asyncpg")
    name = f"hn_test_{uuid4().hex}"

    async def manage_database(create: bool) -> None:
        engine = create_async_engine(
            url, isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        try:
            async with engine.connect() as connection:
                statement = (
                    f'CREATE DATABASE "{name}"'
                    if create
                    else f'DROP DATABASE "{name}" WITH (FORCE)'
                )
                await connection.execute(text(statement))
        finally:
            await engine.dispose()

    asyncio.run(manage_database(True))
    test_url = url.set(database=name).render_as_string(hide_password=False)
    # Only TEST_DATABASE_URL controls test credentials, even in a configured shell.
    for setting in ("DATABASE_USER", "DATABASE_NAME", "DATABASE_PASSWORD"):
        monkeypatch.delenv(setting, raising=False)
    monkeypatch.setenv("DATABASE_URL", test_url)
    try:
        config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        command.upgrade(config, "head")
        yield test_url
    finally:
        asyncio.run(manage_database(False))
