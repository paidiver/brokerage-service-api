"""Api module for the source health check operations."""

import asyncio
import hashlib
import json
import logging

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from redis.exceptions import RedisError

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
    client = getattr(request.app.state, "redis", None)
    cache_key_data = {
        "path": request.url.path,
        "query": sorted(request.query_params.multi_items()),
        "sources": jsonable_encoder(sources_config),
    }
    cache_key = (
        "brokerage:sources:v1:" + hashlib.sha256(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()
    )
    if client is not None:
        try:
            cached = await client.get(cache_key)
            if cached is not None:
                response = json.loads(cached)
                if isinstance(response, dict) and isinstance(response.get("sources"), list):
                    return response
        except (RedisError, OSError, ValueError, TypeError):
            logging.getLogger(__name__).warning("Redis cache read failed; checking upstream sources")
    tasks = [check_source_health(source) for source in sources_config]
    results = await asyncio.gather(*tasks)

    response = {"sources": results}
    if client is not None:
        try:
            await client.set(cache_key, json.dumps(jsonable_encoder(response)), ex=request.app.state.redis_ttl)
        except (RedisError, OSError):
            logging.getLogger(__name__).warning("Redis cache write failed; returning upstream response")
    return response
