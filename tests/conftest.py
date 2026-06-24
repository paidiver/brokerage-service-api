"""Pytest fixtures for testing the PostGIS API."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brokerage_service_api.api.app import create_app


@pytest.fixture
def app() -> Generator[FastAPI]:
    """Create a FastAPI app with dependency overrides cleared after tests.

    Yields:
        FastAPI: A FastAPI application instance.
    """
    app = create_app()
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    """Provide a FastAPI test client.

    Args:
        app (FastAPI): The FastAPI application to test.

    Yields:
        TestClient: A test client for the FastAPI application.
    """
    with TestClient(app) as test_client:
        yield test_client
