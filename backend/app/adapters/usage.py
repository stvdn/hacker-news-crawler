"""Temporary Stage 4 recorder; PostgreSQL persistence arrives in Stage 5."""

import json
import logging
from dataclasses import asdict

from app.domain.models import UsageEvent

logger = logging.getLogger(__name__)


class LoggingUsageRecorder:
    """Emit events for development without claiming durable persistence."""

    async def record(self, event: UsageEvent) -> None:
        logger.warning(
            json.dumps({"event": "usage_not_persisted", **asdict(event)}, default=str)
        )
