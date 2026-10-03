"""Process-local snapshot cache with one refresh at a time."""

import asyncio
import math
import os
from collections.abc import Callable
from dataclasses import replace
from time import monotonic

from app.domain.errors import UpstreamParsingError
from app.domain.models import EntrySnapshot
from app.domain.ports import EntrySource


def _validate_ttl(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError("CACHE_TTL_SECONDS must be a finite nonnegative number")
    return value


def cache_ttl_seconds() -> float:
    """Read startup configuration; zero disables reuse, not usage recording."""
    try:
        value = float(os.environ.get("CACHE_TTL_SECONDS", "60"))
    except ValueError as exc:
        raise ValueError(
            "CACHE_TTL_SECONDS must be a finite nonnegative number"
        ) from exc
    return _validate_ttl(value)


class CachedEntrySource:
    def __init__(
        self,
        source: EntrySource,
        ttl_seconds: float = 60,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._source = source
        self._ttl_seconds = _validate_ttl(ttl_seconds)
        self._clock = clock
        self._lock = asyncio.Lock()
        self._snapshot: EntrySnapshot | None = None
        self._expires_at = 0.0

    def _cached_snapshot(self) -> EntrySnapshot | None:
        if self._snapshot is not None and self._clock() < self._expires_at:
            return replace(self._snapshot, cache_hit=True)
        return None

    async def _fetch_snapshot(self) -> EntrySnapshot:
        snapshot = await self._source.fetch_first_30()
        if len(snapshot.entries) != 30:
            raise UpstreamParsingError("Expected a complete 30-entry snapshot")
        # The wrapper owns per-request hit metadata; it never mutates the source.
        return replace(snapshot, cache_hit=False)

    async def fetch_first_30(self) -> EntrySnapshot:
        if self._ttl_seconds == 0:
            return await self._fetch_snapshot()

        snapshot = self._cached_snapshot()
        if snapshot is not None:
            return snapshot

        async with self._lock:
            # Another request may have completed a refresh while we waited.
            snapshot = self._cached_snapshot()
            if snapshot is not None:
                return snapshot

            snapshot = await self._fetch_snapshot()
            expires_at = self._clock() + self._ttl_seconds
            self._snapshot = snapshot
            self._expires_at = expires_at
            return snapshot
