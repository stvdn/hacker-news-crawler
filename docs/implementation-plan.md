# Hacker News Crawler — Implementation Plan

## Objective and acceptance criteria

Build an interview submission that scrapes the first 30 entries from https://news.ycombinator.com/, filters them according to title length, and persists usage events. Provide a minimal Next.js interface and an independently usable FastAPI API.

The submission is complete when a reviewer can clone the repository, run `docker compose up --build`, use all three views, inspect persisted usage, and run documented automated checks. Do not use the Hacker News API as a substitute for HTML scraping.

Repository name: `hacker-news-crawler`. A Python import package, if needed, uses underscores; the backend application can simply use `app`.

## Stack and architecture

- Frontend: Next.js App Router, TypeScript, Tailwind CSS v4, shadcn/ui, and pnpm.
- Backend: FastAPI, Pydantic, HTTPX, Beautiful Soup using the built-in HTML parser.
- Storage: PostgreSQL, SQLAlchemy async sessions, asyncpg, and Alembic migrations.
- Cache: process memory with a configurable 60-second TTL.
- Verification: pytest, Ruff, mypy, frontend lint/type checks, and Playwright.
- Delivery: Docker Compose and GitHub Actions. Select supported runtime versions at scaffolding, record them, and commit dependency lockfiles.

Use a small modular application with ports-and-adapters boundaries. Organize
HTTP handling, domain contracts/rules, and external adapters into packages;
keep orchestration and dependency assembly at the application root:

```text
Next.js -> FastAPI routes -> EntryService
                              |-- CachedEntrySource -> HackerNewsScraper -> HTML parser
                              |-- pure word-count/filter functions
                              `-- PostgresUsageRepository -> PostgreSQL
```

Repository structure:

```text
backend/
  app/
    main.py
    service.py
    api/
      routes.py
      schemas.py
      errors.py
    domain/
      models.py
      filters.py
      ports.py
      errors.py
    adapters/
      scraper.py
      usage.py
      database.py
      cache.py
  tests/
    conftest.py
    fixtures/
    api/
      test_entries.py
      test_health.py
    domain/
      test_filters.py
      test_models.py
    adapters/
      test_scraper.py
      test_scraper_live.py
    integration/
      conftest.py
      test_usage.py
    test_service.py
  migrations/
frontend/
  src/app/
  src/features/hacker-news/
docs/
  implementation-plan.md
  architecture.md
