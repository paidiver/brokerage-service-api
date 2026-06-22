"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from brokerage_service_api.api.app import create_app


def test_health_endpoint_returns_ok() -> None:
    """Test that the health endpoint returns a successful response."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
