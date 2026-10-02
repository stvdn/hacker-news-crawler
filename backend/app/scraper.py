"""Hacker News HTML adapter; callers own the shared HTTP client lifecycle."""

import re
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup, Tag

from app.models import Entry, EntrySnapshot

# Fixed by the project requirements; this parser supports Hacker News HTML only.
SOURCE_URL = "https://news.ycombinator.com/"
USER_AGENT = "hacker-news-crawler/0.1 (HTML front-page reader)"
TIMEOUT = httpx.Timeout(connect=5, read=10, write=5, pool=5)


class UpstreamError(Exception):
    """The source could not supply a complete snapshot."""


class UpstreamTimeoutError(UpstreamError):
    """The upstream request exceeded its timeout."""


class UpstreamHTTPError(UpstreamError):
    """An upstream transport or HTTP status failure."""


class UpstreamParsingError(UpstreamError):
    """The source HTML did not contain 30 valid entries."""


def _metric(text: str, label: str) -> int | None:
    match = re.fullmatch(rf"([0-9]+) {label}", text)
    return int(match[1]) if match else None


def _parse_metrics(row: Tag) -> tuple[int | None, int | None]:
    """Read points and comments from this story's adjacent metadata row."""
    # Searching forward for any subtext would steal a later story's metrics.
    metadata = row.find_next_sibling("tr")
    if not isinstance(metadata, Tag) or "athing" in metadata.get("class", []):
        return None, None
    subtext = metadata.select_one(".subtext")
    if subtext is None:
        return None, None

    score = subtext.select_one(".score")
    points = _metric(score.get_text(" ", strip=True), "points?") if score else None
    for link in subtext.select('a[href^="item?id="]'):
        text = " ".join(link.get_text(" ", strip=True).split())
        if text == "discuss":
            return points, 0
        comments = _metric(text, "comments?")
        if comments is not None:
            return points, comments
    return points, None


def _parse_entry(row: Tag) -> Entry:
    """Parse one story, rejecting missing or invalid required fields."""
    rank = row.select_one(".rank")
    title = row.select_one(".titleline > a")
    rank_match = (
        re.fullmatch(r"([0-9]+)\.", rank.get_text(strip=True)) if rank else None
    )
    if rank_match is None or title is None:
        raise UpstreamParsingError("Missing or invalid story rank/title")
    number = int(rank_match[1])
    title_text = title.get_text(" ", strip=True)
    if number < 1 or not title_text:
        raise UpstreamParsingError("Missing or invalid story rank/title")

    points, comments = _parse_metrics(row)
    return Entry(number, title_text, points, comments)


def parse_entries(html: str) -> tuple[Entry, ...]:
    """Extract the first 30 story rows without replacing malformed entries."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.athing")[:30]
    if len(rows) != 30:
        raise UpstreamParsingError("Expected 30 story rows")

    entries: list[Entry] = []
    ranks: set[int] = set()
    for row in rows:
        entry = _parse_entry(row)
        if entry.number in ranks:
            raise UpstreamParsingError("Duplicate story rank")
        ranks.add(entry.number)
        entries.append(entry)
    return tuple(entries)


class HackerNewsScraper:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch_first_30(self) -> EntrySnapshot:
        try:
            response = await self._client.get(
                SOURCE_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("Hacker News request timed out") from exc
        except httpx.HTTPError as exc:
            raise UpstreamHTTPError("Hacker News request failed") from exc

        entries = parse_entries(response.text)
        return EntrySnapshot(entries, datetime.now(UTC), cache_hit=False)
