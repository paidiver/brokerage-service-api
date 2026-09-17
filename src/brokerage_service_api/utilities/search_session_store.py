"""Redis session storage with leased writers and atomic checkpoints."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.exceptions import WatchError

from brokerage_service_api.schemas.search_session import SearchSessionState


class SessionError(Exception):
    """An actionable error with a stable public code."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


class SearchSessionStore:
    """Store one hash per search, so pages and state share one expiry."""

    def __init__(self, redis: Redis, max_bytes: int):
        self.redis = redis
        self.max_bytes = max_bytes

    @staticmethod
    def key(search_id: UUID) -> str:
        """Return a versioned key with a Redis Cluster hash tag."""
        return f"brokerage:search:v1:{{{search_id}}}"

    async def create(self, state: SearchSessionState) -> None:
        """Persist initial progress with an absolute expiration."""
        payload = state.model_dump_json()
        self.check_size(len(payload.encode()))
        key = self.key(state.search_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping={"state": payload, "bytes": len(payload.encode())})
            pipe.expireat(key, state.expires_at)
            await pipe.execute()

    async def load(self, search_id: UUID) -> SearchSessionState:
        """Load progress or report an expired session."""
        payload = await self.redis.hget(self.key(search_id), "state")
        if payload is None:
            raise SessionError(410, "search_session_expired", "Search session expired or no longer exists.")
        return SearchSessionState.model_validate_json(payload)

    async def page(self, search_id: UUID, page: int) -> str | None:
        """Read an immutable completed page."""
        return await self.redis.hget(self.key(search_id), f"page:{page}")

    async def delete(self, search_id: UUID) -> None:
        """Delete pages and progress together."""
        await self.redis.delete(self.key(search_id))

    def check_size(self, size: int) -> None:
        """Bound serialized session storage before writing."""
        if size > self.max_bytes:
            raise SessionError(413, "search_session_limit", "Search session storage limit reached; narrow the search.")

    @asynccontextmanager
    async def writer(self, search_id: UUID) -> AsyncGenerator[str]:
        """A stale writer cannot commit or remove another writer's lease."""
        lock = self.key(search_id) + ":lock"
        token = uuid4().hex
        if not await self.redis.set(lock, token, nx=True, ex=30):
            raise SessionError(409, "search_session_busy", "Another request is preparing this search; retry shortly.")
        try:
            yield token
        finally:
            async with self.redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(lock)
                    if await pipe.get(lock) == token:
                        pipe.multi()
                        pipe.delete(lock)
                        await pipe.execute()
                except WatchError:
                    pass

    async def save(self, state: SearchSessionState, token: str, page_json: str | None = None) -> None:
        """Commit state and an optional page together, only while owning the lease."""
        key = self.key(state.search_id)
        lock = key + ":lock"
        payload = state.model_dump_json()
        async with self.redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(key, lock)
                if await pipe.get(lock) != token:
                    raise SessionError(409, "search_session_busy", "Search writer lease expired; retry the page.")
                previous, previous_size = await pipe.hmget(key, "state", "bytes")
                if previous is None:
                    raise SessionError(410, "search_session_expired", "Search session expired or was deleted.")
                size = int(previous_size) - len(previous.encode()) + len(payload.encode())
                values = {"state": payload}
                if page_json is not None:
                    field = f"page:{state.generated_through_page}"
                    old_page = await pipe.hget(key, field)
                    size += len(page_json.encode()) - (len(old_page.encode()) if old_page else 0)
                    values[field] = page_json
                self.check_size(size)
                values["bytes"] = size
                pipe.multi()
                pipe.hset(key, mapping=values)
                await pipe.execute()
            except WatchError as exc:
                raise SessionError(409, "search_session_busy", "Search changed concurrently; retry the page.") from exc
