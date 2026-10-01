# ADR-001: Isolate business rules and infrastructure through a modular structure

- Status: Proposed
- Date: 2026-10-01

## Context

The application combines deterministic rules—word counting, filtering, and sorting—with external operations that can fail: downloading HTML and storing usage events. We need to test the rules independently of Hacker News and PostgreSQL while keeping the structure proportional to the project's size.

## Decision

Implement the rules as pure functions and coordinate operations through `EntryService`. Establish boundaries between rules and infrastructure using a small modular structure.

Use classes for components with state, resources, or dependencies: the scraper, cache, service, and usage repository. Define two contracts using `Protocol`: `EntrySource` and `UsageRecorder`. Inject their implementations when constructing the service.

Filtering logic must not depend on FastAPI, HTTPX, or SQLAlchemy. The parser will be a function without network access: it receives HTML and returns entries.

Use OOP where it supports encapsulation and dependency management. Stateless functions do not need to become classes. Place contracts at external boundaries rather than creating an interface for every class. Protocols support static checking and do not replace runtime data validation.

`EntrySource` lets the scraper and its caching wrapper share the same contract. `UsageRecorder` keeps the service independent of SQLAlchemy and allows testing its behavior when writes fail using a test implementation. Test word counting, filtering, and parsing directly as typed functions without additional interfaces.

## Alternatives considered

- Implement everything inside routes: less initial structure, but mixed responsibilities and harder isolated testing.
- Organize the entire application explicitly into ports and adapters: makes boundaries visible. For the current scope, retain those principles with fewer subdivisions and without duplicating models per layer; hexagonal architecture does not require an interface for every class either.
- Create classes and interfaces for every operation: provides uniformity but introduces abstractions without state or meaningful alternative implementations.

## Consequences

- Rules and coordination can be tested with controlled data.
- HTML and persistence changes remain concentrated in their components.
- Contracts and dependency assembly require maintenance.
- The project deliberately combines functions and objects instead of enforcing one paradigm for uniformity.

## Revisit when

New sources, multiple entry points, or business rules make the existing boundaries insufficient.
