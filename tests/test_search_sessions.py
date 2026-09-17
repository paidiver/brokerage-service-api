"""Session pagination against independently paginated, interleaved sources."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from brokerage_service_api.api.app import create_app
from brokerage_service_api.schemas.search_session import SearchSessionRequest
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import PaginatedSearchResultItemList
from brokerage_service_api.utilities.search_session_store import SessionError
from brokerage_service_api.utilities.search_sessions import SearchSessions
from brokerage_service_api.utilities.source import SourceRegistry
from fakeredis import FakeAsyncRedis, FakeServer
from pydantic import TypeAdapter

# Fixture sizes and HTTP codes are literal expectations, not implementation constants.
# ruff: noqa: PLR2004

pytestmark = pytest.mark.anyio


def row(number: int, value: int | None = None) -> dict:
    """A real upstream row with nullable metadata and an independent sort value."""
    uid = str(UUID(int=number + 1))
    return {
        "uuid": uid,
        "creation_datetime": (datetime(2020, 1, 1, tzinfo=UTC) + timedelta(seconds=number)).isoformat(),
        "annotation_set_uuid": uid,
        "annotation_set_name": "set",
        "image_set_name": "images",
        "image_set_uuid": uid,
        "image_filename": "image.jpg",
        "image_handle": "https://example.test/image",
        "image_uuid": uid,
        "label_name": f"label {number:06}",
        "label_aphia_id": number if value is None else value,
        "annotation_platform": None,
        "annotation_shape": "point",
        "annotation_coordinates": [[1, 2]],
        "annotation_dimension_pixels": None,
        "annotator_name": None,
    }


@pytest.fixture
async def setup(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[SimpleNamespace]:
    """Provide isolated storage and independently paginated upstream fixtures."""
    sources = [SourceConfig(name=name, label=name, base_url=f"https://{name}.test") for name in ("a", "b")]
    monkeypatch.setattr(
        "brokerage_service_api.utilities.search_sessions.get_source_registry", lambda: SourceRegistry(sources)
    )
    monkeypatch.setenv("SEARCH_SESSION_BATCH_SIZE", "7")
    monkeypatch.setenv("SEARCH_SESSION_PAGES_PER_REQUEST", "5")
    data = {"a": [row(i) for i in range(0, 1500, 2)], "b": [row(i) for i in range(1, 1500, 2)]}
    info = {
        name: {
            "image_sets": [{"uuid": str(UUID(int=index + 1)), "name": f"Images {name}"}],
            "annotation_sets": [{"uuid": str(UUID(int=index + 10)), "name": f"Annotations {name}"}],
            "aphia_ids": [{"aphia_id": 558, "scientific_name": "Porifera", "rank": "Phylum"}],
        }
        for index, name in enumerate(data)
    }
    calls = []
    failure = set()

    async def search(client: object, params: object) -> SimpleNamespace:
        name = client.source.name
        calls.append((name, params))
        if name in failure:
            return SimpleNamespace(ok=False, data=None)
        records = data[name]
        start = (params.page - 1) * params.page_size
        batch = records[start : start + params.page_size]
        summary = {"n_annotations": len(records), "n_images": len(records), "n_annotation_sets": 1, "n_image_sets": 1}
        result = TypeAdapter(PaginatedSearchResultItemList).validate_python(
            {
                "count": len(records),
                "next": "https://unused.test/next" if start + len(batch) < len(records) else None,
                "results": {
                    "annotations": batch,
                    "summary": summary if params.add_summary else None,
                    "info": info[name] if params.add_info else None,
                },
            }
        )
        return SimpleNamespace(ok=True, data=result)

    monkeypatch.setattr("brokerage_service_api.upstream.annotations.AnnotationApiClient.search_annotations", search)
    redis = FakeAsyncRedis(decode_responses=True)
    yield SimpleNamespace(
        service=SearchSessions(redis), redis=redis, data=data, calls=calls, failure=failure, info=info
    )
    await redis.aclose()


async def test_jump_to_68_and_cache(setup: SimpleNamespace) -> None:
    """Jump to 68 and cache."""
    service = setup.service
    params = SearchSessionRequest(
        name_part="cod",
        page_size=20,
        add_summary=True,
        include_descendants=True,
        exclude_annotation_set=[UUID(int=50)],
    )
    state = await service.create(params)
    assert state.count == 1500
    assert all(call.page == 1 for _, call in setup.calls)
    for _ in range(14):
        state, result = await service.advance(state.search_id, 68)
        if result:
            break
    assert result is not None
    assert [record.uuid.int - 1 for record in result.annotations] == list(range(1340, 1360))
    assert result.summary.n_annotations == 1500
    assert all(call.include_descendants for _, call in setup.calls)
    assert all(call.exclude_annotation_set == [UUID(int=50)] for _, call in setup.calls)
    count = len(setup.calls)
    _, first = await service.advance(state.search_id, 1)
    _, again = await service.advance(state.search_id, 68)
    assert [record.uuid.int - 1 for record in first.annotations] == list(range(20))
    assert again == result
    assert len(setup.calls) == count
    assert all(call.page_size == 7 for _, call in setup.calls)
    assert all(not call.add_summary for _, call in setup.calls if call.page > 1)


async def test_ties_nulls_empty_source_and_last_page(setup: SimpleNamespace) -> None:
    """Ties nulls empty source and last page."""
    setup.data["a"] = [row(0, 1), row(2, 1), row(4, 2)]
    setup.data["b"] = [row(1, 1), row(3, 2), row(5, 3)]
    setup.data["b"][-1]["label_aphia_id"] = None
    state = await setup.service.create(SearchSessionRequest(name_part="cod", order_by="label_aphia_id", page_size=2))
    records = []
    for page in range(1, 4):
        state, result = await setup.service.advance(state.search_id, page)
        records += result.annotations
    assert [record.uuid.int - 1 for record in records] == [0, 2, 1, 4, 3, 5]
    response = setup.service.response(state, 3, result, "http://test/pages")
    assert response.next is None
    assert response.previous == "http://test/pages/2"
    with pytest.raises(SessionError, match="outside"):
        await setup.service.advance(state.search_id, 4)
    setup.data["a"] = []
    setup.data["b"] = [row(1)]
    state = await setup.service.create(SearchSessionRequest(name_part="cod", page_size=20))
    _, result = await setup.service.advance(state.search_id, 1)
    assert len(result.annotations) == 1
    setup.data["b"] = []
    state = await setup.service.create(SearchSessionRequest(name_part="cod"))
    _, result = await setup.service.advance(state.search_id, 1)
    assert state.count == 0
    assert result.annotations == []


async def test_failure_retry_preserves_checkpoint(setup: SimpleNamespace) -> None:
    """Failure retry preserves checkpoint."""
    state = await setup.service.create(SearchSessionRequest(name_part="cod", page_size=10))
    state, first = await setup.service.advance(state.search_id, 1)
    setup.failure.add("b")
    with pytest.raises(SessionError) as exc:
        await setup.service.advance(state.search_id, 3)
    assert exc.value.code == "upstream_failed"
    saved = await setup.service.store.load(state.search_id)
    assert saved.generated_through_page == 1
    _, cached = await setup.service.advance(state.search_id, 1)
    assert cached == first
    setup.failure.clear()
    _, result = await setup.service.advance(state.search_id, 3)
    assert [record.uuid.int - 1 for record in result.annotations] == list(range(20, 30))


async def test_invalid_order_and_changed_count(setup: SimpleNamespace) -> None:
    """Invalid order and changed count."""
    state = await setup.service.create(SearchSessionRequest(name_part="cod", page_size=10))
    await setup.service.advance(state.search_id, 1)
    setup.data["a"][7], setup.data["a"][8] = setup.data["a"][8], setup.data["a"][7]
    with pytest.raises(SessionError) as exc:
        await setup.service.advance(state.search_id, 2)
    assert exc.value.code == "upstream_ordering"
    setup.data["a"].pop()
    with pytest.raises(SessionError) as exc:
        await setup.service.advance(state.search_id, 2)
    assert exc.value.code == "upstream_changed"


async def test_selection_expiry_and_size_limit(setup: SimpleNamespace) -> None:
    """Selection expiry and size limit."""
    state = await setup.service.create(SearchSessionRequest(name_part="cod", sources=["a", "A"]))
    assert len(state.sources) == 1
    assert state.count == 750
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod", sources=["unknown"]))
    assert exc.value.status == 422
    key = setup.service.store.key(state.search_id)
    assert 0 < await setup.redis.ttl(key) <= 1800
    setup.service.store.max_bytes = 1
    with pytest.raises(SessionError) as exc:
        await setup.service.advance(state.search_id, 1)
    assert exc.value.code == "search_session_limit"
    assert (await setup.service.store.load(state.search_id)).generated_through_page == 0
    await setup.redis.expire(key, 0)
    with pytest.raises(SessionError) as exc:
        await setup.service.advance(state.search_id, 1)
    assert exc.value.status == 410


async def test_writer_ownership_and_deletion(setup: SimpleNamespace) -> None:
    """Writer ownership and deletion."""
    state = await setup.service.create(SearchSessionRequest(name_part="cod"))
    store = setup.service.store
    async with store.writer(state.search_id) as token:
        with pytest.raises(SessionError) as exc:
            async with store.writer(state.search_id):
                pass
        assert exc.value.code == "search_session_busy"
        lock = store.key(state.search_id) + ":lock"
        await setup.redis.set(lock, "new-owner", ex=30)
        with pytest.raises(SessionError):
            await store.save(state, token)
    assert await setup.redis.get(lock) == "new-owner"
    await setup.redis.delete(lock)
    async with store.writer(state.search_id) as token:
        await store.delete(state.search_id)
        with pytest.raises(SessionError) as exc:
            await store.save(state, token)
        assert exc.value.status == 410


async def test_shared_workers(setup: SimpleNamespace) -> None:
    """Shared workers."""
    server = FakeServer()
    redis1 = FakeAsyncRedis(server=server, decode_responses=True)
    redis2 = FakeAsyncRedis(server=server, decode_responses=True)
    try:
        one, two = SearchSessions(redis1), SearchSessions(redis2)
        state = await one.create(SearchSessionRequest(name_part="cod", page_size=10))
        await one.advance(state.search_id, 1)
        _, result = await two.advance(state.search_id, 2)
        assert [record.uuid.int - 1 for record in result.annotations] == list(range(10, 20))
        count = len(setup.calls)
        await one.advance(state.search_id, 2)
        assert len(setup.calls) == count
    finally:
        await redis1.aclose()
        await redis2.aclose()


async def test_timeout_resumes_partial_page(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resume pending records after a bounded fetch times out."""
    state = await setup.service.create(SearchSessionRequest(name_part="cod", page_size=20))
    original = setup.service.fetch

    async def slow(state: object, source: object) -> None:
        await asyncio.sleep(1)
        await original(state, source)

    monkeypatch.setattr(setup.service, "fetch", slow)
    setup.service.seconds = 0.01
    state, result = await setup.service.advance(state.search_id, 1)
    assert result is None
    assert len(state.pending) > 0
    monkeypatch.setattr(setup.service, "fetch", original)
    setup.service.seconds = 5
    _, result = await setup.service.advance(state.search_id, 1)
    assert [record.uuid.int - 1 for record in result.annotations] == list(range(20))


