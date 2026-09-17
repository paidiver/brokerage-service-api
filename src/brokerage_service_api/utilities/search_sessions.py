"""Merge sorted source streams into cached brokerage pages."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from time import monotonic, time
from uuid import UUID, uuid4

from pydantic import ValidationError
from redis.asyncio import Redis

from brokerage_service_api.models.search_model import Result, ResultMetadata, Results, Summary
from brokerage_service_api.schemas.search_session import (
    SearchSessionPage,
    SearchSessionPending,
    SearchSessionRequest,
    SearchSessionState,
    SourceProgress,
)
from brokerage_service_api.upstream.annotations import AnnotationApiClient
from brokerage_service_api.utilities.search_compiler import AnnotationsAPIFetcher, merge_search_info
from brokerage_service_api.utilities.search_session_store import SearchSessionStore, SessionError
from brokerage_service_api.utilities.source import UnknownSourceError, get_source_registry


def setting(name: str, default: int, maximum: int) -> int:
    """Read a bounded positive session setting.

    Args:
        name (str): The name of the environment variable to read.
        default (int): The default value if the environment variable is not set.
        maximum (int): The maximum allowed value for the setting.

    Returns:
        int: The bounded positive session setting.
    """
    value = int(os.getenv(name, str(default)))
    if not 0 < value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def sort_key(record: Result, order_by: str) -> tuple[bool, int | str | datetime | None, str, int]:
    """Ascending values, nulls last, then stable source and row UUID.

    Args:
        record (Result): The search result record to generate the sort key for.
        order_by (str): The attribute name to sort by.

    Returns:
        tuple[bool, int | str | datetime | None, str, int]: The sort key tuple.
    """
    value = getattr(record, order_by)
    if isinstance(value, datetime):
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return (value is None, value, record.source, record.uuid.int)


class SearchSessions:
    """Advance a session within bounded time and page budgets.
    Args:
        redis (Redis | None): The Redis client instance for session storage.
    """
    def __init__(self, redis: Redis | None):
        if redis is None:
            raise SessionError(503, "search_sessions_unavailable", "Search sessions require Redis.")
        self.store = SearchSessionStore(redis, setting("SEARCH_SESSION_MAX_BYTES", 16_000_000, 256_000_000))
        self.creation_limit = setting("SEARCH_SESSION_CREATIONS_PER_MINUTE", 60, 10000)
        self.ttl = setting("SEARCH_SESSION_TTL_SECONDS", 1800, 86400)
        self.batch_size = setting("SEARCH_SESSION_BATCH_SIZE", 100, 500)
        self.page_budget = setting("SEARCH_SESSION_PAGES_PER_REQUEST", 10, 100)
        self.seconds = setting("SEARCH_SESSION_REQUEST_SECONDS", 5, 20)

    async def create(self, params: SearchSessionRequest) -> SearchSessionState:
        """Validate source selection and fetch each initial sorted batch.

        Args:
            params (SearchSessionRequest): The search session request parameters.

        Returns:
            SearchSessionState: The initialized search session state.
        """
        registry = get_source_registry()
        try:
            sources = (
                [registry.get(name) for name in dict.fromkeys(params.sources)] if params.sources else registry.list()
            )
        except UnknownSourceError as exc:
            raise SessionError(422, "unknown_source", str(exc)) from exc
        sources = list({source.name: source for source in sources}.values())
        if not sources:
            raise SessionError(503, "no_sources", "No search sources are configured.")
        admission_key = f"brokerage:search:admission:{int(time()) // 60}"
        async with self.store.redis.pipeline(transaction=True) as pipe:
            pipe.incr(admission_key)
            pipe.expire(admission_key, 120)
            admitted, _ = await pipe.execute()
        if admitted > self.creation_limit:
            raise SessionError(429, "search_creation_limit", "Search creation rate exceeded; retry in one minute.")
        state = SearchSessionState(
            search_id=uuid4(),
            params=params,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.ttl),
            batch_size=self.batch_size,
            sources=[SourceProgress(source=source) for source in sources],
        )
        try:
            async with asyncio.timeout(self.seconds):
                responses = await asyncio.gather(
                    *(self.fetch(state, source) for source in state.sources), return_exceptions=True
                )
                for response in responses:
                    if isinstance(response, BaseException):
                        raise response
        except TimeoutError as exc:
            raise SessionError(
                504, "upstream_timeout", "Sources did not respond in time; retry creating the search."
            ) from exc
        await self.store.create(state)
        return state

    async def fetch(self, state: SearchSessionState, source: SourceProgress) -> None:
        """Validate a whole batch before changing its source position.

        Args:
            state (SearchSessionState): The current search session state.
            source (SourceProgress): The progress of the source being fetched.
        """
        initial = source.next_page == 1
        params = AnnotationsAPIFetcher._build_upstream_params(state.params).model_copy(
            update={
                "page": source.next_page,
                "page_size": state.batch_size,
                "add_summary": state.params.add_summary if initial else False,
                "add_info": state.params.add_info if initial else False,
            }
        )
        async with AnnotationApiClient(source.source) as client:
            response = await client.search_annotations(params)
        if not response.ok or response.data is None:
            raise SessionError(502, "upstream_failed", f"Source {source.source.name} failed; retry this request.")
        data = response.data
        if data.count < 0 or (source.next_page > 1 and data.count != source.count):
            raise SessionError(
                409, "upstream_changed", f"Source {source.source.name} count changed; restart the search."
            )
        try:
            records = [
                AnnotationsAPIFetcher._construct_result_from_annotation(row, source.source.name)
                for row in data.results.annotations
            ]
        except ValidationError as exc:
            raise SessionError(
                502, "upstream_invalid", f"Source {source.source.name} returned invalid records."
            ) from exc
        fetched = source.fetched + len(records)
        if fetched > data.count or (not records and fetched < data.count) or bool(data.next) != (fetched < data.count):
            raise SessionError(
                502, "upstream_invalid", f"Source {source.source.name} returned inconsistent pagination."
            )
        previous = source.last_record
        for record in records:
            if previous is not None and sort_key(record, state.params.order_by) <= sort_key(
                previous, state.params.order_by
            ):
                raise SessionError(
                    502,
                    "upstream_ordering",
                    f"Source {source.source.name} must sort by {state.params.order_by}, nulls last, then row UUID. "
                    "Text comparison must match Unicode code point order.",
                )
            previous = record
        source.count = data.count
        source.fetched = fetched
        source.next_page += 1
        source.buffer = records
        source.last_record = previous
        if initial and state.params.add_info:
            source.info = data.results.info
        if data.results.summary is not None and initial:
            source.summary = Summary(**data.results.summary.model_dump())

    async def advance(self, search_id: UUID, page: int) -> tuple[SearchSessionState, Results | None]:
        """Prepare up to the requested page, checkpointing bounded work.

        Args:
            search_id (UUID): The unique identifier of the search session.
            page (int): The page number to advance to.

        Returns:
            tuple[SearchSessionState, Results | None]: The updated search session state and the results for the requested page, if available.
        """
        state = await self.store.load(search_id)
        if page < 1 or page > max(1, state.total_pages):
            raise SessionError(404, "invalid_page", "Page is outside the search results.")
        cached = await self.store.page(search_id, page)
        if cached is not None:
            return state, Results.model_validate_json(cached)
        async with self.store.writer(search_id) as token:
            state = await self.store.load(search_id)
            cached = await self.store.page(search_id, page)
            if cached is not None:
                return state, Results.model_validate_json(cached)
            stop = min(page, state.generated_through_page + self.page_budget)
            deadline = monotonic() + self.seconds
            while state.generated_through_page < stop and monotonic() < deadline:
                remaining = state.count - state.generated_through_page * state.params.page_size
                target = min(state.params.page_size, remaining)
                try:
                    async with asyncio.timeout(max(0, deadline - monotonic())):
                        while len(state.pending) < target:
                            for source in state.sources:
                                if not source.buffer and source.fetched < source.count:
                                    await self.fetch(state, source)
                            candidates = [source for source in state.sources if source.buffer]
                            winner = min(
                                candidates, key=lambda source: sort_key(source.buffer[0], state.params.order_by)
                            )
                            state.pending.append(winner.buffer.pop(0))
                            # Yield for cancellation even if all records are already buffered.
                            await asyncio.sleep(0)
                except TimeoutError:
                    await self.store.save(state, token)
                    break
                summaries = [source.summary for source in state.sources if source.summary is not None]
                result = Results(
                    annotations=state.pending,
                    summary=sum(summaries) if len(summaries) == len(state.sources) else None,
                    info=merge_search_info([source.info for source in state.sources])
                    if state.params.add_info
                    else None,
                )
                state.pending = []
                state.generated_through_page += 1
                await self.store.save(state, token, result.model_dump_json())
            cached = await self.store.page(search_id, page)
            return state, Results.model_validate_json(cached) if cached is not None else None

    @staticmethod
    def response(
        state: SearchSessionState, page: int, result: Results | None, base_url: str
    ) -> SearchSessionPage | SearchSessionPending:
        """Expose page data or preparation progress without private source state.

        Args:
            state (SearchSessionState): The current search session state.
            page (int): The page number being requested.
            result (Results | None): The results for the requested page, if available.
            base_url (str): The base URL for constructing pagination links.

        Returns:
            SearchSessionPage | SearchSessionPending: The page data or preparation progress.
        """
        if result is None:
            return SearchSessionPending(
                search_id=state.search_id,
                page=page,
                count=state.count,
                total_pages=state.total_pages,
                generated_through_page=state.generated_through_page,
                expires_at=state.expires_at,
            )
        counts = {source.source.name: source.count for source in state.sources}
        return SearchSessionPage(
            search_id=state.search_id,
            page=page,
            page_size=state.params.page_size,
            count=state.count,
            total_pages=state.total_pages,
            generated_through_page=state.generated_through_page,
            source_counts=counts,
            expires_at=state.expires_at,
            results=result,
            result_metadata=ResultMetadata(total_results=state.count, results_from_individual_sources=counts),
            next=f"{base_url}/{page + 1}" if page < state.total_pages else None,
            previous=f"{base_url}/{page - 1}" if page > 1 else None,
        )
