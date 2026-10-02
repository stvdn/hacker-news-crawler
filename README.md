# Hacker News Crawler

An interview project for scraping and filtering the first 30 Hacker News front-page entries and recording API usage. This repository currently contains the FastAPI health endpoint, entry models and filtering rules, HTML scraper, and development PostgreSQL service. Planned functionality is tracked in [the implementation plan](docs/implementation-plan.md).

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

The CI workflow runs these checks and starts the Compose stack to check `/health`.

Scraper tests use saved synthetic HTML fixtures and HTTPX mock transports;
ordinary checks do not contact Hacker News.

## Scraper

`HackerNewsScraper` accepts a caller-owned `httpx.AsyncClient` and asynchronously
returns an immutable snapshot from `fetch_first_30()`. It fetches the fixed Hacker
News front-page URL once, sends a descriptive User-Agent, and uses explicit
connect/read/write/pool timeouts of 5/10/5/5 seconds. It does not retry or follow
redirects. Snapshots have a UTC extraction-completion time and `cache_hit=false`.

The Beautiful Soup parser uses Python's built-in HTML parser and takes the first
30 story rows, including hiring entries. Each story uses only its adjacent
metadata row. `discuss` means zero comments; unavailable or unreadable metrics
are null. Missing/invalid ranks or titles, duplicate ranks, or fewer than 30
entries raise a parsing error without substituting later stories. Timeout,
HTTP/transport, and parsing errors have separate exception types for the future
API layer. The scraper is not yet wired to an HTTP endpoint.

## Available API

`GET /health` returns `{"status":"ok"}`. The entries endpoint and web interface are not implemented yet.

## Entry rules

| Filter | Selection | Order |
|---|---|---|
| `all` | All fetched entries | Original rank ascending |
| `long` | Titles with more than five words | Comments descending |
| `short` | Titles with five or fewer words | Points descending |

Ties use original rank; unavailable metrics sort last. A word is a
whitespace-separated token containing a Unicode letter or digit.
See the [full rules and examples](docs/implementation-plan.md#api-and-business-rules).

The [architecture decision](docs/adr/0001-modular-architecture.md) explains the
module boundaries.
