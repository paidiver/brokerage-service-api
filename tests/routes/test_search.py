"""Test module for search routes."""

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from starlette import status

from brokerage_service_api.models.sources import SourceConfig
from brokerage_service_api.schemas.upstream import TaxaNamePartParams, TaxonWormsLike
from brokerage_service_api.upstream.annotations import UpstreamResponse

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
        path="/annotations/worms_cache/ajax_by_name_part/crab/",
        url="https://api.bodc.example/annotations/worms_cache/ajax_by_name_part/crab/",
        ok=True,
        status_code=200,
        data=SAMPLE_TAXA,
        error=None,
    )

    upstream_response_2 = UpstreamResponse(
        source=jncc_source,
        method="GET",
        path="/annotations/worms_cache/ajax_by_name_part/crab/",
        url="https://api.jncc.example/annotations/worms_cache/ajax_by_name_part/crab/",
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
        path="/annotations/worms_cache/ajax_by_name_part/nonexistent%20species/",
        url="https://api.bodc.example/annotations/worms_cache/ajax_by_name_part/nonexistent%20species/",
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
