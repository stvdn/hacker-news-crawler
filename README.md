# Hacker News Crawler

An interview project for scraping and filtering the first 30 Hacker News front-page entries and recording API usage. This repository provides a Next.js interface, the FastAPI entries endpoint, filtering service, HTML scraper, and durable PostgreSQL usage recording with Alembic migrations. See the [implementation plan](docs/implementation-plan.md) and [architecture](docs/architecture.md).

## Requirements

- Docker with Compose for the containerized stack.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for native backend development. uv installs the pinned Python 3.13 interpreter when needed.
- Node.js 24 and pnpm 10.28.1 for native frontend development.

The project uses Python 3.13 and uv 0.12.21. Dependencies are resolved in `backend/uv.lock`.
The frontend uses Next.js 16, React 19, Tailwind CSS v4, and shadcn/ui;
dependencies are resolved in `frontend/pnpm-lock.yaml`. Enable pnpm through
`corepack enable` if needed; `frontend/package.json` pins its version.

## Run with Docker

From the repository root, copy `.env.example` to `.env` and set
`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` for your local database.
Then run:

```sh
docker compose up --build
```

Open <http://127.0.0.1:3000> for the three story views. The API is available at
<http://127.0.0.1:8000/docs>. Both <http://127.0.0.1:8000/health> and
<http://127.0.0.1:3000/health> return `{"status":"ok"}` without fetching stories.
These endpoints confirm their process is responding; they do not test database
readiness. PostgreSQL has a separate Compose health check. Its data persists in
the named `postgres_data` volume.

Compose waits for PostgreSQL to become healthy, runs the one-shot `migrate`
service (`alembic upgrade head`), then starts the API only if migrations succeed.
The web service waits for API health before starting. The migration container
exiting with code 0 is expected. Application and migration
containers run as a non-root user.

Compose requires explicit database names, users, and passwords from `.env` or the
shell; none has a fallback. `.env.example` contains local development examples and
optional host ports. Single-quote `.env` passwords containing literal `$` or `#`.
Changing these values in `.env` does not rename an existing database or user,
or change its password; existing databases must also be updated in PostgreSQL.
Stop the stack with
`docker compose down`; add `--volumes` only when you intend to remove local data.

## Run the API locally

After configuring `.env` as above, start PostgreSQL in Docker, configure the API,
then run it with reload (POSIX shell; substitute your user, database, password,
and host port):

```sh
docker compose up -d db
cd backend
uv sync --locked
export DATABASE_URL='postgresql+asyncpg://YOUR_USER@localhost:5433/YOUR_DATABASE'
export DATABASE_PASSWORD='your configured POSTGRES_PASSWORD'
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For local backend execution, PostgreSQL is available at `localhost:5433`; Compose services use `db:5432`. The health endpoint does not query PostgreSQL.

In PowerShell, replace the `export` commands with:

```powershell
$env:DATABASE_URL = 'postgresql+asyncpg://YOUR_USER@localhost:5433/YOUR_DATABASE'
$env:DATABASE_PASSWORD = 'your configured POSTGRES_PASSWORD'
```

Both the API and Alembic require `DATABASE_URL`; an unset or blank value stops
startup with a configuration error. There is no application default URL or password.
The URL must use `postgresql+asyncpg`. You can include a URL-encoded password in
the URL, or set `DATABASE_PASSWORD` to a raw password; when set, it overrides the
URL's password and must not be blank. SQLAlchemy constructs the connection URL
without interpreting special characters in that separate password.
`DATABASE_USER` and `DATABASE_NAME` likewise override URL fields when set and
must not be blank. These separate settings accept raw values, including reserved
URL characters. Compose passes the configured database name, user, and password
separately; API and migration services share the same configuration.
The root `.env` configures Compose; native Python commands do not load it.
Apply migrations before starting a native API process. Database sessions are
created per write, and the shared engine is disposed at application shutdown.

### Migration files

Keep `backend/alembic.ini` and the entire `backend/migrations/` source directory
in version control: `env.py` runs migrations, `script.py.mako` is the template for
new revisions, and `versions/` contains the schema history. These are source
files, not database data. Do not commit `.env`, credentials, or Python caches.
Alembic normally scaffolds this environment with `alembic init -t async migrations`;
this repository's environment was written explicitly for its async setup and
environment-based configuration. Do not rerun `init` for an existing checkout.

For a future schema change, update the SQLAlchemy metadata, run
`uv run --locked alembic revision --autogenerate -m "describe the schema change"`
from `backend`, and review the generated `upgrade()` and `downgrade()` before
applying and committing the revision. Autogeneration creates candidate revisions;
it does not regenerate `env.py`.

## Run the frontend locally

Start the API as described above, then use another terminal:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open <http://127.0.0.1:3000>. Native development defaults to
`API_BASE_URL=http://127.0.0.1:8000`; override it in `frontend/.env.local` if
needed. This is a server-only setting, never a `NEXT_PUBLIC_` variable. Compose
sets `API_BASE_URL=http://api:8000` and exposes the page on `WEB_PORT` (default
3000). The root `.env` configures Compose and is not loaded by native Next.js.

