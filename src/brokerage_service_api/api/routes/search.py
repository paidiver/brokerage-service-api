"""Main brokerage search endpoint."""

import asyncio
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from brokerage_service_api.models.search_model import SearchResults
from brokerage_service_api.schemas.search import TaxaBulkResponse
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import (
    AnnotationSearchRequest,
    TaxaCollection,
    TaxaNamePartParams,
    TaxonWormsLike,
)
from brokerage_service_api.upstream.annotations import AnnotationApiClient, UpstreamResponse
from brokerage_service_api.utilities.search_compiler import (
    InvalidPageNumberError,
    fetch_combined_results_from_annotation_apis,
)
from brokerage_service_api.utilities.source import calculate_available_sources

router = APIRouter()


def flatten_unique(results: list[UpstreamResponse[TaxaCollection]], key_func: Callable) -> list[TaxonWormsLike]:
    """Flatten a list of UpstreamResponse objects and remove duplicates based on a key function.

    Args:
        results (list[UpstreamResponse[TaxaCollection]]): List of objects containing lists of TaxonWormsLike.
        key_func (callable): A function that takes a TaxonWormsLike object and returns a unique key for it.

    Returns:
        list[TaxonWormsLike]: A flattened list of unique TaxonWormsLike objects.
    """
    seen = set()
    flattened = []

    for sublist in results:
        if not sublist.ok or sublist.data is None:
            raise HTTPException(
                502, detail={"code": "upstream_failed", "message": "A taxonomy source failed. Please retry."}
            )

        for item in sublist.data.results:
            key = key_func(item)

            if key not in seen:
                seen.add(key)
                flattened.append(item)

    return flattened


@router.get(
    "/taxonomy/worms/taxa/{name_part}",
    summary="Search for taxonomies by name part",
    description="Search for taxonomies by a partial name match.",
    response_model=TaxaBulkResponse,
)
async def search_taxonomies(
    request: Request,
    name_part: str,
    params: Annotated[TaxaNamePartParams, Depends()],
    sources: Annotated[
        list[str] | None,
        Query(description="List of source names to search"),
    ] = None,
) -> TaxaBulkResponse:
    """Search for taxonomies using the external API."""
    available_sources = calculate_available_sources(request, sources)

    async def fetch(source: SourceConfig) -> UpstreamResponse[TaxaCollection]:
        async with AnnotationApiClient(source) as client:
            return await client.search_taxa_by_name_part(name_part, params)

    results = await asyncio.gather(*(fetch(source) for source in available_sources))

    flattened_results = flatten_unique(
        results,
        key_func=lambda item: item.AphiaID,
    )

    return TaxaBulkResponse(count=len(flattened_results), results=flattened_results)


@router.get("/annotations/search", response_model=SearchResults)
def brokerage_search(request: Request, params: Annotated[AnnotationSearchRequest, Query()]) -> SearchResults:
    """Search for annotations across brokerage services.

    Queries both the BODC and JNCC Annotations APIs and returns the
    aggregated search results.

    Results can be ordered using the ``order_by`` field. Supported values are:

    - ``label_aphia_id``
    - ``annotation_creation_datetime``
    - ``label_name``

    Args:
        request: The raw request object.
        params: Search parameters provided as query parameters.

    Returns:
        SearchResults: Aggregated search results.

    Raises:
        HTTPException: If an error occurs during the search, returns an HTTP
            500 response with an error message.
    """
    try:
        return fetch_combined_results_from_annotation_apis(params=params, request=request)
    except InvalidPageNumberError:
        raise HTTPException(
            status_code=404, detail={"code": "invalid_page", "message": "Page is outside the search results."}
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred whilst fetching the search results.") from None
