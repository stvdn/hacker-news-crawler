# ADR-003: Reuse complete snapshots with bounded freshness

- Status: Accepted — implemented in Stage 7
- Date: 2026-10-01

## Context

Caching is not required for the core functionality, and no load measurements currently demonstrate that it is necessary. At this project's scale, fetching on every request would be a reasonable, simpler approach.

This senior interview project includes a small in-memory cache to demonstrate bounded freshness, concurrent refresh coordination, failure handling, and deterministic testing. It can reduce repeated upstream requests when users switch filters, at the cost of potentially stale data and additional complexity. This is an intentional engineering exercise, not evidence of a production performance requirement.

## Decision

Keep a complete, immutable snapshot of the first 30 entries in process memory for a configurable 60 seconds. Apply filters after retrieving the snapshot. Allow a zero TTL to disable caching for measurements.

The 60-second default is an initial tradeoff between reuse and freshness, not a measured optimum or an explicit requirement. Set `CACHE_TTL_SECONDS=0` to compare latency and upstream request volume with caching disabled. Use those measurements and freshness needs to decide whether to retain caching and how to tune its lifetime. A shared cache would require further justification.

Use a monotonic clock for expiration, measured from the completion of a successful extraction, and an asynchronous lock to coordinate refreshes. Recheck freshness after acquiring the lock to reuse a refresh another request has completed.

Do not cache errors or partial results. If the snapshot has expired and refresh fails, return the error rather than silently serving expired data. Subsequent requests may retry refresh under the same lock; sharing a failed result among them is not guaranteed.

Expose `fetched_at` in UTC. Record each request even when it does not cause a download. The initial deployment uses one API process.

`CachedEntrySource` wraps the scraper at application startup. It checks for a
complete 30-entry snapshot, returns a separate immutable snapshot with per-request
hit metadata, and starts expiry after a successful fetch. Zero TTL bypasses cache
reuse and the refresh lock. Invalid, negative, or non-finite TTL values stop startup.

## Alternatives considered

- No cache: fresher data at the cost of repeated upstream requests and their latency.
- Cache each filter separately: duplicates derived results and can produce views based on different extractions.
- Shared Redis cache: supports reuse across processes but adds another service.
- Serve expired data when refresh fails: improves availability but requires an explicit maximum staleness contract and user-visible indication.

## Consequences

- Requests can reuse a snapshot whose extraction completed less than the configured TTL ago. This does not guarantee the freshness of the data provided by the source itself.
- Restarting clears the cache.
- Multiple processes would maintain independent caches.
- Two selections separated by an expiration can use different snapshots.
- Expiration, concurrency, failures, and immutability require tests.
- The lock prevents simultaneous refreshes within the process, but an upstream outage can still cause consecutive failed attempts. It does not provide rate limiting or complete protection against sustained failures.
- Usage persistence remains necessary for every request; caching does not remove that dependency.

## Revisit when

The application requires multiple processes, fresher data, or availability through serving expired snapshots.
