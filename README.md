# Hacker News Crawler

An interview project for scraping and filtering the first 30 Hacker News front-page entries and recording API usage. This repository currently provides the FastAPI entries endpoint, filtering service, HTML scraper, and development PostgreSQL service. Stage 4 logs usage events; durable PostgreSQL recording is planned for Stage 5. Planned functionality is tracked in [the implementation plan](docs/implementation-plan.md).

## Requirements

- Docker with Compose for the containerized stack.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for native backend development. uv installs the pinned Python 3.13 interpreter when needed.

The project uses Python 3.13 and uv 0.12.21. Dependencies are resolved in `backend/uv.lock`.

## Run with Docker

From the repository root:

```sh
docker compose up --build
```

Open <http://127.0.0.1:8000/health>. The response is `{"status":"ok"}`. This endpoint confirms that the API process is responding; it does not test database readiness. PostgreSQL has a separate Compose health check. Its data persists in the named `postgres_data` volume.

The development defaults work without a `.env` file. Copy `.env.example` to `.env` to change the password or host ports. The example password is for local development only. Stop the stack with `docker compose down`; add `--volumes` only when you intend to remove local database data.

## Run the API locally

Start PostgreSQL in Docker, then run the API with reload:

```sh
docker compose up -d db
cd backend
uv sync --locked
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For local backend execution, PostgreSQL is available at `localhost:5433`; Compose services use `db:5432`. The health endpoint does not query PostgreSQL.

## Checks

From `backend`:

```sh
uv run --locked ruff check .
uv run --locked mypy app tests
uv run --locked pytest
```

The CI workflow runs these checks and starts the Compose stack to check `/health`
and entries parameter validation without contacting Hacker News.

Scraper and application assembly tests use saved synthetic HTML fixtures and
HTTPX mock transports. Service and API tests use fake source/usage adapters to
check response schemas, filtering, request IDs, concurrent requests, one event per
valid request, and error mapping. Ordinary checks do not contact Hacker News.

To opt into a single live fetch from `backend`:

```sh
HN_LIVE_SMOKE=1 uv run --locked pytest tests/adapters/test_scraper_live.py
```

In PowerShell, set `$env:HN_LIVE_SMOKE = "1"`, run
`uv run --locked pytest tests/adapters/test_scraper_live.py`, then remove the opt-in with
`Remove-Item Env:HN_LIVE_SMOKE`. The live check depends on upstream availability.

## Scraper

The scraper reads the first 30 Hacker News front-page entries, including hiring
posts, and preserves their original ranks. `discuss` means zero comments;
unavailable metrics become `null`. Invalid or incomplete pages fail instead of
returning partial results. A shared HTTPX client is created at application startup
and closed at shutdown. Each valid entries request currently fetches a new page;
caching is planned for Stage 6.

See [Checks](#checks) for fixture tests and the optional live smoke check, and the
[implementation plan](docs/implementation-plan.md#api-and-business-rules) for
detailed scraping requirements.

## Available API

`GET /health` returns `{"status":"ok"}`.

`GET /api/v1/entries?filter=all|long|short` defaults to `all`. For example:

```sh
curl 'http://127.0.0.1:8000/api/v1/entries?filter=long'
```

The response contains `request_id` (UUID), `fetched_at` (UTC), `cache_hit`,
`filter`, `source_count`, `result_count`, and `entries`. Entries contain their
original `number`, `title`, `points`, and `comments`; unavailable metrics are
`null`. `source_count` is 30 for a successful scrape; `result_count` is the number
remaining after filtering. `cache_hit` is currently always false in the running
application. Interactive API documentation is at <http://127.0.0.1:8000/docs>.

Errors contain `request_id` and a safe `detail` message. The `X-Request-ID` response
header matches the body ID. Invalid filters return 422, upstream timeouts 504,
upstream HTTP/parsing failures 502, usage-recording failures 503, and unexpected
internal errors 500. Exception details stay in application logs.

### Stage 4 usage recording

The service awaits exactly one recording attempt for each valid filter request,
including failed upstream attempts. Invalid filters create no usage event.
The temporary `LoggingUsageRecorder` emits a JSON warning with
`event: "usage_not_persisted"`; it does **not** store events in PostgreSQL.
Inspect these events with `docker compose logs api` or the local API console.
Successful responses at this stage confirm logging only, not durable storage.

Events include the request UUID, UTC request-start timestamp (`requested_at`),
filter, outcome (`success`, `upstream_timeout`, `upstream_error`, or
`internal_error`), result count (null on failure), cache-hit flag, and
`processing_duration_ms`. This monotonic duration ends immediately before usage
recording, so it excludes the recorder's own write and response transmission.
Each request gets its own event, even when a source reports a cache hit. If
recording raises an error, 503 takes precedence over the original result/error,
with a structured diagnostic log and no retry.

Stage 5 replaces the temporary recorder with PostgreSQL persistence and schema
migrations. The web interface is planned for Stage 7.

## Entry rules

| Filter | Selection | Order |
|---|---|---|
| `all` | All fetched entries | Original rank ascending |
| `long` | Titles with more than five words | Comments descending |
| `short` | Titles with five or fewer words | Points descending |

Ties use original rank; unavailable metrics sort last. A word is a
whitespace-separated token containing a Unicode letter or digit.
See the [full rules and examples](docs/implementation-plan.md#api-and-business-rules).

The backend uses a small ports-and-adapters structure: `app/api/` handles HTTP,
`app/domain/` holds data, pure rules, contracts, and exceptions, and
`app/adapters/` handles scraping and usage recording. `app/service.py` coordinates
the flow; `app/main.py` assembles dependencies and manages their lifecycle.
Tests mirror these groups under `backend/tests/api/`, `domain/`, and `adapters/`.
Service tests, shared pytest fixtures (`conftest.py`), and saved HTML (`fixtures/`)
remain at the test root.

The [architecture decision](docs/adr/0001-modular-architecture.md) explains these
boundaries, and the [implementation plan](docs/implementation-plan.md#stack-and-architecture)
shows the complete directory layout, including future components.
