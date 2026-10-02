"""Create durable usage events."""

import sqlalchemy as sa
from alembic import op

revision = "0001_usage_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("request_id", sa.Uuid(), primary_key=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filter", sa.String(5), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("processing_duration_ms", sa.Double(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.CheckConstraint("filter IN ('all', 'long', 'short')", name="valid_filter"),
        sa.CheckConstraint(
            "outcome IN ('success', 'upstream_timeout', "
            "'upstream_error', 'internal_error')",
            name="valid_outcome",
        ),
        sa.CheckConstraint(
            "(outcome = 'success' AND result_count IS NOT NULL "
            "AND result_count BETWEEN 0 AND 30) "
            "OR (outcome <> 'success' AND result_count IS NULL)",
            name="valid_result_count",
        ),
        sa.CheckConstraint(
            "processing_duration_ms >= 0 AND processing_duration_ms < 'Infinity'",
            name="valid_processing_duration",
        ),
    )


def downgrade() -> None:
    op.drop_table("usage_events")
