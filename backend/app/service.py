"""Coordinate a snapshot, pure filtering, and one awaited usage write."""

from collections.abc import Callable
from time import monotonic

from app.domain.errors import PersistenceError, UpstreamError, UpstreamTimeoutError
from app.domain.filters import filter_entries
from app.domain.models import (
    EntriesResult,
    EntryFilter,
    RequestContext,
    UsageEvent,
    UsageOutcome,
)
from app.domain.ports import EntrySource, UsageRecorder


class EntryService:
    def __init__(
        self,
        source: EntrySource,
        usage: UsageRecorder,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._source = source
        self._usage = usage
        self._clock = clock

    async def get_entries(
        self, entry_filter: EntryFilter, context: RequestContext
    ) -> EntriesResult:
        cache_hit = False
        try:
            snapshot = await self._source.fetch_first_30()
            cache_hit = snapshot.cache_hit
            entries = filter_entries(snapshot.entries, entry_filter)
            result = EntriesResult(
                request_id=context.request_id,
                fetched_at=snapshot.fetched_at,
                cache_hit=cache_hit,
                filter=entry_filter,
                source_count=len(snapshot.entries),
                result_count=len(entries),
                entries=entries,
            )
        except Exception as exc:
            if isinstance(exc, UpstreamTimeoutError):
                outcome = UsageOutcome.UPSTREAM_TIMEOUT
            elif isinstance(exc, UpstreamError):
                outcome = UsageOutcome.UPSTREAM_ERROR
            else:
                outcome = UsageOutcome.INTERNAL_ERROR
            await self._record(context, entry_filter, outcome, None, cache_hit)
            raise

        await self._record(
            context, entry_filter, UsageOutcome.SUCCESS, len(entries), cache_hit
        )
        return result

    async def _record(
        self,
        context: RequestContext,
        entry_filter: EntryFilter,
        outcome: UsageOutcome,
        result_count: int | None,
        cache_hit: bool,
    ) -> None:
        event = UsageEvent(
            request_id=context.request_id,
            requested_at=context.started_at,
            filter=entry_filter,
            outcome=outcome,
            result_count=result_count,
            processing_duration_ms=max(
                0.0, (self._clock() - context.started_monotonic) * 1000
            ),
            cache_hit=cache_hit,
        )
        try:
            await self._usage.record(event)
        except Exception as exc:
            raise PersistenceError("Usage recording failed") from exc
