"""Test-only API for Playwright; never imported by the production application.

Uses the real service, routes, filtering, and error mapping with controlled ports.
Run only on loopback. No database or live upstream is accessed.
"""

import asyncio
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.api.errors import configure_error_handling
from app.api.routes import router
from app.domain.errors import UpstreamHTTPError, UpstreamTimeoutError
from app.domain.models import Entry, EntrySnapshot, UsageEvent
from app.service import EntryService

ENTRIES = (
    Entry(1, "One two three four five", 100, 1),
    Entry(2, "One two three four five six", 20, 50),
    Entry(3, "Seven words make this a longer title", 30, 50),
    Entry(4, "Another long title with missing comments", 5, None),
    Entry(5, "C++ & Python: café <tools>", 0, 0),
    Entry(6, "Example company is hiring", None, None),
    *(Entry(rank, f"Example story {rank}", rank, rank) for rank in range(7, 31)),
)
LONG_ONLY_ENTRIES = tuple(
    Entry(rank, f"Example long story number {rank} today", rank, rank)
    for rank in range(1, 31)
)


class Scenario(BaseModel):
    status: int = 200
    delay: float = Field(default=0, ge=0, le=5)
    all_long_titles: bool = False


scenario = Scenario()
events: list[UsageEvent] = []


class BrowserSource:
    async def fetch_first_30(self) -> EntrySnapshot:
        await asyncio.sleep(scenario.delay)
        if scenario.status == 504:
            raise UpstreamTimeoutError("Synthetic timeout")
        if scenario.status == 502:
            raise UpstreamHTTPError("Synthetic upstream failure")
        return EntrySnapshot(
            LONG_ONLY_ENTRIES if scenario.all_long_titles else ENTRIES,
            datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
            cache_hit=False,
        )


class BrowserRecorder:
    async def record(self, event: UsageEvent) -> None:
        if scenario.status == 503:
            raise RuntimeError("Synthetic persistence failure")
        events.append(event)


app = FastAPI()
app.include_router(router)
configure_error_handling(app)
app.state.entry_service = EntryService(BrowserSource(), BrowserRecorder())


@app.post("/__test/scenario")
def set_scenario(value: Scenario) -> dict[str, str]:
    global scenario
    scenario = value
    events.clear()
    return {"status": "ok"}


@app.get("/__test/events")
def recorded_events() -> list[UsageEvent]:
    return events