async def test_http_lifecycle(setup: SimpleNamespace) -> None:
    """Http lifecycle."""
    app = create_app()
    app.state.redis = setup.redis
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/annotations/search/sessions", json={"name_part": "cod", "page_size": 20})
        assert response.status_code == 201, response.text
        body = response.json()
        location = response.headers["Location"]
        assert body["count"] == 1500
        assert body["results"]["annotations"][0]["uuid"] == str(UUID(int=1))
        distant = location.rsplit("/", 1)[0] + "/68"
        pending = await client.get(distant)
        assert pending.status_code == 202
        assert pending.json()["status"] == "preparing"
        assert pending.headers["Retry-After"] == "1"
        invalid = await client.get(location.rsplit("/", 1)[0] + "/999")
        assert invalid.status_code == 404
        delete_url = "/api/annotations/search/sessions/" + body["search_id"]
        assert (await client.delete(delete_url)).status_code == 204
        assert (await client.delete(delete_url)).status_code == 204
        assert (await client.get(location)).status_code == 410
        for params in (
            {"name_part": "cod", "page_size": 0},
            {"name_part": "cod", "page": 68},
            {"name_part": "cod", "sources": []},
        ):
            assert (await client.post("/api/annotations/search/sessions", json=params)).status_code == 422
        app.state.redis = None
        assert (await client.post("/api/annotations/search/sessions", json={"name_part": "cod"})).status_code == 503


