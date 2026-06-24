"""Main brokerage search endpoint."""

from fastapi import APIRouter
from brokerage_service_api.models.search_model import SearchResults,Result

router = APIRouter(prefix="/api/annotations", tags=["Brokerage Search"])




@router.get("/search", response_model=SearchResults)
def brokerage_search():
    pass