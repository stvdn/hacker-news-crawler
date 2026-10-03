# Application specification

This document describes the current application contract. See the
[architecture](architecture.md) for implementation boundaries and the
[completed implementation plan](implementation-plan.md) for delivery history.

## Exercise scope and implementation choices

The exercise scope recorded in this repository is to scrape the first 30 Hacker
News front-page entries, filter and sort them by title length and metrics, and
persist the request timestamp and applied filter. The source is the visible
[Hacker News front page](https://news.ycombinator.com/); the Hacker News API is
not a substitute for HTML scraping.

The implementation adds a Next.js interface and independently usable FastAPI
endpoint, PostgreSQL migrations, diagnostic request IDs, failure-event recording,
a snapshot cache, automated checks, and Docker Compose. These are delivery and
engineering choices. In particular, awaiting persistence before responding and
caching snapshots are deliberate choices rather than mandatory exercise behavior.
The public demo is deployed with Dokploy; its link is in the [README](../README.md).

The rules below make ambiguities explicit: word counting, missing metrics,
tie-breaking, and rejecting incomplete extractions. They define the delivered
behavior and are covered by automated tests.

## API and business rules

`GET /api/v1/entries?filter=all|long|short` defaults to `all`.

| Filter | Selection | Ordering |
| --- | --- | --- |
| `all` | First 30 entries | Original rank ascending |
| `long` | More than five title words | Comments descending |
| `short` | Five or fewer title words | Points descending |

Metric ties use original rank ascending. Unknown metrics sort after all numeric
values. Filtering does not mutate the source snapshot.

A word is a whitespace-separated token containing at least one Unicode letter or
digit. Symbol-only tokens do not count; punctuation inside a token does not split
it. Numbers count as words.

| Title | Word count |
| --- | ---: |
| `This is - a self-explained example` | 5 |
| `C++ and Python` | 3 |
| `Hello — world` | 2 |

### Scraping

Each extraction fetches the front page once, selects its first 30 ranked story
rows, and associates each with its own metadata row. Hiring entries are included.
`discuss` means zero comments; unavailable metrics become `null`. Missing or
invalid required ranks/titles, duplicate ranks, or fewer than 30 story rows fail
the extraction. A malformed entry is never replaced with entry 31.

The source URL is fixed. HTTPX uses a descriptive User-Agent and timeouts of
5 seconds for connect, write, and pool operations, and 10 seconds for reads.
There are no automatic retries within a request.

### Response

| Field | Meaning |
| --- | --- |
| `request_id` | UUID for this API request |
| `fetched_at` | UTC timestamp of the snapshot extraction |
| `cache_hit` | Whether this request reused a fresh snapshot |
| `filter` | Applied filter: `all`, `long`, or `short` |
| `source_count` | 30 for a successful extraction |
| `result_count` | Number of entries after filtering |
| `entries` | Entries containing `number`, `title`, `points`, and `comments` |

`number` is the original front-page rank, not the Hacker News item ID or a new
result position. Metrics are nonnegative integers or `null`. The `X-Request-ID`
header matches the response body ID. Local interactive schemas are available at
[FastAPI docs](http://127.0.0.1:8000/docs).

### Snapshot freshness

The cache stores a complete immutable snapshot, then filters it per request.
The default lifetime is 60 seconds; `CACHE_TTL_SECONDS=0` disables reuse. Hits
preserve `fetched_at` and do not extend the lifetime. Concurrent misses reuse a
successful refresh; failed refreshes are not cached or shared as a common result.
Expired data is not served after a failed refresh. Requests across expiry can
therefore see different stories.

The cache is process-local and clears on restart. See
[ADR-003](adr/0003-snapshot-cache.md) for concurrency, failure, and scaling tradeoffs,
and the [development guide](development.md#cache-configuration) for configuration.

## Usage recording

For each valid filter request, the service awaits one recording attempt before
responding, including cache hits and upstream failures. Invalid filters generate
no usage event. Each successful write commits a separate transaction to
`usage_events`; the request UUID is its primary key.

Events contain `requested_at` (UTC request start), `filter`, `outcome`,
`result_count`, `cache_hit`, and `processing_duration_ms`, together with the UUID.
Outcomes are `success`, `upstream_timeout`, `upstream_error`, or `internal_error`;
result count is null on failure. The monotonic duration stops before recording,
so it excludes the database write and response transmission.

A successful response implies its event was committed. If recording fails, 503
takes precedence over the original result or error, and a diagnostic is logged
without retrying. A lost response may still have a committed event; a client retry
is a new request. These are request counts, not distinct users or exactly-once
processing. See [ADR-002](adr/0002-usage-persistence.md) for the decision and alternatives.

## Errors and health

Errors contain `request_id` and a safe `detail` message. Exception details stay
in application logs.

| HTTP status | Cause |
| --- | --- |
| 422 | Invalid filter or request parameters |
| 504 | Upstream timeout |
| 502 | Upstream HTTP or parsing failure |
| 503 | Usage persistence failure |
| 500 | Unexpected internal failure |

Both the API and web `GET /health` endpoints return `{"status":"ok"}` without
fetching stories or recording usage. They confirm process responsiveness, not
database readiness. Local Compose checks PostgreSQL health separately and gates
API startup on successful migrations.

## Interface behavior

The page provides all three filters, original ranks, result count, and UTC fetch
time. Null metrics appear as an em dash. Titles are plain text because the API
has no story URL field. Loading, empty, error, and retry states are explicit.
Invalid filter URLs show a recovery message without requesting entries.

Each filter selection, including the active filter, makes a new API request.
Server requests use `cache: "no-store"`; ordinary navigation links do not prefetch.
Reloads also count as API requests. See the
[frontend design](architecture.md#frontend-design) for navigation and accessibility choices.