async def test_creation_failures_and_rate_limit(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject unavailable sources, bad ordering and excessive search creation."""
    setup.failure.add("b")
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod"))
    assert exc.value.code == "upstream_failed"
    assert await setup.redis.keys("brokerage:search:v1:*") == []
    setup.failure.clear()
    setup.data["a"] = list(reversed(setup.data["a"]))
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod"))
    assert exc.value.code == "upstream_ordering"
    setup.service.creation_limit = 1
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod"))
    assert exc.value.status == 429
    monkeypatch.setattr(
        "brokerage_service_api.utilities.search_sessions.get_source_registry", lambda: SourceRegistry([])
    )
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod"))
    assert exc.value.code == "no_sources"


async def test_initial_timeout(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Creation timeout cancels upstream work and leaves no inaccessible session."""

    async def slow(state: object, source: object) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr(setup.service, "fetch", slow)
    setup.service.seconds = 0.01
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod"))
    assert exc.value.status == 504
    assert await setup.redis.keys("brokerage:search:v1:*") == []


async def test_http_storage_failure(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Storage failures are explicit rather than falling back to private worker state."""
    from unittest.mock import AsyncMock

    from redis.exceptions import ConnectionError as RedisConnectionError

    app = create_app()
    app.state.redis = setup.redis
    monkeypatch.setattr(setup.redis, "hget", AsyncMock(side_effect=RedisConnectionError("internal-host-secret")))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/annotations/search/sessions/{UUID(int=1)}/pages/1")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "search_sessions_unavailable"
    assert "internal-host-secret" not in response.text


async def test_label_order_and_cross_batch_validation(setup: SimpleNamespace) -> None:
    """Use Unicode text order and reject a backwards jump at a batch boundary."""
    setup.data["a"] = [row(i) for i in range(9)]
    setup.data["b"] = []
    state = await setup.service.create(SearchSessionRequest(name_part="cod", order_by="label_name", page_size=7))
    _, result = await setup.service.advance(state.search_id, 1)
    assert [item.label_name for item in result.annotations] == [f"label {i:06}" for i in range(7)]
    setup.data["a"][7]["label_name"] = "aaa"
    with pytest.raises(SessionError) as exc:
        await setup.service.advance(state.search_id, 2)
    assert exc.value.code == "upstream_ordering"


async def test_inconsistent_pagination(setup: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not treat a prematurely empty upstream batch as an exhausted source."""

    async def broken(client: object, params: object) -> SimpleNamespace:
        return SimpleNamespace(
            ok=True,
            data=TypeAdapter(PaginatedSearchResultItemList).validate_python(
                {
                    "count": 10,
                    "next": None,
                    "results": {"annotations": []},
                }
            ),
        )

    monkeypatch.setattr("brokerage_service_api.upstream.annotations.AnnotationApiClient.search_annotations", broken)
    with pytest.raises(SessionError) as exc:
        await setup.service.create(SearchSessionRequest(name_part="cod"))
    assert exc.value.code == "upstream_invalid"


async def test_real_redis_transactions(setup: SimpleNamespace, tmp_path: object) -> None:
    """Exercise atomic checkpoints, expiry and lease fencing against an isolated Redis."""
    import os
    import shutil
    import subprocess

    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError

    if os.getenv("RUN_LOCAL_REDIS_TESTS") != "1" or not shutil.which("redis-server"):
        pytest.skip("Set RUN_LOCAL_REDIS_TESTS=1 with redis-server installed for local Redis validation")
    socket = str(tmp_path / "redis.sock")
    process = subprocess.Popen(
        ["redis-server", "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    redis = Redis(unix_socket_path=socket, decode_responses=True)
    try:
        for _ in range(100):
            try:
                if await redis.ping():
                    break
            except RedisConnectionError:
                await asyncio.sleep(0.02)
        service = SearchSessions(redis)
        state = await service.create(SearchSessionRequest(name_part="cod", page_size=10))
        state, first = await service.advance(state.search_id, 1)
        key = service.store.key(state.search_id)
        ttl = await redis.ttl(key)
        _, second = await service.advance(state.search_id, 2)
        assert [record.uuid.int - 1 for record in second.annotations] == list(range(10, 20))
        assert 0 < await redis.ttl(key) <= ttl
        async with service.store.writer(state.search_id) as token:
            await redis.set(key + ":lock", "replacement", ex=30)
            with pytest.raises(SessionError):
                await service.store.save(state, token)
        assert await redis.get(key + ":lock") == "replacement"
        assert (await service.advance(state.search_id, 1))[1] == first
        await service.store.delete(state.search_id)
        assert not await redis.exists(key)
    finally:
        await redis.aclose()
        process.terminate()
        process.wait(timeout=5)


async def test_info_is_merged_and_retained_on_cached_pages(setup: SimpleNamespace) -> None:
    """Full-search facets survive source pagination, Redis, and another worker."""
    state = await setup.service.create(SearchSessionRequest(name_part="cod", page_size=10, add_info=True))
    _, first = await setup.service.advance(state.search_id, 1)
    assert len(first.info.image_sets) == 2
    assert len(first.info.annotation_sets) == 2
    assert len(first.info.aphia_ids) == 1
    assert first.info.aphia_ids[0].scientific_name == "Porifera"
    assert first.info.aphia_ids[0].rank == "Phylum"
    other_worker = SearchSessions(setup.redis)
    _, second = await other_worker.advance(state.search_id, 2)
    assert second.info == first.info
    calls = len(setup.calls)
    _, cached = await other_worker.advance(state.search_id, 1)
    assert cached.info == first.info
    assert len(setup.calls) == calls
    assert all(params.add_info for _, params in setup.calls if params.page == 1)
    assert all(not params.add_info for _, params in setup.calls if params.page > 1)


async def test_info_handles_missing_sources_empty_results_and_opt_out(setup: SimpleNamespace) -> None:
    """Missing Info is optional, and an empty search can still return available Info."""
    setup.info["b"] = None
    setup.data["a"] = []
    setup.data["b"] = []
    state = await setup.service.create(SearchSessionRequest(name_part="cod", add_info=True))
    _, result = await setup.service.advance(state.search_id, 1)
    assert result.annotations == []
    assert len(result.info.image_sets) == 1
    setup.info["a"] = None
    state = await setup.service.create(SearchSessionRequest(name_part="cod", add_info=True))
    assert (await setup.service.advance(state.search_id, 1))[1].info is None
    state = await setup.service.create(SearchSessionRequest(name_part="cod", add_info=False))
    assert (await setup.service.advance(state.search_id, 1))[1].info is None


async def test_http_info_contract(setup: SimpleNamespace) -> None:
    """Creation and cached GET expose exactly the Info keys consumed by the UI."""
    app = create_app()
    app.state.redis = setup.redis
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/annotations/search/sessions", json={"name_part": "cod", "add_info": True})
        assert response.status_code == 201
        info = response.json()["results"]["info"]
        assert set(info) == {"image_sets", "annotation_sets", "aphia_ids"}
        assert info["image_sets"][0] == setup.info["a"]["image_sets"][0]
        assert info["aphia_ids"] == setup.info["a"]["aphia_ids"]
        cached = await client.get(response.headers["Location"])
        assert cached.status_code == 200
        assert cached.json()["results"]["info"] == info
