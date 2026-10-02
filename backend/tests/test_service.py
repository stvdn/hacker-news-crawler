import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from conftest import FakeRecorder, FakeSource

from app.domain.errors import (
    PersistenceError,
    UpstreamHTTPError,
    UpstreamParsingError,
    UpstreamTimeoutError,
)
from app.domain.models import EntryFilter, RequestContext, UsageEvent, UsageOutcome
from app.service import EntryService


@pytest.fixture
def context() -> RequestContext:
    return RequestContext(uuid4(), datetime.now(UTC), 10.0)


@pytest.mark.parametrize(
    ("entry_filter", "ranks"),
    [
        (EntryFilter.ALL, [1, 2, 3, 4]),
        (EntryFilter.LONG, [1, 4]),
        (EntryFilter.SHORT, [2, 3]),
    ],
)
def test_filter_and_record(
    source: FakeSource,
    recorder: FakeRecorder,
    context: RequestContext,
    entry_filter: EntryFilter,
    ranks: list[int],
) -> None:
    original = source.snapshot.entries
    service = EntryService(source, recorder, clock=lambda: 10.125)
    result = asyncio.run(service.get_entries(entry_filter, context))

    assert [entry.number for entry in result.entries] == ranks
    assert result.request_id == context.request_id
    assert result.fetched_at == source.snapshot.fetched_at
    assert result.cache_hit is True
    assert result.filter == entry_filter
    assert result.source_count == 4
    assert result.result_count == len(ranks)
    assert source.snapshot.entries == original
    assert source.calls == recorder.attempts == len(recorder.events) == 1
    event = recorder.events[0]
    assert event.request_id == context.request_id
    assert event.requested_at == context.started_at
    assert event.filter == entry_filter
    assert event.outcome == UsageOutcome.SUCCESS
    assert event.cache_hit is True
    assert event.result_count == len(ranks)
    assert event.processing_duration_ms == 125


@pytest.mark.parametrize(
    ("failure", "outcome"),
    [
        (UpstreamTimeoutError("private"), UsageOutcome.UPSTREAM_TIMEOUT),
        (UpstreamHTTPError("private"), UsageOutcome.UPSTREAM_ERROR),
        (UpstreamParsingError("private"), UsageOutcome.UPSTREAM_ERROR),
        (RuntimeError("private"), UsageOutcome.INTERNAL_ERROR),
    ],
)
def test_failed_fetch_is_recorded_before_reraising(
    source: FakeSource,
    recorder: FakeRecorder,
    context: RequestContext,
    failure: Exception,
    outcome: UsageOutcome,
) -> None:
    source.failure = failure
    service = EntryService(source, recorder, clock=lambda: 11)
    with pytest.raises(type(failure)) as error:
        asyncio.run(service.get_entries(EntryFilter.LONG, context))
    assert error.value is failure
    assert recorder.attempts == len(recorder.events) == 1
    event = recorder.events[0]
    assert event.outcome == outcome
    assert event.request_id == context.request_id
    assert event.filter == EntryFilter.LONG
    assert event.result_count is None
    assert event.cache_hit is False


@pytest.mark.parametrize("upstream_failure", [False, True])
def test_recording_failure_takes_precedence_without_retry(
    source: FakeSource,
    recorder: FakeRecorder,
    context: RequestContext,
    upstream_failure: bool,
) -> None:
    if upstream_failure:
        source.failure = UpstreamTimeoutError("private")
    recorder.failure = OSError("database private details")
    service = EntryService(source, recorder)
    with pytest.raises(PersistenceError) as error:
        asyncio.run(service.get_entries(EntryFilter.ALL, context))
    assert error.value.__cause__ is recorder.failure
    assert recorder.attempts == 1
    assert recorder.events == []


def test_duration_excludes_awaited_recording_time(
    source: FakeSource, context: RequestContext
) -> None:
    now = 10.5

    class SlowRecorder(FakeRecorder):
        async def record(self, event: UsageEvent) -> None:
            nonlocal now
            await asyncio.sleep(0)
            now += 2
            await super().record(event)

    recorder = SlowRecorder()
    service = EntryService(source, recorder, clock=lambda: now)
    asyncio.run(service.get_entries(EntryFilter.ALL, context))
    assert recorder.attempts == 1
    assert now == 12.5
    assert recorder.events[0].processing_duration_ms == 500
