import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.usage import PostgresUsageRepository, usage_events
from app.domain.models import EntryFilter, UsageEvent, UsageOutcome
from app.main import app


def event() -> UsageEvent:
    return UsageEvent(
        request_id=uuid4(),
        requested_at=datetime(2026, 10, 2, 12, 30, tzinfo=UTC),
        filter=EntryFilter.SHORT,
        outcome=UsageOutcome.SUCCESS,
        result_count=12,
        processing_duration_ms=23.75,
        cache_hit=True,
    )


def test_record_commits_all_fields_for_concurrent_events(
    migrated_database: str,
) -> None:
    async def run() -> None:
        engine = create_async_engine(migrated_database)
        repository = PostgresUsageRepository(async_sessionmaker(engine))
        events = [event() for _ in range(12)]
        events.extend(
            replace(event(), outcome=outcome, result_count=None, cache_hit=False)
            for outcome in UsageOutcome
            if outcome != UsageOutcome.SUCCESS
        )
        try:
            await asyncio.gather(*(repository.record(item) for item in events))
            # A separate connection must see the committed rows, with exact values.
            async with engine.connect() as connection:
                rows = (await connection.execute(select(usage_events))).mappings().all()
            actual = {row["request_id"]: dict(row) for row in rows}
            assert len(actual) == len(events)
            for item in events:
                assert actual[item.request_id] == {
                    "request_id": item.request_id,
                    "requested_at": item.requested_at,
                    "filter": item.filter.value,
                    "outcome": item.outcome.value,
                    "result_count": item.result_count,
                    "processing_duration_ms": item.processing_duration_ms,
                    "cache_hit": item.cache_hit,
                }
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_record_rolls_back_failed_writes_and_allows_next_write(
    migrated_database: str,
) -> None:
    async def run() -> None:
        engine = create_async_engine(migrated_database)
        repository = PostgresUsageRepository(async_sessionmaker(engine))
        item = event()
        try:
            await repository.record(item)
            with pytest.raises(IntegrityError):
                await repository.record(item)
            with pytest.raises(IntegrityError):
                await repository.record(replace(event(), result_count=-1))
            await repository.record(event())
            async with engine.connect() as connection:
                assert (
                    await connection.scalar(
                        select(func.count()).select_from(usage_events)
                    )
                    == 2
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_migration_matches_metadata_and_can_be_reapplied(
    migrated_database: str,
) -> None:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.check(config)
    command.downgrade(config, "base")

    async def table_exists() -> bool:
        engine = create_async_engine(migrated_database)
        try:
            async with engine.connect() as connection:
                return (
                    await connection.scalar(
                        text("SELECT to_regclass('public.usage_events')")
                    )
                    is not None
                )
        finally:
            await engine.dispose()

    assert not asyncio.run(table_exists())
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert asyncio.run(table_exists())


@pytest.mark.parametrize("upstream_status", [200, 503])
def test_entries_persist_usage_before_returning_response(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch, upstream_status: int
) -> None:
    html = (Path(__file__).parents[1] / "fixtures/front_page.html").read_text(
        encoding="utf-8"
    )
    upstream = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(upstream_status, text=html)
        )
    )
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda: upstream)
    with TestClient(app) as client:
        assert client.get("/api/v1/entries?filter=invalid").status_code == 422
        response = client.get("/api/v1/entries?filter=long")
        assert response.status_code == (200 if upstream_status == 200 else 502)

        async def verify() -> None:
            engine = create_async_engine(migrated_database)
            try:
                async with engine.connect() as connection:
                    result = await connection.execute(select(usage_events))
                    row = result.mappings().one()
                assert str(row["request_id"]) == response.json()["request_id"]
                assert row["filter"] == "long"
                assert row["cache_hit"] is False
                assert row["outcome"] == (
                    "success" if upstream_status == 200 else "upstream_error"
                )
                assert row["result_count"] == response.json().get("result_count")
                assert row["processing_duration_ms"] >= 0
            finally:
                await engine.dispose()

        asyncio.run(verify())
    assert upstream.is_closed


def test_database_write_failure_returns_safe_503(
    migrated_database: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def remove_table() -> None:
        engine = create_async_engine(migrated_database)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DROP TABLE usage_events"))
        finally:
            await engine.dispose()

    asyncio.run(remove_table())
    upstream = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    )
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda: upstream)
    with TestClient(app) as client:
        response = client.get("/api/v1/entries")
    assert response.status_code == 503
    assert response.json()["detail"] == "Usage recording is unavailable"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    log = next(record for record in caplog.records if record.name == "app.api.errors")
    assert json.loads(log.message)["error_type"] == "PersistenceError"


def test_cached_requests_each_commit_their_own_usage_event(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CACHE_TTL_SECONDS", "60")
    html = (Path(__file__).parents[1] / "fixtures/front_page.html").read_text(
        encoding="utf-8"
    )
    fetches = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal fetches
        fetches += 1
        return httpx.Response(200, text=html)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda: upstream)
    with TestClient(app) as client:
        responses = [
            client.get(f"/api/v1/entries?filter={selected}")
            for selected in ("all", "long", "short")
        ]
        assert all(response.status_code == 200 for response in responses)
        assert fetches == 1
        assert [response.json()["cache_hit"] for response in responses] == [
            False,
            True,
            True,
        ]
        assert len({response.json()["fetched_at"] for response in responses}) == 1

        async def verify() -> None:
            engine = create_async_engine(migrated_database)
            try:
                async with engine.connect() as connection:
                    rows = (
                        (await connection.execute(select(usage_events)))
                        .mappings()
                        .all()
                    )
                assert len(rows) == 3
                by_id = {str(row["request_id"]): row for row in rows}
                for response in responses:
                    body = response.json()
                    row = by_id[body["request_id"]]
                    assert row["outcome"] == "success"
                    assert row["filter"] == body["filter"]
                    assert row["cache_hit"] == body["cache_hit"]
                    assert row["result_count"] == body["result_count"]
            finally:
                await engine.dispose()

        asyncio.run(verify())
