"""Api module for the source health check operations."""

import asyncio

import httpx
from fastapi import APIRouter, Request

from brokerage_service_api.models.sources import SourceConfig

router = APIRouter()


async def check_source_health(client: httpx.AsyncClient, source: SourceConfig) -> dict:
    """Check the health status of a source API.

    Args:
        client (httpx.AsyncClient): The HTTP client to use for the request.
        source (SourceConfig): The source configuration object.

    Returns:
        dict: A dictionary with the health status of the source.
    """
    try:
        base_url = str(source.base_url).rstrip("/")

        health_endpoint = f"{base_url}/health/"
        response = await client.get(health_endpoint, timeout=5.0)

        response.raise_for_status()

        status = response.json().get("status", "unknown")

        return {"source_name": source.name, "source_label": source.label, "base_url": source.base_url, "status": status}
    except (httpx.RequestError, httpx.HTTPStatusError):
        return {
            "source_name": source.name,
            "source_label": source.label,
            "base_url": source.base_url,
            "status": "unhealthy",
        }


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
    async with httpx.AsyncClient() as client:
        tasks = [check_source_health(client, source) for source in sources_config]
        results = await asyncio.gather(*tasks)

    return {"sources": results}
