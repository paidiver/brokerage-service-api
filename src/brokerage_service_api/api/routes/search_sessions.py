"""Session-based search endpoints; legacy search remains compatible."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from redis.exceptions import RedisError

from brokerage_service_api.models.search_model import Results
from brokerage_service_api.schemas.search_session import (
    SearchSessionPage,
    SearchSessionPending,
    SearchSessionRequest,
    SearchSessionState,
)
from brokerage_service_api.utilities.search_session_store import SessionError
from brokerage_service_api.utilities.search_sessions import SearchSessions

router = APIRouter(prefix="/annotations/search/sessions")


async def service(request: Request) -> AsyncIterator[SearchSessions]:
    """Translate storage and session failures without leaking source internals.

    Args:
        request (Request): The incoming request.

    Yields:
        SearchSessions: The search sessions service instance.
    """
    try:
        yield SearchSessions(getattr(request.app.state, "redis", None))
    except SessionError as exc:
        raise HTTPException(
            exc.status,
            detail={"code": exc.code, "message": str(exc)},
            headers=(
                {"Retry-After": "1"}
                if exc.code == "search_session_busy"
                else {"Retry-After": "60"}
                if exc.code == "search_creation_limit"
                else None
            ),
        ) from exc
    except (RedisError, OSError) as exc:
        raise HTTPException(
            503, detail={"code": "search_sessions_unavailable", "message": "Search session storage is unavailable."}
        ) from exc


SessionService = Annotated[SearchSessions, Depends(service)]


def page_response(  # noqa: PLR0913
    request: Request,
    response: Response,
    sessions: SearchSessions,
    state: SearchSessionState,
    page: int,
    result: Results | None,
) -> SearchSessionPage | SearchSessionPending:
    """Build links respecting application root paths and mark pending pages.

    Args:
        request (Request): The incoming request.
        response (Response): The outgoing response.
        sessions (SearchSessions): The search sessions service instance.
        state (SearchSessionState): The current state of the search session.
        page (int): The page number being requested.
        result (Results | None): The search results for the page, if available.

    Returns:
        SearchSessionPage | SearchSessionPending: The response model for the search session page.
    """
    url = str(request.url_for("search_session_page", search_id=state.search_id, page=page))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = url
    if result is None:
        response.status_code = 202
        response.headers["Retry-After"] = "1"
    return sessions.response(state, page, result, url.rsplit("/", 1)[0])


@router.post(
    "",
    response_model=SearchSessionPage | SearchSessionPending,
    status_code=201,
    responses={202: {"model": SearchSessionPending}},
)
async def create_search_session(
    params: SearchSessionRequest, request: Request, response: Response, sessions: SessionService
) -> SearchSessionPage | SearchSessionPending:
    """Create a search and prepare its first page; no upstream snapshot is implied.

    Args:
        params (SearchSessionRequest): The search session request parameters.
        request (Request): The incoming request.
        response (Response): The outgoing response.
        sessions (SessionService): The search sessions service instance.

    Returns:
        SearchSessionPage | SearchSessionPending: The response model for the search session page.
    """
    state = await sessions.create(params)
    try:
        state, result = await sessions.advance(state.search_id, 1)
    except SessionError:
        await sessions.store.delete(state.search_id)
        raise
    return page_response(request, response, sessions, state, 1, result)


@router.get(
    "/{search_id}/pages/{page}",
    response_model=SearchSessionPage | SearchSessionPending,
    responses={202: {"model": SearchSessionPending}},
    name="search_session_page",
)
async def search_session_page(
    search_id: UUID, page: Annotated[int, Path(ge=1)], request: Request, response: Response, sessions: SessionService
) -> SearchSessionPage | SearchSessionPending:
    """Read a cached page or advance a bounded portion of the sorted merge."""
    state, result = await sessions.advance(search_id, page)
    return page_response(request, response, sessions, state, page, result)


@router.delete("/{search_id}", status_code=204)
async def delete_search_session(search_id: UUID, sessions: SessionService) -> None:
    """Release a search; deletion is idempotent and invalidates active writers."""
    await sessions.store.delete(search_id)
