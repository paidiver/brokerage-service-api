"""Tests for the source health check endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from brokerage_service_api.api.app import app
from brokerage_service_api.api.v1.source_health import check_source_health
from brokerage_service_api.models.sources import SourceConfig
from fastapi.testclient import TestClient
from starlette import status


@pytest.fixture
def mock_source_config() -> SourceConfig:
    """Create a mock source configuration."""
    return SourceConfig(
        name="test_source",
        label="Test Source",
        base_url="http://test-api:8000/api/",
        enabled=True,
    )


class TestCheckSourceHealth:
    """Tests for the check_source_health function."""

    @pytest.mark.anyio
    async def test_check_source_health_success(self, mock_source_config: SourceConfig) -> None:
        """Test successful health check."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_client.get.return_value = mock_response

        result = await check_source_health(mock_client, mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["source_label"] == "Test Source"
        assert str(result["base_url"]).rstrip("/") == "http://test-api:8000/api"
        assert result["status"] == "ok"

        mock_client.get.assert_called_once_with("http://test-api:8000/api/health/", timeout=5.0)

    @pytest.mark.anyio
    async def test_check_source_health_http_error(self, mock_source_config: SourceConfig) -> None:
        """Test health check with HTTP error."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock())

        result = await check_source_health(mock_client, mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["source_label"] == "Test Source"
        assert str(result["base_url"]).rstrip("/") == "http://test-api:8000/api"
        assert result["status"] == "unhealthy"

    @pytest.mark.anyio
    async def test_check_source_health_request_error(self, mock_source_config: SourceConfig) -> None:
        """Test health check with request error."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.RequestError("Connection refused")

        result = await check_source_health(mock_client, mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["status"] == "unhealthy"

    @pytest.mark.anyio
    async def test_check_source_health_unknown_status(self, mock_source_config: SourceConfig) -> None:
        """Test health check when status field is missing."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # Missing 'status' field
        mock_client.get.return_value = mock_response

        result = await check_source_health(mock_client, mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["status"] == "unknown"


class TestGetSourcesEndpoint:
    """Tests for the get_sources endpoint."""

    def test_get_sources_success(
        self,
        bodc_source: SourceConfig,
        jncc_source: SourceConfig,
    ) -> None:
        """Test successful retrieval of all sources health status."""
        client = TestClient(app, raise_server_exceptions=False)
        mock_sources = [bodc_source, jncc_source]

        with patch("brokerage_service_api.api.v1.source_health.httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client

            # Mock responses for both sources
            mock_response_bodc = MagicMock()
            mock_response_bodc.json.return_value = {"status": "healthy"}

            mock_response_jncc = MagicMock()
            mock_response_jncc.json.return_value = {"status": "healthy"}

            mock_http_client.get.side_effect = [mock_response_bodc, mock_response_jncc]

            # Set sources in app state and make the endpoint call
            app.state.sources = mock_sources
            response = client.get("/api/sources")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "sources" in data

            bodc_result = next(s for s in data["sources"] if s["source_name"] == "bodc")
            jncc_result = next(s for s in data["sources"] if s["source_name"] == "jncc")

            assert bodc_result["status"] == "healthy"
            assert jncc_result["status"] == "healthy"

    def test_get_sources_empty(self) -> None:
        """Test retrieval when no sources are configured."""
        client = TestClient(app, raise_server_exceptions=False)

        with patch("brokerage_service_api.api.v1.source_health.httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client

            # Set empty sources in app state and make the endpoint call
            app.state.sources = []
            response = client.get("/api/sources")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "sources" in data
            assert len(data["sources"]) == 0
