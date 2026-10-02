"""FastAPI application startup and dependency assembly."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.database import database_url
from app.adapters.scraper import HackerNewsScraper
from app.adapters.usage import PostgresUsageRepository
from app.api.errors import configure_error_handling
from app.api.routes import router
from app.service import EntryService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_async_engine(database_url(), pool_pre_ping=True)
    try:
        async with httpx.AsyncClient() as client:
            app.state.entry_service = EntryService(
                HackerNewsScraper(client),
                PostgresUsageRepository(async_sessionmaker(engine)),
            )
            yield
    finally:
        await engine.dispose()


app = FastAPI(title="Hacker News Crawler API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
configure_error_handling(app)
