"""Custom exceptions for the PostGIS API."""

import logging
from collections.abc import Callable
from fastapi import FastAPI
from fastapi import HTTPException
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def exception_handler_factory(status_code: int) -> Callable:
    """Create a FastAPI exception handler from a status code.

    Args:
        status_code (int): The HTTP status code to return when the exception is raised.

    Returns:
        Callable: A FastAPI exception handler function that returns a JSON response with the given status code
    """

    def handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle exceptions by returning a JSON response with the specified status code.

        Args:
            request (Request): The incoming HTTP request that caused the exception.
            exc (Exception): The exception that was raised.

        Returns:
            JSONResponse: A JSON response containing the exception details and the specified HTTP status code.
        """
        logger.error(exc, exc_info=True)
        return JSONResponse(content={"detail": str(exc)}, status_code=status_code)

    return handler


def add_exception_handlers(app: FastAPI, status_codes: dict[type[Exception], int]) -> None:
    """Add exception handlers to the FastAPI app.

    Args:
        app (FastAPI): The FastAPI application instance to which the exception handlers will be added.
        status_codes (dict[type[Exception], int]): A dictionary mapping exception types to HTTP status
            codes. The keys should be exception classes, and the values should be the corresponding HTTP status codes.
    """
    for exc, code in status_codes.items():
        app.add_exception_handler(exc, exception_handler_factory(code))


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


DEFAULT_STATUS_CODES = {
    Exception: status.HTTP_500_INTERNAL_SERVER_ERROR,
}
