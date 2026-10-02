"""HTTP request context and safe error responses."""

import json
import logging
from datetime import UTC, datetime
from time import monotonic
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.domain.errors import PersistenceError, UpstreamError, UpstreamTimeoutError
from app.domain.models import RequestContext

logger = logging.getLogger(__name__)


def error_response(
    request: Request, status: int, detail: str, exc: Exception
) -> JSONResponse:
    context = cast(RequestContext, request.state.context)
    if status >= 500:
        logger.error(
            json.dumps(
                {
                    "event": "request_failed",
                    "request_id": str(context.request_id),
                    "status_code": status,
                    "error_type": type(exc).__name__,
                }
            ),
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    return JSONResponse(
        status_code=status,
        content={"request_id": str(context.request_id), "detail": detail},
    )


async def request_context(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    request.state.context = RequestContext(uuid4(), datetime.now(UTC), monotonic())
    try:
        response = await call_next(request)
    except Exception as exc:
        response = error_response(request, 500, "Internal server error", exc)
    response.headers["X-Request-ID"] = str(request.state.context.request_id)
    return response


async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(request, 422, "Invalid request parameters", exc)


async def upstream_error(request: Request, exc: UpstreamError) -> JSONResponse:
    if isinstance(exc, UpstreamTimeoutError):
        return error_response(request, 504, "Hacker News request timed out", exc)
    return error_response(request, 502, "Hacker News entries are unavailable", exc)


async def persistence_error(request: Request, exc: PersistenceError) -> JSONResponse:
    return error_response(request, 503, "Usage recording is unavailable", exc)


def configure_error_handling(app: FastAPI) -> None:
    app.middleware("http")(request_context)
    app.exception_handler(RequestValidationError)(validation_error)
    app.exception_handler(UpstreamError)(upstream_error)
    app.exception_handler(PersistenceError)(persistence_error)
