"""PostgreSQL usage persistence with one transaction and session per event."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Double,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    insert,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models import UsageEvent

metadata = MetaData()
usage_events = Table(
    "usage_events",
    metadata,
    Column("request_id", Uuid, primary_key=True),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    Column("filter", String(5), nullable=False),
    Column("outcome", String(16), nullable=False),
    Column("result_count", Integer, nullable=True),
    Column("processing_duration_ms", Double, nullable=False),
    Column("cache_hit", Boolean, nullable=False),
    CheckConstraint("filter IN ('all', 'long', 'short')", name="valid_filter"),
    CheckConstraint(
        "outcome IN ('success', 'upstream_timeout', "
        "'upstream_error', 'internal_error')",
        name="valid_outcome",
    ),
    CheckConstraint(
        "(outcome = 'success' AND result_count IS NOT NULL "
        "AND result_count BETWEEN 0 AND 30) "
        "OR (outcome <> 'success' AND result_count IS NULL)",
        name="valid_result_count",
    ),
    CheckConstraint(
        "processing_duration_ms >= 0 AND processing_duration_ms < 'Infinity'",
        name="valid_processing_duration",
    ),
)


class PostgresUsageRepository:
    """Return only after the event commits; propagate write failures to the service."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def record(self, event: UsageEvent) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                insert(usage_events).values(
                    request_id=event.request_id,
                    requested_at=event.requested_at,
                    filter=event.filter.value,
                    outcome=event.outcome.value,
                    result_count=event.result_count,
                    processing_duration_ms=event.processing_duration_ms,
                    cache_hit=event.cache_hit,
                )
            )
