"""Main brokerage search endpoint."""

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from brokerage_service_api.models.search_model import SearchResults
from brokerage_service_api.schemas.search import TaxaBulkResponse
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest, TaxaNamePartParams, TaxonWormsLike
from brokerage_service_api.upstream.annotations import AnnotationApiClient, UpstreamResponse
from brokerage_service_api.utilities.search_compiler import fetch_combined_results_from_annotation_apis
from brokerage_service_api.utilities.source import calculate_available_sources

router = APIRouter()


def flatten_unique(results: list[UpstreamResponse[list[TaxonWormsLike]]], key_func: callable) -> list[TaxonWormsLike]:
    """Flatten a list of UpstreamResponse objects and remove duplicates based on a key function.

    Args:
        results (list[UpstreamResponse[list[TaxonWormsLike]]]): List of objects containing lists of TaxonWormsLike.
        key_func (callable): A function that takes a TaxonWormsLike object and returns a unique key for it.

    Returns:
        list[TaxonWormsLike]: A flattened list of unique TaxonWormsLike objects.
    """
    seen = set()
    flattened = []

    for sublist in results:
        if not sublist.data:
            continue

        for item in sublist.data:
            key = key_func(item)

            if key not in seen:
                seen.add(key)
                flattened.append(item)

    return flattened


@router.get(
    "/taxa/ajax_by_name_part/{name_part}",
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

    tasks = [
        AnnotationApiClient(source).search_taxa_by_name_part(name_part, params) for source in available_sources
    ]
    results = await asyncio.gather(*tasks)

    flattened_results = flatten_unique(
        results,
        key_func=lambda item: item.AphiaID,
    )

    return {"results": flattened_results}


@router.get("/annotations/search", response_model=SearchResults)
def brokerage_search(params: Annotated[AnnotationSearchRequest, Query()]) -> SearchResults:
    """Route to provide access to the brokerage search feature.

    Returns:
        SearchResults: A SearchResults instance

    Raises:
        HTTPException: Will return a 500 and simple error message if any issues are encountered upstream.
    """
    try:
        return fetch_combined_results_from_annotation_apis(params=params)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"An error occured whilst fetching the search results. {exc}"
        ) from None
