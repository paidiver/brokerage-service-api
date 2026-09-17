"""FastAPI module that represent the root of the API."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from redis.exceptions import RedisError

from brokerage_service_api.api.exceptions import add_exception_handlers
from brokerage_service_api.api.routes import brokerage_search_router, export_router, source_health_router
from brokerage_service_api.api.routes.search_sessions import router as search_sessions_router
from brokerage_service_api.schemas.response import ProblemDetails
from brokerage_service_api.utilities.redis import create_redis_client, redis_enabled, redis_ttl
from brokerage_service_api.utilities.source import get_source_registry


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str


def problem_openapi(app: FastAPI) -> dict:
    """Document problem responses with their actual media type."""
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes, servers=app.servers)
        for path in schema["paths"].values():
            for operation in path.values():
                if not isinstance(operation, dict):
                    continue
                for response in operation.get("responses", {}).values():
                    content = response.get("content", {})
                    if "application/problem+json" in content:
                        content.pop("application/json", None)
        app.openapi_schema = schema
    return app.openapi_schema


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application instance.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Lifespan context manager for the FastAPI application to load sources."""
        try:
            app.state.sources = get_source_registry().list()
            print(f"Loaded sources: {app.state.sources}")
        except FileNotFoundError:
            print("Warning: sources.yaml file not found!")
            app.state.sources = {}
        app.state.redis_ttl = redis_ttl()
        app.state.redis = create_redis_client() if redis_enabled() else None
        try:
            if app.state.redis is not None:
                try:
                    await app.state.redis.ping()
                except (RedisError, OSError):
                    logging.getLogger(__name__).warning("Redis unavailable; continuing without cached responses")
            yield
        finally:
            if app.state.redis is not None:
                await app.state.redis.aclose()

    app = FastAPI(
        lifespan=lifespan,
        title="Brokerage Service API",
        version="0.1.0",
        root_path=os.getenv("FASTAPI_ROOT_PATH", ""),
        openapi_url="/openapi.json",
        docs_url="/docs",
        openapi_version="3.0.3",
        responses={
            code: {
                "model": ProblemDetails,
                "description": "Problem Details",
                "content": {"application/problem+json": {"schema": {"$ref": "#/components/schemas/ProblemDetails"}}},
            }
            for code in (400, 401, 403, 404, 405, 422, 429, 500, 502, 503, 504)
        },
    )

    origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE"],
        allow_headers=["Access-Control-Allow-Headers", "Content-Type", "Authorization", "Access-Control-Allow-Origin"],
        allow_credentials=True,
        expose_headers=["Location", "Retry-After"],
    )

    @app.get("/", include_in_schema=False)
    async def main() -> RedirectResponse:
        """Redirect to docs.

        Returns:
            RedirectResponse: RedirectResponse to the documentation
        """
        return RedirectResponse(url="/docs")

    add_exception_handlers(app)

    @app.get(
        "/health",
        description="Health Check.",
        summary="Health Check.",
        operation_id="healthCheck",
        tags=["Health Check"],
    )
    async def health() -> HealthResponse:
        """Health check.

        Returns:
            dict: A dictionary with a "status" key and "ok" value to indicate the service is healthy.
        """
        return HealthResponse(status="ok")

    app.include_router(
        source_health_router,
        prefix="/api",
        tags=["Sources"],
    )

    app.include_router(
        brokerage_search_router,
        prefix="/api",
        tags=["Brokerage Search Endpoints"],
    )

    app.include_router(search_sessions_router, prefix="/api", tags=["Search Sessions"])

    app.include_router(
        export_router,
        prefix="/api",
        tags=["Brokerage Export Endpoints"],
    )

    app.openapi = lambda: problem_openapi(app)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
