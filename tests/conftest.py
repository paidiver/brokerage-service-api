"""Pytest fixtures for testing the PostGIS API."""

from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from brokerage_service_api.api.app import create_app
from brokerage_service_api.models.sources import SourceConfig
from fastapi import FastAPI

DEFAULT_PORT = 8000


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


@pytest.fixture
def bodc_source() -> SourceConfig:
    """Provide a BODC test source configuration.

    Returns:
        SourceConfig: A test configuration for the BODC source.
    """
    return SourceConfig(
        name="bodc",
        label="British Oceanographic Data Centre",
        base_url="http://bodc-api:8000/",
        enabled=True,
    )


@pytest.fixture
def jncc_source() -> SourceConfig:
    """Provide a JNCC test source configuration.

    Returns:
        SourceConfig: A test configuration for the JNCC source.
    """
    return SourceConfig(
        name="jncc",
        label="Joint Nature Conservation Committee",
        base_url="http://jncc-api:8000/",
        enabled=True,
    )
