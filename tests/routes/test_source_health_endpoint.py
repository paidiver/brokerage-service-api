"""Tests for the source health check endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from brokerage_service_api.api.app import app
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.upstream.annotations import UpstreamError, UpstreamResponse
from brokerage_service_api.utilities.source import check_source_health
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
        upstream_response = UpstreamResponse(
            source=mock_source_config,
            method="GET",
            path="/health/",
            url="http://test-api:8000/api/health/",
            ok=True,
            status_code=200,
            data={"status": "ok"},
            error=None,
        )

        with patch(
            "brokerage_service_api.utilities.source.AnnotationApiClient.health_check",
            new_callable=AsyncMock,
            return_value=upstream_response,
        ) as mock_health_check:
            result = await check_source_health(mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["source_label"] == "Test Source"
        assert str(result["base_url"]).rstrip("/") == "http://test-api:8000/api"
        assert result["status"] == "ok"

        mock_health_check.assert_awaited_once_with()

    @pytest.mark.anyio
    async def test_check_source_health_http_error(self, mock_source_config: SourceConfig) -> None:
        """Test health check with HTTP error."""
        upstream_response = UpstreamResponse(
            source=mock_source_config,
            method="GET",
            path="/health/",
            url="http://test-api:8000/api/health/",
            ok=False,
            status_code=404,
            data=None,
            error=UpstreamError(message="Not Found", type="HTTPStatusError"),
        )

        with patch(
            "brokerage_service_api.utilities.source.AnnotationApiClient.health_check",
            new_callable=AsyncMock,
            return_value=upstream_response,
        ):
            result = await check_source_health(mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["source_label"] == "Test Source"
        assert str(result["base_url"]).rstrip("/") == "http://test-api:8000/api"
        assert result["status"] == "unhealthy"

    @pytest.mark.anyio
    async def test_check_source_health_request_error(self, mock_source_config: SourceConfig) -> None:
        """Test health check with request error."""
        upstream_response = UpstreamResponse(
            source=mock_source_config,
            method="GET",
            path="/health/",
            url="http://test-api:8000/api/health/",
            ok=False,
            status_code=None,
            data=None,
            error=UpstreamError(message="Connection refused", type="RequestError"),
        )

        with patch(
            "brokerage_service_api.utilities.source.AnnotationApiClient.health_check",
            new_callable=AsyncMock,
            return_value=upstream_response,
        ):
            result = await check_source_health(mock_source_config)

        assert result["source_name"] == "test_source"
        assert result["status"] == "unhealthy"

    @pytest.mark.anyio
    async def test_check_source_health_unknown_status(self, mock_source_config: SourceConfig) -> None:
        """Test health check when status field is missing."""
        upstream_response = UpstreamResponse(
            source=mock_source_config,
            method="GET",
            path="/health/",
            url="http://test-api:8000/api/health/",
            ok=True,
            status_code=200,
            data={},
            error=None,
        )

        with patch(
            "brokerage_service_api.utilities.source.AnnotationApiClient.health_check",
            new_callable=AsyncMock,
            return_value=upstream_response,
        ):
            result = await check_source_health(mock_source_config)

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

        upstream_responses = [
            UpstreamResponse(
                source=bodc_source,
                method="GET",
                path="/health/",
                url="http://bodc-api:8000/api/health/",
                ok=True,
                status_code=200,
                data={"status": "healthy"},
                error=None,
            ),
            UpstreamResponse(
                source=jncc_source,
                method="GET",
                path="/health/",
                url="http://jncc-api:8000/api/health/",
                ok=True,
                status_code=200,
                data={"status": "healthy"},
                error=None,
            ),
        ]

        with patch(
            "brokerage_service_api.utilities.source.AnnotationApiClient.health_check",
            new_callable=AsyncMock,
            side_effect=upstream_responses,
        ) as mock_health_check:
            app.state.sources = mock_sources
            response = client.get("/api/sources")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "sources" in data

            bodc_result = next(s for s in data["sources"] if s["source_name"] == "bodc")
            jncc_result = next(s for s in data["sources"] if s["source_name"] == "jncc")

            assert bodc_result["status"] == "healthy"
            assert jncc_result["status"] == "healthy"
            assert mock_health_check.await_count == 2

    def test_get_sources_empty(self) -> None:
        """Test retrieval when no sources are configured."""
        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "brokerage_service_api.utilities.source.AnnotationApiClient.health_check",
            new_callable=AsyncMock,
        ) as mock_health_check:
            app.state.sources = []
            response = client.get("/api/sources")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "sources" in data
            assert len(data["sources"]) == 0
            mock_health_check.assert_not_awaited()
