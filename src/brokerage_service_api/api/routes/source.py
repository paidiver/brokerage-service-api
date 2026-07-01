"""Api module for the source health check operations."""

import asyncio

from fastapi import APIRouter, Request

from brokerage_service_api.utilities.source import check_source_health

router = APIRouter()


@router.get(
    "/sources",
    summary="Get the health status of source APIs",
    description="Retrieve the health status of all configured source APIs.",
)
async def get_sources(request: Request) -> dict:
    """Get the health status of all configured source APIs.

    Args:
        request (Request): The incoming request.

    Returns:
        dict: A dictionary with the health status of each configured source.
    """
    sources_config = request.app.state.sources
    tasks = [check_source_health(source) for source in sources_config]
    results = await asyncio.gather(*tasks)

    return {"sources": results}
