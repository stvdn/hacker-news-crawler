"""HTTP endpoints and service access."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from app.api.schemas import EntriesResponse, ErrorResponse
from app.domain.models import EntryFilter, RequestContext
from app.service import EntryService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is accepting requests."""
    return {"status": "ok"}


def get_entry_service(request: Request) -> EntryService:
    return cast(EntryService, request.app.state.entry_service)


@router.get(
    "/api/v1/entries",
    response_model=EntriesResponse,
    responses={
        status: {"model": ErrorResponse} for status in (422, 500, 502, 503, 504)
    },
)
async def entries(
    request: Request,
    service: Annotated[EntryService, Depends(get_entry_service)],
    filter: EntryFilter = EntryFilter.ALL,
) -> EntriesResponse:
    context = cast(RequestContext, request.state.context)
    result = await service.get_entries(filter, context)
    return EntriesResponse.model_validate(result)
