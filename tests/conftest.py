"""Pytest fixtures for testing the PostGIS API."""

from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from brokerage_service_api.api.app import create_app
from fastapi import FastAPI


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio."""
    return "asyncio"


@pytest.fixture
def app() -> Generator[FastAPI, None, None]:
    """Create a FastAPI app with the DB dependency overridden.

    Yields:
        FastAPI: A FastAPI application instance
    """
    app = create_app()
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide a FastAPI test client.

    Args:
        app (FastAPI): The FastAPI application to test.

    Yields:
        AsyncClient: A test client for the FastAPI application.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url=f"http://testserver:{DEFAULT_PORT}",
    ) as test_client:
        yield test_client
