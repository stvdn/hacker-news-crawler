import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from conftest import FakeRecorder, FakeSource

from app.adapters.cache import CachedEntrySource, cache_ttl_seconds
from app.domain.errors import (
    PersistenceError,
    UpstreamHTTPError,
    UpstreamParsingError,
    UpstreamTimeoutError,
)
from app.domain.models import Entry, EntryFilter, EntrySnapshot, RequestContext
from app.service import EntryService


@dataclass
class FakeClock:
    now: float = 0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def source() -> FakeSource:
    return FakeSource(
        EntrySnapshot(
            tuple(
                Entry(
                    rank,
                    "One two three four five six" if rank % 2 else "Short title",
                    rank,
                    31 - rank,
                )
                for rank in range(1, 31)
            ),
            datetime(2026, 10, 2, tzinfo=UTC),
            cache_hit=False,
        )
    )


@pytest.mark.parametrize("ttl", [-1, float("nan"), float("inf"), float("-inf")])
def test_rejects_invalid_ttl(source: FakeSource, ttl: float) -> None:
    with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
        CachedEntrySource(source, ttl_seconds=ttl)


@pytest.mark.parametrize("value", ["", "seconds", "-1", "nan", "inf", "-inf"])
def test_rejects_invalid_environment(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CACHE_TTL_SECONDS", value)
    with pytest.raises(ValueError, match="CACHE_TTL_SECONDS"):
        cache_ttl_seconds()


def test_default_and_configured_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CACHE_TTL_SECONDS", raising=False)
    assert cache_ttl_seconds() == 60
    for value in ("0", "0.5", "120"):
        monkeypatch.setenv("CACHE_TTL_SECONDS", value)
        assert cache_ttl_seconds() == float(value)


def test_miss_hit_exact_expiry_and_immutable_metadata(source: FakeSource) -> None:
    async def run() -> None:
        clock = FakeClock()
        cache = CachedEntrySource(source, clock=clock)
        first = await cache.fetch_first_30()
        clock.now = 59
        hit = await cache.fetch_first_30()
        assert source.calls == 1
        assert not first.cache_hit and hit.cache_hit
        assert hit.entries is first.entries is source.snapshot.entries
        assert hit.fetched_at == first.fetched_at
        assert source.snapshot.cache_hit is False

        # A hit must not extend expiry. Equality with the deadline is expired.
        clock.now = 60
        source.snapshot = replace(
            source.snapshot, fetched_at=first.fetched_at + timedelta(minutes=1)
        )
        refreshed = await cache.fetch_first_30()
        assert source.calls == 2
        assert refreshed.cache_hit is False
        assert refreshed.fetched_at == source.snapshot.fetched_at
        assert hit.fetched_at == first.fetched_at

    asyncio.run(run())


def test_ttl_starts_after_extraction_finishes(source: FakeSource) -> None:
    async def run() -> None:
        clock = FakeClock()

        class SlowSource(FakeSource):
            async def fetch_first_30(self) -> EntrySnapshot:
                clock.now += 100
                return await super().fetch_first_30()

        upstream = SlowSource(source.snapshot)
        cache = CachedEntrySource(upstream, ttl_seconds=10, clock=clock)
        await cache.fetch_first_30()
        clock.now = 109
        assert (await cache.fetch_first_30()).cache_hit is True
        clock.now = 110
        assert (await cache.fetch_first_30()).cache_hit is False
        assert upstream.calls == 2

    asyncio.run(run())


def test_zero_ttl_never_reuses_a_snapshot(source: FakeSource) -> None:
    async def run() -> None:
        cache = CachedEntrySource(source, ttl_seconds=0)
        results = await asyncio.gather(*(cache.fetch_first_30() for _ in range(5)))
        assert source.calls == 5
        assert all(not result.cache_hit for result in results)

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure",
    [
        UpstreamHTTPError("http failure"),
        UpstreamParsingError("malformed page"),
        UpstreamTimeoutError("timeout"),
        RuntimeError("unexpected failure"),
    ],
)
def test_failures_are_not_cached_or_replaced_with_expired_data(
    source: FakeSource, failure: Exception
) -> None:
    async def run() -> None:
        clock = FakeClock()
        cache = CachedEntrySource(source, clock=clock)
        source.failure = failure
        for _ in range(2):
            with pytest.raises(type(failure)):
                await cache.fetch_first_30()
        assert source.calls == 2
        source.failure = None
        assert not (await cache.fetch_first_30()).cache_hit
        assert (await cache.fetch_first_30()).cache_hit

        clock.now = 60
        source.failure = failure
        with pytest.raises(type(failure)):
            await cache.fetch_first_30()
        source.failure = None
        assert not (await cache.fetch_first_30()).cache_hit
        assert source.calls == 5

    asyncio.run(run())


