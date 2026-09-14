"""Application Redis client and FastAPI dependency."""

import os

from fakeredis import FakeAsyncRedis
from fastapi import Request
from redis.asyncio import Redis


def create_redis_client() -> Redis:
    """Create a real or in-memory client according to REDIS_BACKEND."""
    backend = os.getenv("REDIS_BACKEND", "fake").strip().lower()
    if backend == "fake":
        return FakeAsyncRedis(decode_responses=True)
    if backend == "redis":
        return Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    raise ValueError("REDIS_BACKEND must be 'fake' or 'redis'")


def get_redis(request: Request) -> Redis | None:
    """Return the shared client for use with FastAPI Depends(get_redis)."""
    return request.app.state.redis


def redis_enabled() -> bool:
    """Whether response caching is enabled (with either backend)."""
    return os.getenv("REDIS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def redis_ttl() -> int:
    """Return the positive cache lifetime in seconds."""
    ttl = int(os.getenv("REDIS_DEFAULT_TTL_SECONDS", "300"))
    if ttl <= 0:
        raise ValueError("REDIS_DEFAULT_TTL_SECONDS must be positive")
    return ttl