## Checks

### Frontend

From `frontend`, run:

```sh
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

Run `uv sync --locked` in `backend` first and make `uv` available on PATH.
Playwright starts a production Next.js server on port 3100 and a test-only
FastAPI server on port 8100, so those ports must be free. It checks desktop and
mobile views, five/six-word boundaries, sorting, null/zero metrics, loading,
empty/error/retry states, keyboard navigation, and one API event per selection
without hover prefetching. The test server uses the real service and filters
with synthetic entries and an in-memory recorder; it never contacts Hacker News
or PostgreSQL. Database persistence is covered separately by backend integration
tests. CI runs frontend checks and uploads browser traces on failure.

The frontend renders API results without implementing business filtering. Plain
navigation links disable prefetching and fetch on every selection, including the
active filter. Server requests use `cache: "no-store"`; no frontend data cache
is used. Counts and UTC fetch times describe each response. Titles are plain
text because the API does not supply story URLs. Usage counts API requests,
not unique human actions; reloads also record requests. Invalid filter URLs show
a recovery message without making an entries request. Web health checks do not
generate usage events.

shadcn/ui components live in `frontend/src/components/ui`, with aliases in
`frontend/components.json`. Tailwind v4 uses `@tailwindcss/postcss` and CSS theme
tokens in `frontend/src/app/globals.css`; there is no Tailwind v3 config file.

### Backend

From `backend`:

```sh
uv run --locked ruff check .
uv run --locked mypy app tests
uv run --locked pytest
```

The CI workflow runs these checks with a PostgreSQL service and starts the Compose
stack to check `/health` and entries parameter validation without contacting
Hacker News.

Scraper and application assembly tests use saved synthetic HTML fixtures and
HTTPX mock transports. Service and API tests use fake source/usage adapters to
check response schemas, filtering, request IDs, concurrent requests, one event per
valid request, and error mapping. Ordinary checks do not contact Hacker News.

PostgreSQL integration tests skip unless `TEST_DATABASE_URL` is set. To run them
against the existing Docker database from `backend` (POSIX shell):

```sh
TEST_DATABASE_URL='postgresql+asyncpg://YOUR_USER:URL_ENCODED_PASSWORD@localhost:5433/YOUR_DATABASE' uv run --locked pytest tests/integration
```

Substitute your configured database, user, and URL-encoded password. In PowerShell, set
`$env:TEST_DATABASE_URL` to that URL, run
`uv run --locked pytest tests/integration`, then
`Remove-Item Env:TEST_DATABASE_URL`. The test user must have `CREATEDB` permission
(the Compose development user does). Each test creates a uniquely named database,
applies real migrations, and drops only that database afterward. Tests verify
committed values, concurrent writes, transaction rollback, API persistence/error
handling, schema drift, and migration downgrade/upgrade. CI enables these tests.

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
and closed at shutdown. The API reuses a complete snapshot for up to 60 seconds
by default; every valid request still filters and records its own usage event.

See [Checks](#checks) for fixture tests and the optional live smoke check, and the
[implementation plan](docs/implementation-plan.md#api-and-business-rules) for
detailed scraping requirements.

## Snapshot caching

`CACHE_TTL_SECONDS` defaults to `60`. Set it in the root `.env` for Compose, or
as an environment variable before starting a native API process. Use `0` to
disable reuse and fetch on every request. Fractional seconds are accepted;
blank, negative, nonnumeric, and non-finite values stop API startup. After changing
the Compose setting, run `docker compose up -d api` to recreate the API if needed.

The cache stores the complete immutable set of 30 entries; each request applies
its own filter. Expiry uses a monotonic clock starting when extraction finishes.
Hits do not extend the lifetime. Concurrent misses share the first successful
refresh through an async lock. Failed refreshes and incomplete results are never
cached, and expired stories are not returned when a refresh fails. Waiting
requests can try another refresh, one at a time; failures are not shared or retried
automatically within a request.

Every valid request still records usage before responding, including cache hits.
The response's `cache_hit` describes that request, while `fetched_at` remains the
time of the original extraction. Different views can share a snapshot within its
lifetime; a selection after expiry can show different stories. Next.js continues
to make an uncached API request for every selection.

The cache is scoped to one API process and is cleared on restart. Compose runs
one worker; additional workers would each maintain their own cache. A shared
cache such as Redis is a future option, not part of this deployment.

Tests use fake clocks and controlled async gates for expiry, concurrent success
and failure, cancellation, disabled caching, and independent filters. API and
PostgreSQL integration tests verify separate usage events for hits and misses.

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
remaining after filtering. `cache_hit` is false for a fetch and true when a request
reuses a fresh snapshot. A hit preserves the original `fetched_at`.
Interactive API documentation is at <http://127.0.0.1:8000/docs>.

Errors contain `request_id` and a safe `detail` message. The `X-Request-ID` response
header matches the body ID. Invalid filters return 422, upstream timeouts 504,
upstream HTTP/parsing failures 502, usage-recording failures 503, and unexpected
internal errors 500. Exception details stay in application logs.

### Usage recording

The service awaits exactly one recording attempt for each valid filter request,
including failed upstream attempts. Invalid filters create no usage event.
`PostgresUsageRepository` commits each event to `usage_events` before the response.
The request UUID is the primary key, timestamps use PostgreSQL `timestamptz`, and
database constraints enforce valid filters, outcomes, counts, and durations.
Inspect stored events from the repository root:

```sh
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM usage_events ORDER BY requested_at DESC LIMIT 20;"'
```

Events include the request UUID, UTC request-start timestamp (`requested_at`),
filter, outcome (`success`, `upstream_timeout`, `upstream_error`, or
`internal_error`), result count (null on failure), cache-hit flag, and
`processing_duration_ms`. This monotonic duration ends immediately before usage
recording, so it excludes the recorder's own write and response transmission.
Each request gets its own event, even when a source reports a cache hit. If
recording raises an error, 503 takes precedence over the original result/error,
with a structured diagnostic log and no retry.

Persistence failures appear in `docker compose logs api` or the native API console.
The web interface was added in Stage 6 and the snapshot cache in Stage 7.

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
shows the complete directory layout.

## Release verification

The [Stage 8 verification record](docs/release-verification.md) reports the clean
clone, Compose, migration, automated check, and timing results for `v1.0.0`.
To repeat the descriptive fixture timing from `backend`, run:

```sh
uv run --locked python -m scripts.benchmark_release --fixture-samples 200
```

To measure the full API, restart one API process with the default positive cache
TTL, then add
`--api-url http://127.0.0.1:8000 --warm-samples 8`. This makes one live Hacker
News request, then eight cached API requests. Each API request still writes a
usage event. The script requires a newly started API process and fails if the
first response is already cached.

## Known limitations

The scraper depends on Hacker News HTML and fails a whole snapshot when required
story fields are missing. The cache is process-local, expires after 60 seconds
by default, and does not serve stale data after refresh failure. The page does
not link to stories because the API exposes titles but not story URLs. Usage
events count API requests, not distinct people. The delivered Compose setup is
for running the application locally; this repository does not define a cloud
deployment.
