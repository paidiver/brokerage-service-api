"""Main brokerage search endpoint."""

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from brokerage_service_api.models.search_model import SearchResults
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest, TaxaNamePartParams, TaxonWormsLike
from brokerage_service_api.upstream.annotations import AnnotationApiClient, UpstreamResponse
from brokerage_service_api.utilities.search_compiler import (
    InvalidPageNumberError,
    fetch_combined_results_from_annotation_apis,
)

router = APIRouter()


class TaxaBulkResponse(BaseModel):
    """Response model for bulk taxonomy search results."""

    results: list[UpstreamResponse[list[TaxonWormsLike]]]


@router.get(
    "/taxa/ajax_by_name_part/{name_part}",
    summary="Search for taxonomies by name part",
    description="Search for taxonomies by a partial name match.",
    response_model=TaxaBulkResponse,
)
async def search_taxonomies(
    request: Request,
    name_part: str,
    sources: list[str] | None = Query(default=None, description="List of source names to search"),  # noqa: B008
    params: TaxaNamePartParams = Depends(),  # noqa: B008
) -> TaxaBulkResponse:
    """Search for taxonomies using the external API.

    Args:
        request (Request): The incoming request.
        name_part (str): The partial name to search for.
        sources (list[str] | None): Optional list of source names to filter the search.
        params (TaxaNamePartParams): The query parameters for the search.

    Returns:
        TaxaBulkResponse: The search results wrapped in a TaxaBulkResponse.
    """
    configured_sources = request.app.state.sources
    if sources:
        available_sources = [source for source in configured_sources if source.name in sources]
    else:
        available_sources = configured_sources
    try:
        tasks = [
            AnnotationApiClient(source).search_taxa_by_name_part(name_part, params) for source in available_sources
        ]
        results = await asyncio.gather(*tasks)
        return {"results": results}
    except (httpx.RequestError, httpx.HTTPStatusError):
        return {"results": []}


@router.get("/annotations/search", response_model=SearchResults)
def brokerage_search(params: Annotated[AnnotationSearchRequest, Query()]) -> SearchResults:
    """Search for annotations across brokerage services.

    Queries both the BODC and JNCC Annotations APIs and returns the
    aggregated search results.

    Results can be ordered using the ``order_by`` field. Supported values are:

    - ``label_aphia_id``
    - ``annotation_creation_datetime``
    - ``label_name``

    Args:
        params: Search parameters provided as query parameters.

    Returns:
        SearchResults: Aggregated search results.

    Raises:
        HTTPException: If an error occurs during the search, returns an HTTP
            500 response with an error message.
    """
    try:
        return fetch_combined_results_from_annotation_apis(params=params)
    except InvalidPageNumberError:
        raise HTTPException(status_code=500, detail="Invalid page.") from None
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"An error occured whilst fetching the search results. {exc}"
        ) from None
