"""Test module for search routes."""

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from brokerage_service_api.models.sources import SourceConfig
from brokerage_service_api.schemas.upstream import TaxaNamePartParams, TaxonWormsLike
from brokerage_service_api.upstream.annotations import UpstreamResponse
from starlette import status

if TYPE_CHECKING:
    import httpx as httpx_type


# Sample test data
SAMPLE_TAXA = [
    TaxonWormsLike(
        AphiaID=1066,
        scientificname="Crustacea",
        url="https://marinespecies.org/aphia.php?p=taxdetails&id=1066",
        status="accepted",
        rank="Subphylum",
        valid_AphiaID=1066,
        valid_name="Crustacea",
        modified=datetime(2015, 5, 5, 9, 47, 59, 543000),
        cached_at=datetime(2026, 6, 25, 16, 1, 20, 599686),
        parent_AphiaID=1065,
    ),
    TaxonWormsLike(
        AphiaID=1071,
        scientificname="Malacostraca",
        url="https://marinespecies.org/aphia.php?p=taxdetails&id=1071",
        status="accepted",
        rank="Class",
        valid_AphiaID=1071,
        valid_name="Malacostraca",
        modified=datetime(2015, 5, 5, 9, 47, 59, 543000),
        cached_at=datetime(2026, 6, 25, 16, 1, 17, 367613),
        parent_AphiaID=845959,
    ),
]


@pytest.mark.anyio
async def test_search_taxa_by_name_success(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig, jncc_source: SourceConfig
) -> None:
    """Test successful taxonomy search returns results from all sources."""
    upstream_response_1 = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    upstream_response_2 = UpstreamResponse(
        source=jncc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://jncc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    client._transport.app.state.sources = [bodc_source, jncc_source]

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
        side_effect=[upstream_response_1, upstream_response_2],
    ):
        response = await client.get(
            "/api/taxa/ajax_by_name_part/crab",
            params={"combine_vernaculars": "true"},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "results" in data
    assert data["results"][0]["ok"] is True
    assert data["results"][1]["ok"] is True


@pytest.mark.anyio
async def test_search_taxa_with_empty_results(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig
) -> None:
    """Test taxonomy search returns empty results when no matches found."""
    upstream_response = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/nonexistent%20species/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/nonexistent%20species/",
        ok=True,
        status_code=200,
        data=[],
        error=None,
    )

    client._transport.app.state.sources = [bodc_source]

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
        return_value=upstream_response,
    ):
        response = await client.get("/api/taxa/ajax_by_name_part/nonexistent%20species")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["data"] == []


@pytest.mark.anyio
async def test_search_taxa_request_error_handling(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig
) -> None:
    """Test taxonomy search handles request errors gracefully."""
    client._transport.app.state.sources = [bodc_source]
    upstream_response = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=False,
        status_code=None,
        data=None,
        error={"type": "ConnectTimeout", "message": ""},
    )
    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
        return_value=upstream_response,
    ):
        response = await client.get("/api/taxa/ajax_by_name_part/crab")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["ok"] is False
    assert data["results"][0]["status_code"] is None
    assert data["results"][0]["error"]["type"] == "ConnectTimeout"


@pytest.mark.anyio
async def test_search_taxa_http_status_error_handling(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig
) -> None:
    """Test taxonomy search handles HTTP status errors gracefully."""
    client._transport.app.state.sources = [bodc_source]

    upstream_response = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=False,
        status_code=None,
        data=None,
        error={"type": "HTTPStatusError", "message": ""},
    )

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
        return_value=upstream_response,
    ):
        response = await client.get("/api/taxa/ajax_by_name_part/crab")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["ok"] is False
    assert data["results"][0]["status_code"] is None
    assert data["results"][0]["error"]["type"] == "HTTPStatusError"


@pytest.mark.anyio
async def test_search_taxa_passes_params(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig
) -> None:
    """Test that search parameters are correctly passed to the client."""
    upstream_response = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    client._transport.app.state.sources = [bodc_source]
    mock_search = AsyncMock(return_value=upstream_response)

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=lambda: mock_search,
    ):
        await client.get(
            "/api/taxa/ajax_by_name_part/crab",
            params={"combine_vernaculars": "true"},
        )

        mock_search.assert_called()
        call_args = mock_search.call_args
        assert call_args[0][0] == "crab"
        assert isinstance(call_args[0][1], TaxaNamePartParams)
        assert call_args[0][1].combine_vernaculars is True


@pytest.mark.anyio
async def test_search_taxa_response_structure(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig
) -> None:
    """Test that search response has correct structure and types."""
    upstream_response = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    client._transport.app.state.sources = [bodc_source]

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
        return_value=upstream_response,
    ):
        response = await client.get("/api/taxa/ajax_by_name_part/crab")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data, dict)
    assert "results" in data
    assert isinstance(data["results"], list)

    result = data["results"][0]
    assert "source" in result
    assert "method" in result
    assert "path" in result
    assert "url" in result
    assert "ok" in result
    assert "status_code" in result
    assert "data" in result
    assert "error" in result


@pytest.mark.anyio
async def test_search_taxa_filter_by_single_source(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig, jncc_source: SourceConfig
) -> None:
    """Test that sources query parameter filters results to specific source."""
    upstream_response = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    client._transport.app.state.sources = [bodc_source, jncc_source]
    mock_search = AsyncMock(return_value=upstream_response)

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=lambda: mock_search,
    ):
        response = await client.get(
            "/api/taxa/ajax_by_name_part/crab",
            params={"sources": "bodc"},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["source"]["name"] == "bodc"
    mock_search.assert_called_once()


@pytest.mark.anyio
async def test_search_taxa_filter_by_multiple_sources(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig, jncc_source: SourceConfig
) -> None:
    """Test that sources parameter can filter by multiple sources."""
    upstream_response_bodc = UpstreamResponse(
        source=bodc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://bodc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    upstream_response_jncc = UpstreamResponse(
        source=jncc_source,
        method="GET",
        path="/api/annotations/worms_cache/ajax_by_name_part/crab/",
        url="http://jncc-api:8000/api/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    client._transport.app.state.sources = [bodc_source, jncc_source]

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
        side_effect=[upstream_response_bodc, upstream_response_jncc],
    ):
        response = await client.get(
            "/api/taxa/ajax_by_name_part/crab",
            params={"sources": ["bodc", "jncc"]},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    source_names = {result["source"]["name"] for result in data["results"]}
    assert source_names == {"bodc", "jncc"}


@pytest.mark.anyio
async def test_search_taxa_filter_by_invalid_source(
    client: "httpx_type.AsyncClient", bodc_source: SourceConfig, jncc_source: SourceConfig
) -> None:
    """Test that filtering by non-existent source name returns empty results."""
    client._transport.app.state.sources = [bodc_source, jncc_source]

    with patch(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        new_callable=AsyncMock,
    ) as mock_search:
        response = await client.get(
            "/api/taxa/ajax_by_name_part/crab",
            params={"sources": "invalid_source"},
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["results"] == []
    mock_search.assert_not_called()
