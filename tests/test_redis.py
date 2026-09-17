"""Tests for Redis configuration and application lifecycle."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
from brokerage_service_api.api.app import create_app
from brokerage_service_api.utilities.redis import create_redis_client, get_redis
from fastapi import Request
from redis.asyncio import Redis


@pytest.mark.anyio
async def test_fake_redis_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default client supports storage, expiry and request injection without a server."""
    monkeypatch.delenv("REDIS_BACKEND", raising=False)
    monkeypatch.setenv("REDIS_ENABLED", "true")
    app = create_app()
    async with app.router.lifespan_context(app):
        client = get_redis(Request({"type": "http", "app": app}))
        assert await client.ping()
        await client.set("key", "value", ex=60)
        assert await client.get("key") == "value"
        assert await client.ttl("key") > 0
        await client.expire("key", 0)
        assert await client.get("key") is None
    async with app.router.lifespan_context(app):
        assert await app.state.redis.get("key") is None


@pytest.mark.anyio
async def test_real_redis_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real mode configures an async client with the requested URL."""
    monkeypatch.setenv("REDIS_BACKEND", "redis")
    port, database = 6380, 2
    monkeypatch.setenv("REDIS_URL", f"redis://redis.example:{port}/{database}")
    client = create_redis_client()
    try:
        assert isinstance(client, Redis)
        options = client.connection_pool.connection_kwargs
        assert options["host"] == "redis.example"
        assert options["port"] == port
        assert options["db"] == database
        assert options["decode_responses"] is True
    finally:
        await client.aclose()


def test_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration mistakes fail explicitly."""
    monkeypatch.setenv("REDIS_BACKEND", "invalid")
    with pytest.raises(ValueError, match="REDIS_BACKEND"):
        create_redis_client()


@pytest.mark.anyio
@pytest.mark.parametrize("startup_fails", [False, True])
async def test_client_cleanup(monkeypatch: pytest.MonkeyPatch, startup_fails: bool) -> None:
    """Close connections on shutdown even when the startup ping fails."""
    monkeypatch.setenv("REDIS_ENABLED", "true")
    client = AsyncMock()
    if startup_fails:
        client.ping.side_effect = ConnectionError("Redis unavailable")
    monkeypatch.setattr("brokerage_service_api.api.app.create_redis_client", lambda: client)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.redis is client
    client.aclose.assert_awaited_once()


@pytest.mark.anyio
async def test_disabled_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled caching starts without constructing a client."""
    monkeypatch.setenv("REDIS_ENABLED", "false")
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.redis is None


@pytest.mark.anyio
async def test_sources_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache hits avoid upstream calls and respect parameters and expiration."""
    import httpx

    monkeypatch.setenv("REDIS_BACKEND", "fake")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    ttl = 42
    monkeypatch.setenv("REDIS_DEFAULT_TTL_SECONDS", str(ttl))
    check = AsyncMock(
        return_value={
            "source_name": "test",
            "source_label": "Test",
            "base_url": "https://test.example/",
            "status": "ok",
        }
    )
    monkeypatch.setattr("brokerage_service_api.api.routes.source.check_source_health", check)
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.sources = [{"name": "test"}]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/api/sources?detail=a")
            second = await client.get("/api/sources?detail=a")
            assert first.status_code == HTTPStatus.OK
            assert first.json() == second.json()
            check.assert_awaited_once()
            keys = await app.state.redis.keys("brokerage:*")
            assert 0 < await app.state.redis.ttl(keys[0]) <= ttl
            check.reset_mock()
            await app.state.redis.expire(keys[0], 0)
            await client.get("/api/sources?detail=a")
            check.assert_awaited_once()
            check.reset_mock()
            await client.get("/api/sources?detail=b")
            check.assert_awaited_once()
            check.reset_mock()
            app.state.sources = [{"name": "changed"}]
            await client.get("/api/sources?detail=b")
            check.assert_awaited_once()


@pytest.mark.anyio
async def test_sources_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis read and write failures leave successful upstream responses intact."""
    import httpx
    from redis.exceptions import ConnectionError as RedisConnectionError

    monkeypatch.setenv("REDIS_ENABLED", "true")
    redis = AsyncMock()
    redis.ping.side_effect = RedisConnectionError("offline")
    redis.get.side_effect = RedisConnectionError("offline")
    redis.set.side_effect = RedisConnectionError("offline")
    monkeypatch.setattr("brokerage_service_api.api.app.create_redis_client", lambda: redis)
    check = AsyncMock(
        return_value={
            "source_name": "test",
            "source_label": "Test",
            "base_url": "https://test.example/",
            "status": "ok",
        }
    )
    monkeypatch.setattr("brokerage_service_api.api.routes.source.check_source_health", check)
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.sources = [{"name": "test"}]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            requests = 2
            for _ in range(requests):
                response = await client.get("/api/sources")
                assert response.status_code == HTTPStatus.OK
                assert response.json() == {
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "source_name": "test",
                            "source_label": "Test",
                            "base_url": "https://test.example/",
                            "status": "ok",
                        }
                    ],
                }
        assert check.await_count == requests
        redis.set.assert_awaited()
