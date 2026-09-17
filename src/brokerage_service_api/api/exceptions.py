"""Consistent RFC 9457 errors for framework and application failures."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from brokerage_service_api.schemas.response import ProblemDetails

logger = logging.getLogger(__name__)


def problem_response(
    status_code: int,
    detail: str,
    *,
    code: str | None = None,
    errors: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a safe machine-readable error while retaining HTTP headers."""
    code = code or {
        400: "invalid_parameters",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        422: "invalid_parameters",
        500: "internal_error",
        502: "upstream_failed",
        503: "service_unavailable",
        504: "upstream_timeout",
    }.get(status_code, "request_failed")
    body = ProblemDetails(
        title=HTTPStatus(status_code).phrase, status=status_code, detail=detail, code=code, errors=errors
    )
    return JSONResponse(
        body.model_dump(exclude_none=True),
        status_code=status_code,
        media_type="application/problem+json",
        headers=headers,
    )


def add_exception_handlers(app: FastAPI) -> None:
    """Register one error contract for HTTP, validation and unexpected failures."""

    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        code = detail.get("code") if isinstance(detail, dict) else None
        message = detail.get("message", "The request failed.") if isinstance(detail, dict) else str(detail)
        return problem_response(exc.status_code, message, code=code, headers=exc.headers)

    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()
        ]
        return problem_response(422, "One or more request parameters are invalid.", errors=errors)

    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API exception", exc_info=exc)
        return problem_response(500, "An unexpected error occurred.")

    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(Exception, internal_error)


class AppException(HTTPException):
    """Base application exception."""

    def __init__(self, status_code: int, detail: str) -> None:
        """Initialize an application-scoped HTTP exception."""
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(AppException):
    """Exception raised when an item is not found."""

    def __init__(self, name: str = "Item") -> None:
        """Initialize a not-found exception for a named resource."""
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} not found")


class ValueErrorException(AppException):
    """Exception raised for value errors."""

    def __init__(self, detail: str) -> None:
        """Initialize a value-error exception with a custom message."""
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
