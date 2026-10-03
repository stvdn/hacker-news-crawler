# v1.0.0 release verification

Verified on 2026-10-03. The release candidate was commit `dc5ec28`, checked
out into a clean directory before these checks. An earlier clean HTTPS clone
of `main` at `468fbc8` also passed the pre-release checks. The repository is
public and its HTTPS clone succeeded. This verification covered the local Docker
Compose runtime. The current public demo is deployed with Dokploy and linked in
the [README](../README.md#deployment-and-limitations); the results below describe
the original local checks, not a validation of the remote infrastructure.

## Environment and procedure

- Host: Windows, Intel Core i5-1334U (12 logical processors).
- Native tools: Python 3.13.15, uv 0.12.21, Node.js 24.19.0, pnpm 10.28.1.
- Containers: Docker Engine 29.1.3, Compose 5.0.1, `postgres:17-alpine`,
  Python 3.13 and Node.js 24 images from the committed Dockerfiles.
- From the clean clone, created an ignored `.env` with the required keys from
  `.env.example`, fresh local database credentials, and alternate localhost ports.
  Ran `docker compose --project-name hn-stage8-final up --build -d`.
  Compose started PostgreSQL, completed the one-shot Alembic migration, then
  started the API and web service through their health gates.
- The test database was isolated. The PostgreSQL integration suite created
  and dropped its own databases using `TEST_DATABASE_URL`.

## Results

| Check | Result |
| --- | --- |
| Clean clone and locked dependency installs | Passed: `uv sync --locked` and `pnpm install --frozen-lockfile`. |
| Compose build and startup | Passed: database, API, and web healthy; migration service exited successfully. `alembic_version` was `0001_usage_events`. |
| Health and release version | Passed: both `/health` endpoints returned `{"status":"ok"}`; OpenAPI reported `1.0.0`. |
| Live views | Passed: API returned 30 source entries for `all`, `long`, and `short`; observed result counts were 30, 18, and 12. The three web views each returned HTTP 200. Counts depend on the live front page. |
| Usage persistence | Passed: six smoke requests produced six rows, one miss and five hits. The later benchmark added nine rows, for 15 total, including a row for every warm request. |
| Backend | `ruff check .` passed; `mypy app tests scripts` passed; `pytest` with PostgreSQL reported 142 passed, 1 skipped. The skip is the opt-in live scraper test; the Compose smoke did fetch live Hacker News HTML. |
| Frontend | `pnpm lint`, `pnpm typecheck`, and `pnpm build` passed. Playwright reported 12 passed across desktop and mobile. |

Pytest emitted a dependency deprecation warning from Starlette's test client;
it did not fail a check. The Playwright test server emitted expected diagnostic
logs while exercising synthetic error states.

## Descriptive measurements

Run from the clean clone's `backend` directory with:

```sh
uv run --locked python -m scripts.benchmark_release \
  --fixture-samples 200 --warm-samples 8 \
  --api-url http://127.0.0.1:18000
```

The fixture measurements use saved HTML, no network, and a parsed 30-entry
snapshot for filtering. The API measurements use loopback HTTP to the Compose
API and include the awaited PostgreSQL usage write. The API was restarted
immediately before the run to clear its process-local cache. The script made
one cold request that downloaded live Hacker News HTML, then eight warm
requests within the default 60-second TTL. It verified the cache-hit flags
and 30-entry source count. Times are wall-clock milliseconds; p95 is the
sample at index `floor((n - 1) × 0.95)` after sorting.

| Operation | Samples | Median | p95 | Min–max |
| --- | ---: | ---: | ---: | ---: |
| Parse saved 30-entry HTML | 200 | 29.585 ms | 52.212 ms | 23.663–96.487 ms |
| Filter `all` | 200 | 0.002 ms | 0.004 ms | 0.002–0.052 ms |
| Filter `long` | 200 | 0.049 ms | 0.107 ms | 0.032–1.936 ms |
| Filter `short` | 200 | 0.060 ms | 0.111 ms | 0.038–1.967 ms |
| Full API, cold | 1 | 787.131 ms | — | — |
| Full API, warm | 8 | 40.874 ms | 104.076 ms | 24.933–130.870 ms |

These are observations on one machine, not latency guarantees. The cold
request includes an external network fetch and has only one sample, so it is
not a reliable estimate of typical cold latency. Warm requests avoid the
upstream fetch but still filter and commit a usage event. Host load and the
live upstream can change these times; no timing threshold is used in tests.

## Repository review

The release review used `git diff --check`, inspected the new and modified
files, and checked tracked paths for `.env`, virtual environments, generated
build output, browser reports, Python caches, and bytecode. The generated
Compose `.env` and database volume were isolated to verification and are not
part of the release. The repository is public at
<https://github.com/stvdn/hacker-news-crawler>.
