"""Small asynchronous contracts for source and usage adapters."""

from typing import Protocol

from app.domain.models import EntrySnapshot, UsageEvent


class EntrySource(Protocol):
    async def fetch_first_30(self) -> EntrySnapshot: ...


class UsageRecorder(Protocol):
    async def record(self, event: UsageEvent) -> None: ...
