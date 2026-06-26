"""Tests for the health endpoint."""

from typing import TYPE_CHECKING

import pytest
from starlette import status

if TYPE_CHECKING:
    import httpx


@pytest.mark.anyio
async def test_health(client: "httpx.AsyncClient") -> None:
    """Test the health check endpoint."""
    r = await client.get("/health")
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == {"status": "ok"}
