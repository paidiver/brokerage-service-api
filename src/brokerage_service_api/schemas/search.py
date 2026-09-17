"""Schemas for the search API endpoints."""

from brokerage_service_api.schemas.response import CollectionResponse
from brokerage_service_api.schemas.upstream import TaxonWormsLike


class TaxaBulkResponse(CollectionResponse[TaxonWormsLike]):
    """Response model for bulk taxonomy search results."""

    results: list[TaxonWormsLike]
