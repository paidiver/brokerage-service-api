"""Public search session contracts and persisted progress."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from brokerage_service_api.models.search_model import Result, SearchResults, Summary
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationOrderBy, AnnotationSearchRequest, SearchResultInfo


class SearchSessionRequest(AnnotationSearchRequest):
    """Immutable filters for a new search; pagination starts at page one."""

    model_config = ConfigDict(extra="forbid")
    sources: list[str] | None = Field(default=None, min_length=1)
    page: Literal[1] = 1
    page_size: int = Field(default=20, ge=1, le=500)
    order_by: AnnotationOrderBy = "annotation_creation_datetime"


class SourceProgress(BaseModel):
    """Independent upstream position and unused batch records."""

    source: SourceConfig
    count: int = 0
    next_page: int = 1
    fetched: int = 0
    buffer: list[Result] = Field(default_factory=list)
    last_record: Result | None = None
    summary: Summary | None = None
    info: SearchResultInfo | None = None


class SearchSessionState(BaseModel):
    """Private state saved atomically with each completed page."""

    search_id: UUID
    params: SearchSessionRequest
    expires_at: datetime
    batch_size: int
    sources: list[SourceProgress]
    generated_through_page: int = 0
    pending: list[Result] = Field(default_factory=list)

    @property
    def count(self) -> int:
        """Return the sum of initial upstream row counts."""
        return sum(source.count for source in self.sources)

    @property
    def total_pages(self) -> int:
        """Return the number of nonempty brokerage pages."""
        return (self.count + self.params.page_size - 1) // self.params.page_size


class SearchSessionPage(SearchResults):
    """Completed brokerage page and session metadata."""

    search_id: UUID
    page: int
    page_size: int
    total_pages: int
    generated_through_page: int
    source_counts: dict[str, int]
    expires_at: datetime


class SearchSessionPending(BaseModel):
    """Progress for a page that needs another bounded request."""

    status: Literal["preparing"] = "preparing"
    search_id: UUID
    page: int
    count: int
    total_pages: int
    generated_through_page: int
    expires_at: datetime
