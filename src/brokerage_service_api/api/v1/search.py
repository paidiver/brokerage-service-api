"""Module to handle search requests."""

import asyncio

import httpx
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from brokerage_service_api.schemas.upstream import TaxaNamePartParams, TaxonWormsLike
from brokerage_service_api.upstream.annotations import AnnotationApiClient, UpstreamResponse

router = APIRouter()


# async def get_taxas(
#     client: httpx.AsyncClient,
#     source: SourceConfig,
#     name_part: str,
#     combine_vernaculars: bool = False,
# ) -> list[dict]:
#     """Search for taxonomies using the external API.

#     Args:
#         client (httpx.AsyncClient): The HTTP client to use for the request.
#         source (SourceConfig): The source configuration object.
#         name_part (str): The partial name to search for.
#         combine_vernaculars (bool): Whether to include vernacular matching. Defaults to False.

#     Returns:
#         list[dict]: A list of dictionaries containing the search results.
#     """
#     base_url = str(source.base_url).rstrip("/")
#     search_endpoint = f"{base_url}/annotations/worms_cache/ajax_by_name_part/{name_part}"

#     try:
#         params = {"combine_vernaculars": combine_vernaculars}
#         response = await client.get(search_endpoint, params=params, timeout=5.0)
#         response.raise_for_status()
#         return response.json()
#     except (httpx.RequestError, httpx.HTTPStatusError):
#         return []

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
    params: TaxaNamePartParams = Query(),
) -> TaxaBulkResponse:
    """Search for taxonomies using the external API.

    Args:
        request (Request): The incoming request.
        name_part (str): The partial name to search for.
        params (TaxaNamePartParams): The query parameters for the search.

    Returns:
        TaxaBulkResponse: The search results wrapped in a TaxaBulkResponse.
    """
    sources = request.app.state.sources

    try:
        tasks = [
            AnnotationApiClient(source).search_taxa_by_name_part(name_part, params)
            for source in sources
        ]
        results = await asyncio.gather(*tasks)
        print(f"Results from all sources: {results}")  # Debugging print statement
        return {"results": results}
    except (httpx.RequestError, httpx.HTTPStatusError):
        return {"results": []}
