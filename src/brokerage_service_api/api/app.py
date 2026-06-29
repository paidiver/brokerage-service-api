"""FastAPI module that represent the root of the API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from brokerage_service_api.api.exceptions import DEFAULT_STATUS_CODES, AppException, add_exception_handlers
from brokerage_service_api.api.routes import brokerage_search_router, source_health_router
from brokerage_service_api.registry import get_source_registry


class HealthResponse(BaseModel):
    """Health check response model."""

    ping: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application instance.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Lifespan context manager for the FastAPI application to load sources."""
        try:
            app.state.sources = get_source_registry().list()
            print(f"Loaded sources: {app.state.sources}")
        except FileNotFoundError:
            print("Warning: sources.yaml file not found!")
            app.state.sources = {}
        yield

    app = FastAPI(
        lifespan=lifespan,
        title="Brokerage Service API",
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
        openapi_version="3.0.3",
    )

    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE"],
        allow_headers=["Access-Control-Allow-Headers", "Content-Type", "Authorization", "Access-Control-Allow-Origin"],
        allow_credentials=True,
    )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Handle application exceptions.

        Args:
            request (Request): The incoming request.
            exc (AppException): The application exception to handle.

        Returns:
            JSONResponse: A JSON response with the error details.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "type": exc.__class__.__name__, "path": str(request.url)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle request validation errors.

        Args:
            request (Request): The incoming request.
            exc (RequestValidationError): The validation error to handle.

        Returns:
            JSONResponse: A JSON response with the error details.
        """
        return (
            JSONResponse(
                status_code=400,
                content={
                    "code": "InvalidParameterValue",
                    "description": str(exc),
                },
            )
            if request.url.path.startswith("/v1/ogc")
            else await request_validation_exception_handler(request, exc)
        )

    @app.get("/", include_in_schema=False)
    async def main() -> RedirectResponse:
        """Redirect to docs.

        Returns:
            RedirectResponse: RedirectResponse to the documentation
        """
        return RedirectResponse(url="/docs")

    add_exception_handlers(app, DEFAULT_STATUS_CODES)

    @app.get(
        "/health",
        description="Health Check.",
        summary="Health Check.",
        operation_id="healthCheck",
        tags=["Health Check"],
    )
    async def health() -> dict:
        """Health check.

        Returns:
            dict: A dictionary with a "status" key and "ok" value to indicate the service is healthy.
        """
        return {"status": "ok"}

    app.include_router(
        source_health_router,
        prefix="/api",
        tags=["Health Check"],
    )

    app.include_router(
        brokerage_search_router,
        prefix="/api",
        tags=["Brokerage Search Endpoints"],
    )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
