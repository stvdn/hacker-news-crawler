from datetime import UTC, datetime

import pytest

from app.domain.models import Entry, EntrySnapshot, UsageEvent


class FakeSource:
    def __init__(self, snapshot: EntrySnapshot) -> None:
        self.snapshot = snapshot
        self.failure: Exception | None = None
        self.calls = 0

    async def fetch_first_30(self) -> EntrySnapshot:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.snapshot


class FakeRecorder:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []
        self.failure: Exception | None = None
        self.attempts = 0

    async def record(self, event: UsageEvent) -> None:
        self.attempts += 1
        if self.failure is not None:
            raise self.failure
        self.events.append(event)


@pytest.fixture
def source() -> FakeSource:
    return FakeSource(
        EntrySnapshot(
            (
                Entry(4, "One two three four five six", 8, None),
                Entry(2, "One two three four five", 20, 3),
                Entry(1, "One two three four five six", 10, 12),
                Entry(3, "Short title", None, 5),
            ),
            datetime(2026, 10, 2, tzinfo=UTC),
            cache_hit=True,
        )
    )


@pytest.fixture
def recorder() -> FakeRecorder:
    return FakeRecorder()
