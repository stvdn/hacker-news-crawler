import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.scraper import (
    SOURCE_URL,
    USER_AGENT,
    HackerNewsScraper,
    UpstreamHTTPError,
    UpstreamParsingError,
    UpstreamTimeoutError,
    parse_entries,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def html() -> str:
    return (FIXTURES / "front_page.html").read_text(encoding="utf-8")


def test_first_30_and_metrics(html: str) -> None:
    entries = parse_entries(html)
    assert isinstance(entries, tuple)
    assert [entry.number for entry in entries] == list(range(1, 31))
    assert entries[0].title == "C++ & Python: café <tools>"
    assert (entries[0].points, entries[0].comments) == (1, 1)
    assert (entries[1].points, entries[1].comments) == (2, 0)
    assert entries[2].title == "Example company is hiring"
    assert (entries[2].points, entries[2].comments) == (None, None)
    assert (entries[3].points, entries[3].comments) == (None, 4)
    assert (entries[4].points, entries[4].comments) == (5, None)
    assert (entries[29].points, entries[29].comments) == (30, 30)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('<span class="rank">1.</span>', ""),
        ('<span class="rank">1.</span>', '<span class="rank">bad</span>'),
        ('<span class="rank">1.</span>', '<span class="rank">0.</span>'),
        ('<span class="rank">2.</span>', '<span class="rank">1.</span>'),
        ('<span class="titleline">', '<span class="missing">'),
        ("C++ &amp; Python: caf&#233; &lt;tools&gt;", " \t "),
        ('<span class="rank">30.</span>', ""),
    ],
)
def test_invalid_required_fields_are_not_replaced_by_31st(
    html: str, old: str, new: str
) -> None:
    with pytest.raises(UpstreamParsingError):
        parse_entries(html.replace(old, new, 1))


def test_malformed_31st_is_ignored(html: str) -> None:
    assert len(parse_entries(html.replace('<span class="rank">31.</span>', ""))) == 30


def test_fewer_than_30_rows(html: str) -> None:
    with pytest.raises(UpstreamParsingError):
        parse_entries(html.split('<tr class="athing submission" id="40030">')[0])


def test_error_page_is_not_a_snapshot() -> None:
    with pytest.raises(UpstreamParsingError):
        parse_entries((FIXTURES / "upstream_error.html").read_text())


def test_missing_metadata_does_not_borrow_next_story_metrics(html: str) -> None:
    start = html.index('<tr><td colspan="2">')
    end = html.index('<tr class="athing submission" id="40002">')
    entries = parse_entries(html[:start] + html[end:])
    assert (entries[0].points, entries[0].comments) == (None, None)
    assert (entries[1].points, entries[1].comments) == (2, 0)


def test_unreadable_metrics_are_unknown(html: str) -> None:
    entries = parse_entries(
        html.replace("1 point</span>", "-1 points</span>").replace(
            "1&nbsp;comment</a>", "unknown comments</a>"
        )
    )
    assert (entries[0].points, entries[0].comments) == (None, None)


def test_username_discuss_is_not_a_comment_count(html: str) -> None:
    entries = parse_entries(
        html.replace(
            '<a href="user?id=example" class="hnuser">example</a>',
            '<a href="user?id=discuss" class="hnuser">discuss</a>',
        )
    )
    assert entries[0].comments == 1
    assert entries[4].comments is None


def test_fetch_snapshot_and_request_configuration(html: str) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == SOURCE_URL
        assert request.headers["user-agent"] == USER_AGENT
        assert request.extensions["timeout"] == {
            "connect": 5,
            "read": 10,
            "write": 5,
            "pool": 5,
        }
        return httpx.Response(200, text=html)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            before = datetime.now(UTC)
            snapshot = await HackerNewsScraper(client).fetch_first_30()
            assert before <= snapshot.fetched_at <= datetime.now(UTC)
            assert snapshot.fetched_at.tzinfo is UTC
            assert snapshot.cache_hit is False
            assert snapshot.entries == parse_entries(html)
            assert not client.is_closed

    asyncio.run(run())
    assert len(requests) == 1


@pytest.mark.parametrize("status", [301, 404, 429, 500])
def test_http_errors_are_not_retried_or_followed(status: int) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, headers={"Location": "https://example.com/"})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with pytest.raises(UpstreamHTTPError) as error:
                await HackerNewsScraper(client).fetch_first_30()
            assert isinstance(error.value.__cause__, httpx.HTTPStatusError)

    asyncio.run(run())
    assert len(requests) == 1


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        httpx.ConnectError,
        httpx.RemoteProtocolError,
    ],
)
def test_transport_errors(failure: type[httpx.RequestError]) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise failure("upstream details", request=request)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            expected = (
                UpstreamTimeoutError
                if issubclass(failure, httpx.TimeoutException)
                else UpstreamHTTPError
            )
            with pytest.raises(expected) as error:
                await HackerNewsScraper(client).fetch_first_30()
            assert isinstance(error.value.__cause__, failure)

    asyncio.run(run())
    assert len(requests) == 1


def test_fetch_propagates_parsing_failure() -> None:
    async def run() -> None:
        transport = httpx.MockTransport(lambda _: httpx.Response(200, text="<html/>"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(UpstreamParsingError):
                await HackerNewsScraper(client).fetch_first_30()

    asyncio.run(run())
