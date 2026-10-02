"""Explicitly opted-in smoke check; excluded from ordinary test runs."""

import asyncio
import os

import httpx
import pytest

from app.scraper import HackerNewsScraper


@pytest.mark.skipif(
    os.environ.get("HN_LIVE_SMOKE") != "1", reason="Set HN_LIVE_SMOKE=1 to opt in"
)
def test_live_front_page() -> None:
    async def run() -> None:
        async with httpx.AsyncClient() as client:
            snapshot = await HackerNewsScraper(client).fetch_first_30()
        assert len(snapshot.entries) == 30
        assert [entry.number for entry in snapshot.entries] == list(range(1, 31))

    asyncio.run(run())
