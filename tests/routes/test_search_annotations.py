"""Test the search route behaves as expected in normal/error states."""

import httpx
import pytest
from brokerage_service_api.models.search_model import SearchResults
from brokerage_service_api.utilities.search_compiler import InvalidPageNumberError
from pytest_mock import MockerFixture


@pytest.mark.anyio
async def test_seach_route(mocker: MockerFixture, client: "httpx.AsyncClient") -> None:
    """Test the seach route under normal conditions."""
    mocker.patch(
        "brokerage_service_api.api.routes.search.fetch_combined_results_from_annotation_apis",
        return_value=SearchResults(next="next-url", count=1, previous="prev-url", results={"annotations": []}),
    )
    response = await client.get("/api/annotations/search", params={"aphia_ids": 123})
    expected_status_code = 200
    assert response.status_code == expected_status_code
    assert response.json() == {
        "count": 1,
        "next": "next-url",
        "previous": "prev-url",
        "result_metadata": {"bodc_results": 0, "jncc_results": 0, "total_results": 0},
        "results": {"summary": None, "annotations": []},
    }


@pytest.mark.anyio
async def test_search_router_with_exception_raised(mocker: MockerFixture, client: "httpx.AsyncClient") -> None:
    """Test the seach route returns the expected content if an error is raised."""
    mocker.patch(
        "brokerage_service_api.api.routes.search.fetch_combined_results_from_annotation_apis",
        side_effect=ValueError("Some error being raised!"),
    )
    response = await client.get("/api/annotations/search", params={"aphia_ids": 123})
    expected_status_code_with_error = 500
    assert response.status_code == expected_status_code_with_error
    assert response.json() == {
        "detail": "An error occured whilst fetching the search results. Some error being raised!"
    }


@pytest.mark.anyio
async def test_search_router_with_invalid_page(mocker: MockerFixture, client: "httpx.AsyncClient") -> None:
    """Test the seach route returns the expected content if an invalid page is passed in."""
    mocker.patch(
        "brokerage_service_api.api.routes.search.fetch_combined_results_from_annotation_apis",
        side_effect=InvalidPageNumberError("Some error being raised!"),
    )
    response = await client.get("/api/annotations/search", params={"aphia_ids": 123})
    expected_status_code_with_error = 500
    assert response.status_code == expected_status_code_with_error
    assert response.json() == {"detail": "Invalid page."}