def test_partial_snapshots_are_rejected_and_not_cached(source: FakeSource) -> None:
    async def run() -> None:
        complete = source.snapshot
        source.snapshot = replace(complete, entries=complete.entries[:29])
        cache = CachedEntrySource(source)
        for _ in range(2):
            with pytest.raises(UpstreamParsingError):
                await cache.fetch_first_30()
        source.snapshot = complete
        assert not (await cache.fetch_first_30()).cache_hit
        assert (await cache.fetch_first_30()).cache_hit
        assert source.calls == 3

    asyncio.run(run())


@pytest.mark.parametrize("expired", [False, True])
def test_concurrent_misses_share_one_successful_refresh(
    source: FakeSource, expired: bool
) -> None:
    async def run() -> None:
        clock = FakeClock()
        entered, release = asyncio.Event(), asyncio.Event()

        class GatedSource(FakeSource):
            async def fetch_first_30(self) -> EntrySnapshot:
                self.calls += 1
                entered.set()
                await release.wait()
                return self.snapshot

        upstream = GatedSource(source.snapshot)
        cache = CachedEntrySource(upstream, clock=clock)
        if expired:
            release.set()
            await cache.fetch_first_30()
            clock.now = 60
            release.clear()
            entered.clear()

        tasks = [asyncio.create_task(cache.fetch_first_30()) for _ in range(12)]
        await asyncio.wait_for(entered.wait(), timeout=5)
        await asyncio.sleep(0)  # Let every caller reach the held refresh lock.
        assert upstream.calls == 1 + int(expired)
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        assert upstream.calls == 1 + int(expired)
        assert sum(not result.cache_hit for result in results) == 1
        assert all(result.entries is source.snapshot.entries for result in results)
        assert len({result.fetched_at for result in results}) == 1

    asyncio.run(run())


def test_concurrent_failed_refreshes_remain_serialized(source: FakeSource) -> None:
    async def run() -> None:
        active = maximum = 0

        class FailingSource(FakeSource):
            async def fetch_first_30(self) -> EntrySnapshot:
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                try:
                    await asyncio.sleep(0)
                    return await super().fetch_first_30()
                finally:
                    active -= 1

        upstream = FailingSource(source.snapshot)
        upstream.failure = UpstreamTimeoutError("unavailable")
        cache = CachedEntrySource(upstream)
        results = await asyncio.wait_for(
            asyncio.gather(
                *(cache.fetch_first_30() for _ in range(6)), return_exceptions=True
            ),
            timeout=5,
        )
        assert all(isinstance(result, UpstreamTimeoutError) for result in results)
        assert upstream.calls == 6
        assert maximum == 1
        upstream.failure = None
        assert not (await cache.fetch_first_30()).cache_hit
        assert (await cache.fetch_first_30()).cache_hit

    asyncio.run(run())


def test_cancelled_refresh_releases_lock_for_waiter(source: FakeSource) -> None:
    async def run() -> None:
        entered = asyncio.Event()

        class CancelledSource(FakeSource):
            async def fetch_first_30(self) -> EntrySnapshot:
                self.calls += 1
                if self.calls == 1:
                    entered.set()
                    await asyncio.Event().wait()
                return self.snapshot

        upstream = CancelledSource(source.snapshot)
        cache = CachedEntrySource(upstream)
        first = asyncio.create_task(cache.fetch_first_30())
        await asyncio.wait_for(entered.wait(), timeout=5)
        second = asyncio.create_task(cache.fetch_first_30())
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not (await asyncio.wait_for(second, timeout=5)).cache_hit
        assert (await cache.fetch_first_30()).cache_hit
        assert upstream.calls == 2

    asyncio.run(run())


def test_independent_filters_and_usage_over_one_snapshot(
    source: FakeSource, recorder: FakeRecorder
) -> None:
    async def run() -> None:
        original = source.snapshot
        service = EntryService(CachedEntrySource(source), recorder)

        async def request(selected: EntryFilter) -> list[int]:
            result = await service.get_entries(
                selected, RequestContext(uuid4(), datetime.now(UTC), 0)
            )
            return [entry.number for entry in result.entries]

        assert await request(EntryFilter.ALL) == list(range(1, 31))
        assert await request(EntryFilter.LONG) == list(range(1, 31, 2))
        assert await request(EntryFilter.SHORT) == list(range(30, 0, -2))
        assert source.calls == 1
        assert source.snapshot == original
        assert [event.cache_hit for event in recorder.events] == [False, True, True]
        assert len({event.request_id for event in recorder.events}) == 3

        # A warm cache must still await recording and surface persistence errors.
        recorder.failure = OSError("unavailable")
        with pytest.raises(PersistenceError):
            await request(EntryFilter.ALL)
        assert recorder.attempts == 4
        assert source.calls == 1

    asyncio.run(run())
