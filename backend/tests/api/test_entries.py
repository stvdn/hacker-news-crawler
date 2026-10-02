import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from conftest import FakeRecorder, FakeSource
from fastapi.testclient import TestClient

from app.api.routes import get_entry_service
from app.domain.errors import (
    UpstreamHTTPError,
    UpstreamParsingError,
    UpstreamTimeoutError,
)
from app.main import app
from app.service import EntryService


@pytest.fixture
def client(source: FakeSource, recorder: FakeRecorder) -> Iterator[TestClient]:
    app.dependency_overrides[get_entry_service] = lambda: EntryService(source, recorder)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("query", "selected", "ranks"),
    [
        ("", "all", [1, 2, 3, 4]),
        ("?filter=all", "all", [1, 2, 3, 4]),
        ("?filter=long", "long", [1, 4]),
        ("?filter=short", "short", [2, 3]),
    ],
)
def test_entries_schema_and_filters(
    client: TestClient,
    recorder: FakeRecorder,
    query: str,
    selected: str,
    ranks: list[int],
) -> None:
    before = datetime.now(UTC)
    response = client.get(f"/api/v1/entries{query}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "request_id",
        "fetched_at",
        "cache_hit",
        "filter",
        "source_count",
        "result_count",
        "entries",
    }
    assert str(UUID(body["request_id"])) == response.headers["X-Request-ID"]
    assert body["fetched_at"] == "2026-10-02T00:00:00Z"
    assert body["filter"] == selected
    assert body["cache_hit"] is True
    assert body["source_count"] == 4
    assert body["result_count"] == len(ranks)
    assert [entry["number"] for entry in body["entries"]] == ranks
    assert all(
        set(e) == {"number", "title", "points", "comments"} for e in body["entries"]
    )
    assert any(e["points"] is None or e["comments"] is None for e in body["entries"])
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert str(event.request_id) == body["request_id"]
    assert before <= event.requested_at <= datetime.now(UTC)


@pytest.mark.parametrize("query", ["unknown", "ALL", ""])
def test_invalid_filter_has_no_usage_or_fetch(
    client: TestClient, source: FakeSource, recorder: FakeRecorder, query: str
) -> None:
    response = client.get(f"/api/v1/entries?filter={query}")
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid request parameters"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert source.calls == recorder.attempts == 0


@pytest.mark.parametrize(
    ("failure", "status"),
    [
        (UpstreamTimeoutError("private"), 504),
        (UpstreamHTTPError("private"), 502),
        (UpstreamParsingError("private"), 502),
        (RuntimeError("private"), 500),
    ],
)
def test_errors_are_safe_and_recorded(
    client: TestClient,
    source: FakeSource,
    recorder: FakeRecorder,
    failure: Exception,
    status: int,
) -> None:
    source.failure = failure
    response = client.get("/api/v1/entries")
    assert response.status_code == status
    assert "private" not in response.text
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert len(recorder.events) == 1
    assert recorder.events[0].result_count is None


@pytest.mark.parametrize("upstream_failure", [False, True])
def test_record_failure_returns_503_and_structured_log(
    client: TestClient,
    source: FakeSource,
    recorder: FakeRecorder,
    caplog: pytest.LogCaptureFixture,
    upstream_failure: bool,
) -> None:
    recorder.failure = OSError("private connection details")
    if upstream_failure:
        source.failure = UpstreamTimeoutError("private upstream details")
    response = client.get("/api/v1/entries")
    assert response.status_code == 503
    assert "private" not in response.text
    assert recorder.attempts == 1
    assert recorder.events == []
    log = next(r for r in caplog.records if r.name == "app.api.errors")
    assert json.loads(log.message) == {
        "event": "request_failed",
        "request_id": response.json()["request_id"],
        "status_code": 503,
        "error_type": "PersistenceError",
    }
    assert "private connection details" in caplog.text


def test_concurrent_requests_have_independent_contexts_and_events(
    client: TestClient, source: FakeSource, recorder: FakeRecorder
) -> None:
    async def run() -> list[httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as async_client:
            return await asyncio.gather(
                *(
                    async_client.get(f"/api/v1/entries?filter={value}")
                    for value in ("all", "long", "short")
                )
            )

    responses = asyncio.run(run())
    assert all(response.status_code == 200 for response in responses)
    ids = {response.json()["request_id"] for response in responses}
    assert len(ids) == 3
    assert {str(event.request_id) for event in recorder.events} == ids
    assert source.calls == recorder.attempts == 3
    assert [r.json()["result_count"] for r in responses] == [4, 2, 2]


def test_lifespan_assembles_scraper_and_closes_shared_client(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    html = (Path(__file__).parents[1] / "fixtures" / "front_page.html").read_text(
        encoding="utf-8"
    )
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=html)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda: upstream_client)
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get("/api/v1/entries")
            assert response.status_code == 200
            assert response.json()["source_count"] == 30
            assert response.json()["cache_hit"] is False
        assert not upstream_client.is_closed
    assert upstream_client.is_closed
    assert len(requests) == 2
    events = [
        json.loads(r.message)
        for r in caplog.records
        if r.name == "app.adapters.usage"
    ]
    assert len(events) == 2
    assert all(event["event"] == "usage_not_persisted" for event in events)
    assert all(event["outcome"] == "success" for event in events)
