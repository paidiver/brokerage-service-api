"""Reusable client to access the annotations API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, cast
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter, ValidationError

from brokerage_service_api.models.sources import SourceConfig
from brokerage_service_api.schemas.upstream import (
    Annotation,
    AnnotationSearchParams,
    AnnotationSet,
    Image,
    ImageSet,
    JsonValue,
    Label,
    PaginatedAnnotationList,
    PaginatedAnnotationSetList,
    PaginatedGroupedSearchResultItemList,
    PaginatedImageList,
    PaginatedImageSetList,
    PaginatedLabelList,
    PaginatedSearchResultItemList,
    PaginationParams,
    QueryParamModel,
    TaxaNamePartParams,
    TaxonWormsLike,
)

ResponseDataT = TypeVar("ResponseDataT")


@dataclass(frozen=True, slots=True)
class UpstreamError:
    """Error details returned from an upstream request."""

    message: str
    type: str


@dataclass(frozen=True, slots=True)
class UpstreamResponse(Generic[ResponseDataT]):
    """Response envelope for an upstream request."""

    source: SourceConfig
    method: str
    path: str
    url: str
    ok: bool
    status_code: int | None
    data: ResponseDataT | None = None
    error: UpstreamError | None = None


class AnnotationApiClient:
    """Shared annotations API client configured for one upstream source."""

    def __init__(
        self,
        source: SourceConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create an annotations API client.

        Args:
            source: Upstream source configuration.
            transport: Optional httpx transport, primarily useful for tests.
        """
        self.source = source
        self._client = httpx.AsyncClient(
            base_url=str(source.base_url),
            timeout=source.timeout.to_httpx_timeout(),
            transport=transport,
            follow_redirects=True,
        )

    async def __aenter__(self) -> AnnotationApiClient:
        """Return this client as an async context manager."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Close the underlying HTTP client."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def search_annotations(
        self,
        params: AnnotationSearchParams | None = None,
    ) -> UpstreamResponse[PaginatedSearchResultItemList]:
        """Search annotations.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            "/api/annotations/search/",
            response_schema=PaginatedSearchResultItemList,
            params=params,
        )

    async def search_annotations_grouped(
        self,
        params: AnnotationSearchParams | None = None,
    ) -> UpstreamResponse[PaginatedGroupedSearchResultItemList]:
        """Search annotations grouped by upstream API semantics.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            "/api/annotations/search/grouped/",
            response_schema=PaginatedGroupedSearchResultItemList,
            params=params,
        )

    async def search_taxa_by_name_part(
        self,
        name_part: str,
        params: TaxaNamePartParams | None = None,
    ) -> UpstreamResponse[list[TaxonWormsLike]]:
        """Search WoRMS cache taxa by a partial name.

        Args:
            name_part: The partial name to search for.
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            f"/api/annotations/worms_cache/ajax_by_name_part/{self._path_param(name_part)}/",
            response_schema=list[TaxonWormsLike],
            params=params,
        )

    async def list_image_sets(self, params: PaginationParams | None = None) -> UpstreamResponse[PaginatedImageSetList]:
        """List image sets.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get("/api/images/image_sets/", response_schema=PaginatedImageSetList, params=params)

    async def get_image_set(self, image_set_id: str) -> UpstreamResponse[ImageSet]:
        """Get an image set by ID.

        Args:
            image_set_id: The ID of the image set to retrieve.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            f"/api/images/image_sets/{self._path_param(image_set_id)}/",
            response_schema=ImageSet,
        )

    async def list_images(self, params: PaginationParams | None = None) -> UpstreamResponse[PaginatedImageList]:
        """List images.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get("/api/images/images/", response_schema=PaginatedImageList, params=params)

    async def get_image(self, image_id: str) -> UpstreamResponse[Image]:
        """Get an image by ID.

        Args:
            image_id: The ID of the image to retrieve.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(f"/api/images/images/{self._path_param(image_id)}/", response_schema=Image)

    async def list_annotation_sets(
        self,
        params: PaginationParams | None = None,
    ) -> UpstreamResponse[PaginatedAnnotationSetList]:
        """List annotation sets.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            "/api/annotations/annotation_sets/",
            response_schema=PaginatedAnnotationSetList,
            params=params,
        )

    async def get_annotation_set(
        self,
        annotation_set_id: str,
    ) -> UpstreamResponse[AnnotationSet]:
        """Get an annotation set by ID.

        Args:
            annotation_set_id: The ID of the annotation set to retrieve.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            f"/api/annotations/annotation_sets/{self._path_param(annotation_set_id)}/",
            response_schema=AnnotationSet,
        )

    async def list_annotations(
        self,
        params: PaginationParams | None = None,
    ) -> UpstreamResponse[PaginatedAnnotationList]:
        """List annotations.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get("/api/annotations/annotations/", response_schema=PaginatedAnnotationList, params=params)

    async def get_annotation(self, annotation_id: str) -> UpstreamResponse[Annotation]:
        """Get an annotation by ID.

        Args:
            annotation_id: The ID of the annotation to retrieve.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(
            f"/api/annotations/annotations/{self._path_param(annotation_id)}/",
            response_schema=Annotation,
        )

    async def list_labels(self, params: PaginationParams | None = None) -> UpstreamResponse[PaginatedLabelList]:
        """List labels.

        Args:
            params: Optional query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get("/api/labels/labels/", response_schema=PaginatedLabelList, params=params)

    async def get_label(self, label_id: str) -> UpstreamResponse[Label]:
        """Get a label by ID.

        Args:
            label_id: The ID of the label to retrieve.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        return await self._get(f"/api/labels/labels/{self._path_param(label_id)}/", response_schema=Label)

    async def _get(
        self,
        path: str,
        *,
        response_schema: object,
        params: QueryParamModel | None = None,
    ) -> UpstreamResponse[ResponseDataT]:
        """Perform a GET request to the upstream annotations API.

        Args:
            path: The path of the API endpoint.
            response_schema: Expected response data schema.
            params: Optional typed query parameters to include in the request.

        Returns:
            An UpstreamResponse object containing the response data or error information.
        """
        request = self._client.build_request(
            "GET",
            path,
            params=params.to_query_params() if params else None,
        )
        try:
            response = await self._client.send(request)
        except httpx.RequestError as exc:
            return UpstreamResponse(
                source=self.source,
                method=request.method,
                path=path,
                url=str(request.url),
                ok=False,
                status_code=None,
                error=UpstreamError(message=str(exc), type=exc.__class__.__name__),
            )

        raw_data = self._raw_response_data(response)
        if response.is_success:
            try:
                data = self._parse_response_data(raw_data, response_schema)
            except ValidationError as exc:
                return UpstreamResponse(
                    source=self.source,
                    method=request.method,
                    path=path,
                    url=str(response.url),
                    ok=False,
                    status_code=response.status_code,
                    error=UpstreamError(message=str(exc), type=exc.__class__.__name__),
                )
        else:
            data = None

        return UpstreamResponse(
            source=self.source,
            method=request.method,
            path=path,
            url=str(response.url),
            ok=response.is_success,
            status_code=response.status_code,
            data=data,
            error=None
            if response.is_success
            else UpstreamError(
                message=self._error_message(response, raw_data),
                type="HTTPStatusError",
            ),
        )

    @staticmethod
    def _path_param(value: str) -> str:
        """Encode a path parameter for use in a URL.

        Args:
            value: The value to encode.

        Returns:
            The encoded value.
        """
        return quote(str(value), safe="")

    @staticmethod
    def _raw_response_data(response: httpx.Response) -> JsonValue:
        """Extract the response data from an httpx.Response.

        Args:
            response: The httpx.Response object.

        Returns:
            The response data, which may be a dict, list, or raw text, depending on the content type.
        """
        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def _parse_response_data(data: JsonValue, response_schema: object) -> ResponseDataT:
        """Validate raw response data against the expected response schema."""
        return cast(ResponseDataT, TypeAdapter(response_schema).validate_python(data))

    @staticmethod
    def _error_message(response: httpx.Response, data: JsonValue) -> str:
        """Generate an error message based on the response and data.

        Args:
            response: The httpx.Response object.
            data: The response data.

        Returns:
            A string containing the error message.
        """
        if isinstance(data, dict):
            detail = data.get("detail") or data.get("error")
            if detail:
                return str(detail)
        return f"Upstream request failed with status {response.status_code}"
