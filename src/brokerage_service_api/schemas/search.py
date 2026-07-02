"""Schemas for the search API endpoints."""

from pydantic import BaseModel

from brokerage_service_api.schemas.upstream import TaxonWormsLike


class TaxaBulkResponse(BaseModel):
    """Response model for bulk taxonomy search results."""

    results: list[TaxonWormsLike]
