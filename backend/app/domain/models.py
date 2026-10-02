"""Immutable data shared by entry sources and domain rules."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class EntryFilter(StrEnum):
    ALL = "all"
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class Entry:
    """A story with its original front-page rank and optional metrics."""

    number: int
    title: str
    points: int | None
    comments: int | None

    def __post_init__(self) -> None:
        if type(self.number) is not int or self.number < 1:
            raise ValueError("entry number must be a positive integer")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("entry title must be nonempty")
        for name, value in (("points", self.points), ("comments", self.comments)):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"entry {name} must be a nonnegative integer or null")


@dataclass(frozen=True, slots=True)
class EntrySnapshot:
    """One complete fetch, which can be shared by multiple filter requests."""

    entries: tuple[Entry, ...]
    fetched_at: datetime
    cache_hit: bool

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise ValueError("snapshot entries must be a tuple")
        if (
            self.fetched_at.tzinfo is None
            or self.fetched_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("snapshot fetched_at must be UTC")


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: UUID
    started_at: datetime
    started_monotonic: float


class UsageOutcome(StrEnum):
    SUCCESS = "success"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_ERROR = "upstream_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class UsageEvent:
    request_id: UUID
    requested_at: datetime
    filter: EntryFilter
    outcome: UsageOutcome
    result_count: int | None
    processing_duration_ms: float
    cache_hit: bool


@dataclass(frozen=True, slots=True)
class EntriesResult:
    request_id: UUID
    fetched_at: datetime
    cache_hit: bool
    filter: EntryFilter
    source_count: int
    result_count: int
    entries: tuple[Entry, ...]
