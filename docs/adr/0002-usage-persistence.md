# ADR-002: Confirm usage persistence before returning a successful response

- Status: Proposed
- Date: 2026-10-01

## Context

The exercise requires storing the request timestamp and applied filter. We must decide whether recording usage is part of a successful operation or whether a record can be lost without affecting the response.

The requirements do not mandate withholding entries during a database outage. This availability dependency is a deliberate choice to guarantee that successful responses have persisted usage records.

## Decision

For each request with a valid filter, persist an event before returning the response. Also record requests whose scraping fails and requests served from cache. Reject invalid filters through validation without creating a usage event.

If persistence fails, return HTTP 503 and emit a diagnostic log. Do not claim the event was stored. When the event for a scraping failure is successfully persisted, return the corresponding scraping error afterward.

Events represent API requests, not unique users or necessarily unique human actions.

PostgreSQL is the planned implementation. This record addresses the persistence guarantee and its failure implications; product selection is an implementation detail.

## Alternatives considered

- Record usage on a best-effort basis and respond even if recording fails: preserves query availability but permits event loss.
- Record usage in a background task within the process: reduces response waiting time, but process termination can lose records.
- Use a durable queue: decouples processing from storage writes but adds infrastructure and recovery mechanisms.

## Consequences

- A successful response implies that its event was committed to the database.
- Response latency includes the write, and availability depends on PostgreSQL. Even with a fresh cached snapshot, a failed event write prevents a successful response.
- If the response is lost after the commit, the event may exist even though the client did not receive the result.
- A client retry is a new request. This decision does not guarantee exactly-once processing.
- A persistence failure can prevent recording the attempt; a diagnostic log is not equivalent to a committed database event.

## Revisit when

Traffic volume, write latency, or availability requirements justify durable asynchronous persistence.
