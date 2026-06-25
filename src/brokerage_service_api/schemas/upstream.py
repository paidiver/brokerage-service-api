"""Upstream request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

Deployment = Literal["experiment", "exploration", "mapping", "sampling", "stationary", "survey"]
FaunaAttraction = Literal["baited", "light", "none"]
MarineZone = Literal["atmosphere", "laboratory", "sea surface", "seafloor", "water column"]


class QueryParamModel(BaseModel):
    """Base model for upstream query parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    def to_query_params(self) -> dict[str, JsonValue]:
        """Return parameters using upstream API query names."""
        return self.model_dump(by_alias=True, exclude_none=True)


class PaginationParams(QueryParamModel):
    """Pagination query parameters used by list endpoints."""

    page: int | None = Field(default=None, gt=0)
    page_size: int | None = Field(default=None, gt=0)


class AnnotationSearchParams(PaginationParams):
    """Query parameters for annotation search endpoints."""

    aphia_ids: list[int] | None = Field(default=None, alias="aphia_ids[]")
    calculate_summary: bool | None = None
    deployment: Deployment | None = None
    exclude_annotation_set: list[float] | None = Field(default=None, alias="exclude_annotation_set[]")
    exclude_aphia_ids: list[float] | None = Field(default=None, alias="exclude_aphia_ids[]")
    exclude_image_set: list[float] | None = Field(default=None, alias="exclude_image_set[]")
    fauna_attraction: FaunaAttraction | None = None
    image_set_name: str | None = Field(default=None, min_length=3)
    include_descendants: bool | None = None
    marine_zone: MarineZone | None = None
    max_lat: float | None = None
    max_lon: float | None = None
    min_lat: float | None = None
    min_lon: float | None = None
    name_part: str | None = Field(default=None, min_length=3)
    platform: str | None = Field(default=None, min_length=3)
    project: str | None = Field(default=None, min_length=3)
    return_image_annotation_name_info: bool | None = None


class TaxaNamePartParams(QueryParamModel):
    """Query parameters for WoRMS taxa name-part lookup."""

    combine_vernaculars: bool | None = None


class UpstreamModel(BaseModel):
    """Base model for upstream API responses."""

    model_config = ConfigDict(extra="allow", frozen=True)


ResultT = TypeVar("ResultT", bound=UpstreamModel)


class PaginatedResponse(UpstreamModel, Generic[ResultT]):
    """Paginated upstream response."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[ResultT]


class SearchPaginatedResponse(PaginatedResponse[ResultT], Generic[ResultT]):
    """Paginated upstream response for search endpoints."""

    results: ResultT


class SharedSearchResultItem(UpstreamModel):
    """Shared fields for search result items."""

    uuid: UUID
    creation_datetime: datetime
    annotation_set_name: str
    image_set_name: str
    image_set_uuid: UUID
    image_filename: str
    image_uuid: UUID
    label_name: str
    label_aphia_id: int
    annotation_platform: str | None
    annotation_shape: str
    annotation_coordinates: list[JsonValue]
    annotation_dimension_pixels: float | None
    annotator_name: str | None


class SearchResultItem(SharedSearchResultItem):
    """One row returned by the annotation search endpoint."""

    annotation_set_uuid: UUID


class SearchResultSummary(UpstreamModel):
    """Summary block returned by annotation search."""

    n_annotations: int
    n_images: int
    n_annotation_sets: int
    n_image_sets: int


class SearchResultInfo(UpstreamModel):
    """Info block returned by annotation search."""

    image_sets: list[ImageSetInfo]
    annotations_sets: list[AnnotationSetInfo]
    aphia_ids: list[AphiaIdInfo]


class SearchResultRow(UpstreamModel):
    """Grouped annotation search response."""

    summary: SearchResultSummary | None = None
    info: SearchResultInfo | None = None
    annotations: list[SearchResultItem]


class GroupedSearchResultRow(UpstreamModel):
    """Grouped annotation search response."""

    summary: SearchResultSummary | None = None
    info: SearchResultInfo | None = None
    annotations: dict[UUID, list[SharedSearchResultItem]]


class TaxonWormsLike(UpstreamModel):
    """WoRMS-like taxon lookup result."""

    AphiaID: int
    scientificname: str
    url: str | None = None
    status: str | None = None
    rank: str | None = None
    valid_AphiaID: int | None = None
    valid_name: str | None = None
    modified: datetime | None = None
    cached_at: datetime | None = None
    parent_AphiaID: int | None = None


class AphiaIdInfo(UpstreamModel):
    """Info about a WoRMS Aphia ID returned by the annotations API."""

    aphia_id: int
    scientific_name: str
    rank: str | None = None


class ImageSet(UpstreamModel):
    """Image set returned by the annotations API."""

    id: UUID
    name: str


class ImageSetInfo(UpstreamModel):
    """Info about an image set returned by the annotations API."""

    uuid: UUID
    name: str


class Image(UpstreamModel):
    """Image returned by the annotations API."""

    id: UUID
    filename: str


class AnnotationSetInfo(UpstreamModel):
    """Info about an annotation set returned by the annotations API."""

    uuid: UUID
    name: str


class AnnotationSet(UpstreamModel):
    """Annotation set returned by the annotations API."""

    id: UUID
    name: str


class Annotation(UpstreamModel):
    """Annotation returned by the annotations API."""

    id: UUID
    image_id: UUID
    annotation_platform: str | None = None
    shape: str
    coordinates: JsonValue
    dimension_pixels: float | None = None
    annotation_set_id: UUID


class Label(UpstreamModel):
    """Label returned by the annotations API."""

    id: UUID
    name: str
    parent_label_name: str
    lowest_taxonomic_name: str | None = None
    lowest_aphia_id: int | None = None
    name_is_lowest: bool | None = None
    identification_qualifier: str | None = None
    annotation_set_id: UUID


type PaginatedGroupedSearchResultItemList = SearchPaginatedResponse[GroupedSearchResultRow]
type PaginatedSearchResultItemList = SearchPaginatedResponse[SearchResultRow]
type PaginatedImageSetList = PaginatedResponse[ImageSet]
type PaginatedImageList = PaginatedResponse[Image]
type PaginatedAnnotationSetList = PaginatedResponse[AnnotationSet]
type PaginatedAnnotationList = PaginatedResponse[Annotation]
type PaginatedLabelList = PaginatedResponse[Label]
