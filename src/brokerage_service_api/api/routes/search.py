"""Main brokerage search endpoint."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from brokerage_service_api.models.search_model import SearchResults
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.utilities.search_compiler import fetch_combined_results_from_annotation_apis

router = APIRouter(prefix="/api/annotations", tags=["Brokerage Search"])


@router.get("/search", response_model=SearchResults)
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
