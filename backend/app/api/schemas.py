"""Validated response schemas for the HTTP boundary."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.models import EntryFilter


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    points: int | None = Field(ge=0)
    comments: int | None = Field(ge=0)


class EntriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: UUID
    fetched_at: AwareDatetime
    cache_hit: bool
    filter: EntryFilter
    source_count: int = Field(ge=0)
    result_count: int = Field(ge=0)
    entries: tuple[EntryResponse, ...]


class ErrorResponse(BaseModel):
    request_id: UUID
    detail: str
