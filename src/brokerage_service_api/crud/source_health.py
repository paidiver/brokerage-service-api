"""Api module for the source health check operations."""

import asyncio

import httpx
from fastapi import APIRouter, Request

router = APIRouter()


async def check_source_health(client: httpx.AsyncClient, source: dict) -> dict:
    """Check the health status of a source API.

    Args:
        client (httpx.AsyncClient): The HTTP client to use for the request.
        source (dict): The source configuration dictionary.

    Returns:
        dict: A dictionary with the health status of the source.
    """
    try:
        source_name = source.get("source_name", "unknown")
        source_label = source.get("source_label", source_name)
        base_url = source.get("base_url")

        health_endpoint = f"{base_url}/api/health/"
        response = await client.get(health_endpoint, timeout=5.0)

        response.raise_for_status()

        status = response.json().get("status", "unknown")

        return {"source_name": source_name, "source_label": source_label, "base_url": base_url, "status": status}
    except (httpx.RequestError, httpx.HTTPStatusError):
        return {
            "source_name": source_name,
            "source_label": source_label,
            "base_url": base_url,
            "status": "unhealthy",
        }


@router.get(
    "/sources",
    summary="Get the health status of source APIs",
    description="Retrieve the health status of all configured source APIs.",
)
async def get_sources(request: Request) -> dict:
    """Get the health status of a source API.

    Args:
        request (Request): The incoming request.

    Returns:
        dict: A dictionary with the health status of the source with some other information related to source.
    """
    sources_config = request.app.state.sources
    async with httpx.AsyncClient() as client:
        tasks = []
        for source in sources_config.values():
            tasks.append(check_source_health(client, source))

        results = await asyncio.gather(*tasks)

    return {"sources": results}
