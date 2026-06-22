"""Tests for the health endpoint."""

from typing import TYPE_CHECKING

from starlette import status

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_health(client: "TestClient") -> None:
    """Test the health check endpoint."""
    r = client.get("/health")
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == {"status": "ok"}


# def test_health_endpoint_returns_ok() -> None:
#     """Test that the health endpoint returns a successful response."""
#     app = create_app()
#     client = TestClient(app)

#     response = client.get("/health")

#     assert response.status_code == status.
#     assert response.json() == {"status": "ok"}