compose.yaml
README.md
.env.example
.github/workflows/
```

`api/` owns HTTP schemas, routes, request context middleware, and error mapping.
Keep Pydantic request/response schemas in `api/schemas.py` and endpoints in
`api/routes.py`; domain dataclasses remain in `domain/models.py`.
`domain/` owns immutable data, pure filtering, the two port contracts, and shared
application exceptions; it must not import the API, adapters, or their libraries.
`service.py` coordinates the domain and ports without importing concrete adapters.
`adapters/` implements the ports for external access and caching. `main.py` owns
lifespan resources and assembles the service, adapters, routes, and error handling.
Tests mirror these responsibilities under `backend/tests/api/`, `domain/`, and
`adapters/`; service tests stay at the test root. Shared pytest fixtures belong in
the root `conftest.py`, and saved HTML stays in `tests/fixtures/`. Fixtures used
only by one group can live in that group's `conftest.py`.
This is a technical responsibility layout using ports and adapters.

### OOP, interfaces, and patterns

Use classes for state and resource management: `EntryService`, `HackerNewsScraper`, `CachedEntrySource`, and `PostgresUsageRepository`. Use pure functions for parsing, counting words, filtering, and sorting. A stateless word-counting class would add ceremony without improving encapsulation.

Define only two small `typing.Protocol` contracts:

- `EntrySource.fetch_first_30()`: asynchronously return a snapshot containing entries, UTC fetch time, and cache-hit metadata.
- `UsageRecorder.record(event)`: asynchronously persist a usage event.

These interfaces let the service use fake dependencies in tests and let the cache wrap the scraper. Do not introduce interfaces for every class, generic repositories, or inheritance hierarchies. Protocols support static checking; Pydantic validates HTTP boundaries.

Patterns: Dependency Injection for assembly, Adapter for external HTML, Repository for usage persistence, and Decorator for the caching wrapper. Compose dependencies at application startup. The domain rules must not import FastAPI, SQLAlchemy, or HTTPX.

Manage the shared HTTP client and database engine through application lifespan. Create a separate database session for each write; never share a session between concurrent requests.

## API and business rules

`GET /api/v1/entries?filter=all|long|short`, defaulting to `all`.

The JSON response contains `request_id`, `fetched_at`, `cache_hit`, `filter`, `source_count`, `result_count`, and `entries`. Each entry contains `number`, `title`, `points`, and `comments`. Metrics are nonnegative integers or null. `number` is the original front-page rank, not the Hacker News item ID or a newly assigned result position.

| Filter | Selection | Ordering |
|---|---|---|
| all | First 30 entries | Original rank ascending |
| long | More than five title words | Comments descending |
| short | Five or fewer title words | Points descending |

Break metric ties by original rank ascending. Unknown metrics sort after all numeric values. Filtering must not mutate the snapshot.

Count whitespace-separated tokens containing at least one Unicode letter or digit. Symbol-only tokens do not count; punctuation inside a token does not split it. Examples: `This is - a self-explained example` = 5; `C++ and Python` = 3; `Hello — world` = 2. Numbers count as words. Document these assumptions.

Fetch the front page once, select its first 30 ranked story rows, and associate each with its own metadata row. Include hiring entries. Parse `discuss` as zero comments and unavailable metrics as null. Do not silently skip a malformed entry and replace it with entry 31. Missing required ranks/titles or fewer than 30 valid entries produce an upstream parsing error.

Use a fixed source URL, a descriptive User-Agent, and explicit HTTPX timeouts: connect 5 seconds, read 10 seconds, write 5 seconds, and pool 5 seconds. Do not add automatic retries in the first version.

### Cache behavior

Cache the complete immutable snapshot, not individual filtered responses. Default `CACHE_TTL_SECONDS=60`; allow zero to disable caching for measurements. A hit reuses entries, while each request still filters and writes its own usage event.

Use a monotonic clock for expiry, measured from successful extraction completion, and UTC for the public `fetched_at`. Inject a clock callable for deterministic tests. Protect refresh with an async lock and recheck freshness after acquiring it. Concurrent misses share the first successful refresh. A failed refresh does not populate the cache; subsequent attempts remain subject to the same lock.

Do not cache errors or partial results. Do not serve expired data on refresh failure. Restarting clears the cache. Run one API worker initially; multiple workers would have independent caches. Redis is unnecessary for this deployment and is a documented future option for shared caching.

Requests within a cache lifetime normally use the same snapshot. Requests across expiry may see different entries; the application does not promise a permanently fixed snapshot across filter selections.

### Usage storage and errors

An Alembic migration creates a usage-events table with request UUID, UTC request-start timestamp, filter identifier, outcome, result count, duration in milliseconds, and cache-hit flag. Failed crawls use a null result count. Request duration measures application processing up to the persistence step; name/document the field accordingly rather than claiming it includes its own database write.

Write exactly one event per valid filter request, including cache hits and failed upstream attempts. Invalid filters return validation errors without a usage event. Complete the write before sending a successful response. If persistence itself fails, emit a structured application log and return 503; do not claim the event was stored.

HTTP errors: 422 invalid filter, 504 upstream timeout, 502 upstream HTTP/parsing failure, 503 persistence unavailable. Unexpected internal failures return 500. Return safe error messages with a request ID; keep exception details in logs.

## Frontend and development environment

Build one page with a table, three filter controls, result count, fetch timestamp, and loading/error states. Display null metrics as an em dash. Keep business filtering in FastAPI.

Server-side Next.js requests use an internal API base URL. Disable Next.js data caching for these requests and disable filter-link prefetch, so each deliberate selection reaches FastAPI. Usage measures API requests, not guaranteed unique human actions.

Introduce Docker in stage 1 and evolve it alongside the application:

1. Add the backend Dockerfile, Compose services for the API and PostgreSQL, `.dockerignore`, and `.env.example`. Expose a minimal `GET /health` endpoint that confirms the API process is running; it does not check database readiness. Configure PostgreSQL's own health check and a named data volume.
2. Develop FastAPI and Next.js locally with automatic reload by default, using PostgreSQL in Docker. Document the different database hostnames for local execution and the Compose network. Keep the containerized backend runnable as dependencies are added.
3. Add the database repository, schema migration, migration service, and startup dependency gates in stage 5. Starting PostgreSQL early establishes the environment without bringing persistence implementation into stage 1.
4. Add the Next.js Dockerfile and web service in stage 6. Run the available Compose stack at each integration milestone and the complete stack once the frontend exists.

Stage 1 is complete when a reviewer can start the API and PostgreSQL with `docker compose up --build`, reach `GET /health`, and run the initial automated checks using the documented commands.

Final Compose includes PostgreSQL, a one-shot migration service, API, and web. Gate migrations on database health and API startup on successful migration completion. Add application health checks and a named database volume. Use committed `.env.example` placeholders, exclude actual `.env` files, and use non-root application containers. Runtime-generated database data must not enter Git.

## Testing, CI, and performance

- Unit tests: exact five/six-word boundaries, Unicode, whitespace, symbols, hyphens, numeric tokens, sort direction, ties, null metrics, and input immutability.
- Parser fixtures: 30 entries plus an excluded 31st, hiring entries, missing metrics, discuss, singular/plural comments, entities, and malformed required fields.
- Service tests with fake ports: successful requests, upstream failures, and persistence failures.
- Cache tests with a fake clock: initial miss, hit, expiry, disabled cache, concurrent successful refresh, failures not cached, and independent filter results over one snapshot.
- API tests: response schema, default filter, invalid filters, error mapping, request identifiers, and one usage event per valid request.
- PostgreSQL integration tests: apply real migrations to an isolated test database and verify committed events. Do not replace these tests with SQLite.
- Playwright: run all three views against controlled data, verify sorting and filter boundaries, and exercise an error state.
- Keep live Hacker News access out of ordinary tests. Provide an opt-in live smoke check.

Enable GitHub Actions as soon as checks exist. Run backend lint/type checks/tests, PostgreSQL integration tests, frontend lint/type checks/build, and the browser smoke flow as their components are added.

Measure fixture parsing/filtering separately from full API latency. Compare a small documented set of cold and warm cache requests, including usage persistence, without repeatedly loading Hacker News. Record environment, sample count, and observed timings. Do not make unmeasured speed claims or add fragile timing thresholds to correctness tests.

## Staged delivery and Git workflow

Keep one repository and an executable `main`. Use short feature branches, coherent commits, and small pull requests with purpose and verification notes. Tests and documentation accompany each feature. Preserve useful commits; do not fabricate historical progress or leave all tests until the end.

- [x] Stage 1 — Scaffold backend and health endpoint; add the API Dockerfile, Compose API/PostgreSQL services, `.dockerignore`, `.env.example`, initial README, dependency management, lint/type checks, and initial CI. Verify container startup and the health endpoint.
- [x] Stage 2 — Entry models and pure rules, with complete unit tests.
- [x] Stage 3 — Scraper and saved HTML fixtures, including failure cases.
- [x] Stage 4 — Service, entries HTTP endpoint, dependency assembly, and tests; verify the existing API container with the new dependencies. Uses an explicit logging-only usage recorder until Stage 5; successful responses do not yet imply durable persistence.
- [x] Stage 5 — PostgreSQL migration, repository, migration service, startup readiness gates, and integration tests using the existing database service.
- [x] Stage 6 — Next.js interface using pnpm, Tailwind CSS v4, and shadcn/ui; frontend container, integrated Compose startup, and browser tests. Moved ahead of caching.
- [x] Stage 7 — Cache wrapper, configurable TTL, deterministic expiration/concurrency tests, and verification that cache hits persist separate usage events.
- [x] Stage 8 — Clean-clone verification, measurements, complete architecture documentation, and release tag `v1.0.0`.

At each stage, review the diff, run relevant checks, update actual setup instructions, and merge only a working increment. Multiple meaningful commits per stage are expected.

## Documentation and final review

README: purpose, prerequisites, Docker and native startup, configuration, API examples, test commands, how to inspect usage events, and known limitations.

Architecture document: diagram, module responsibilities, dependency direction, and short decisions with context, choice, and consequences. Explain selective OOP/interfaces, PostgreSQL versus SQLite, HTML scraping, cache consistency, missing metrics, and word-count interpretation. Include an honest AI-assistance note describing what was reviewed and validated.

Before submission, clone into a clean directory, follow the README literally, verify migrations and all three views, confirm events persist, and run the checks. Inspect tracked files for secrets or generated artifacts. Ensure the reviewer has repository access, tag the verified commit, and send the repository link with the release tag.
