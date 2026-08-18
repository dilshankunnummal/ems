"""
Global exception handlers registered on the FastAPI app instance.

Guarantees that every error response — expected or not — leaves the API
in the same JSON shape defined by `app.shared.responses.envelope`.
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.exceptions import AppException
from app.shared.responses import error_response

logger = structlog.get_logger(__name__)


def _sanitize_errors(errors: list) -> list:
    """Pydantic/Starlette validation errors can include the raw request
    body as `bytes` in the "input" field (e.g. malformed or non-JSON
    bodies). `bytes` isn't JSON-serializable, so JSONResponse would crash
    when trying to return these errors. Decode any bytes to str first.
    """
    for err in errors:
        if isinstance(err.get("input"), bytes):
            err["input"] = err["input"].decode("utf-8", errors="replace")
    return errors


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        logger.warning(
            "app_exception",
            path=str(request.url),
            error_code=exc.error_code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.message, exc.error_code, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _sanitize_errors(exc.errors())
        logger.warning("validation_error", path=str(request.url), errors=errors)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response(
                "Request validation failed.", "VALIDATION_ERROR", errors
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(str(exc.detail), "HTTP_ERROR"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "unhandled_exception", path=str(request.url), error=str(exc), exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(
                "An unexpected error occurred. Please try again later.",
                "INTERNAL_SERVER_ERROR",
            ),
        )
