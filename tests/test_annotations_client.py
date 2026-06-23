"""Tests for the upstream annotations API client."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from brokerage_service_api.models.sources import SourceConfig
from brokerage_service_api.upstream import (
    AnnotationApiClient,
    AnnotationSearchParams,
    PaginationParams,
    TaxaNamePartParams,
)
from pydantic import ValidationError
from starlette import status

COD_APHIA_ID = 126436

BODC_SOURCE = SourceConfig(
    name="bodc",
    label="BODC",
    base_url="https://annotations.bodc.example/",
)
JNCC_SOURCE = SourceConfig(
    name="jncc",
    label="JNCC",
    base_url="https://annotations-api.jncc.example/",
)


def run(coro: Any) -> Any:
    """Run an async client call from a synchronous test."""
    return asyncio.run(coro)


def test_client_sends_query_params_and_returns_success_metadata() -> None:
    """The client should preserve source and request metadata on success."""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            status.HTTP_200_OK,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": {
                    "annotations": [
                        {
                            "uuid": "11111111-1111-1111-1111-111111111111",
                            "image_filename": "image-1.jpg",
                            "image_uuid": "22222222-2222-2222-2222-222222222222",
                            "label_name": "cod",
                            "label_aphia_id": COD_APHIA_ID,
                            "annotation_platform": None,
                            "creation_datetime": "2024-01-01T12:00:00Z",
                            "annotation_shape": "point",
                            "annotation_coordinates": [[1.0, 2.0]],
                            "annotation_dimension_pixels": None,
                            "annotator_name": None,
                            "annotation_set_uuid": "33333333-3333-3333-3333-333333333333",
                            "annotation_set_name": "Example annotation set",
                            "image_set_uuid": "44444444-4444-4444-4444-444444444444",
                            "image_set_name": "Example image set",
                        },
                    ],
                },
            },
            request=request,
        )

    async def exercise() -> None:
        async with AnnotationApiClient(BODC_SOURCE, transport=httpx.MockTransport(handler)) as client:
            response = await client.search_annotations(
                AnnotationSearchParams(
                    name_part="cod",
                    page=2,
                    aphia_ids=[COD_APHIA_ID, 141433],
                    calculate_summary=True,
                    deployment="survey",
                ),
            )

        assert response.ok is True
        assert response.status_code == status.HTTP_200_OK
        assert response.source == BODC_SOURCE
        assert response.method == "GET"
        assert response.data is not None
        assert response.data.count == 1
        assert response.data.results.annotations[0].image_filename == "image-1.jpg"
        assert response.data.results.annotations[0].label_aphia_id == COD_APHIA_ID
        assert response.error is None
        assert response.path == "/api/annotations/search/"
        assert seen_requests[0].url == (
            "https://annotations.bodc.example/api/annotations/search/"
            "?page=2&aphia_ids%5B%5D=126436&aphia_ids%5B%5D=141433&calculate_summary=true"
            "&deployment=survey&name_part=cod"
        )

    run(exercise())


def test_client_encodes_path_params() -> None:
    """Path parameters should be URL encoded before the upstream call."""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(status.HTTP_200_OK, json=[], request=request)

    async def exercise() -> None:
        async with AnnotationApiClient(JNCC_SOURCE, transport=httpx.MockTransport(handler)) as client:
            response = await client.search_taxa_by_name_part(
                "Abra alba",
                TaxaNamePartParams(combine_vernaculars=True),
            )

        assert response.ok is True
        assert response.path == "/api/annotations/worms_cache/ajax_by_name_part/Abra%20alba/"
        assert seen_requests[0].url == (
            "https://annotations-api.jncc.example/api/annotations/worms_cache/ajax_by_name_part/"
            "Abra%20alba/?combine_vernaculars=true"
        )

    run(exercise())


def test_client_parses_paginated_list_response() -> None:
    """List endpoints should parse upstream data into typed response models."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status.HTTP_200_OK,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": "55555555-5555-5555-5555-555555555555",
                        "name": "Example image set",
                        "extra_upstream_field": "kept",
                    },
                ],
            },
            request=request,
        )

    async def exercise() -> None:
        async with AnnotationApiClient(BODC_SOURCE, transport=httpx.MockTransport(handler)) as client:
            response = await client.list_image_sets()

        assert response.ok is True
        assert response.data is not None
        assert response.data.count == 1
        assert response.data.results[0].name == "Example image set"
        assert response.data.results[0].extra_upstream_field == "kept"

    run(exercise())


def test_client_returns_error_metadata_for_http_errors() -> None:
    """Non-2xx upstream responses should keep failure details without raising."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            json={"detail": "Temporarily unavailable"},
            request=request,
        )

    async def exercise() -> None:
        async with AnnotationApiClient(BODC_SOURCE, transport=httpx.MockTransport(handler)) as client:
            response = await client.list_image_sets()

        assert response.ok is False
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data is None
        assert response.error is not None
        assert response.error.type == "HTTPStatusError"
        assert response.error.message == "Temporarily unavailable"

    run(exercise())


def test_client_returns_generic_error_metadata_for_non_json_http_errors() -> None:
    """Non-JSON errors should fall back to a status-code error message."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=b"upstream exploded",
            request=request,
        )

    async def exercise() -> None:
        async with AnnotationApiClient(BODC_SOURCE, transport=httpx.MockTransport(handler)) as client:
            response = await client.list_image_sets()

        assert response.ok is False
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data is None
        assert response.error is not None
        assert response.error.type == "HTTPStatusError"
        assert response.error.message == "Upstream request failed with status 500"

    run(exercise())


def test_client_returns_error_metadata_for_request_errors() -> None:
    """Transport failures should be represented in the response envelope."""
    source = SourceConfig(
        name="example",
        label="Example",
        base_url="https://example.test/",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("could not connect", request=request)

    async def exercise() -> None:
        async with AnnotationApiClient(source, transport=httpx.MockTransport(handler)) as client:
            response = await client.get_label("label-1")

        assert response.ok is False
        assert response.status_code is None
        assert response.url == "https://example.test/api/labels/labels/label-1/"
        assert response.error is not None
        assert response.error.type == "ConnectError"
        assert "could not connect" in response.error.message

    run(exercise())


def test_client_methods_map_to_expected_paths() -> None:
    """Public helper methods should target the requested upstream endpoints."""
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(status.HTTP_200_OK, json={}, request=request)

    async def exercise() -> None:
        async with AnnotationApiClient(BODC_SOURCE, transport=httpx.MockTransport(handler)) as client:
            await client.search_annotations_grouped()
            await client.list_image_sets(PaginationParams(page=1, page_size=20))
            await client.get_image_set("image-set-1")
            await client.list_images()
            await client.get_image("image-1")
            await client.list_annotation_sets()
            await client.get_annotation_set("annotation-set-1")
            await client.list_annotations()
            await client.get_annotation("annotation-1")
            await client.list_labels()
            await client.get_label("label-1")

    run(exercise())

    assert seen_paths == [
        "/api/annotations/search/grouped/",
        "/api/images/image_sets/",
        "/api/images/image_sets/image-set-1/",
        "/api/images/images/",
        "/api/images/images/image-1/",
        "/api/annotations/annotation_sets/",
        "/api/annotations/annotation_sets/annotation-set-1/",
        "/api/annotations/annotations/",
        "/api/annotations/annotations/annotation-1/",
        "/api/labels/labels/",
        "/api/labels/labels/label-1/",
    ]


def test_search_params_reject_unknown_and_invalid_values() -> None:
    """Query parameters should be constrained to the upstream API spec."""
    with pytest.raises(ValidationError):
        AnnotationSearchParams(name_part="co")

    with pytest.raises(ValidationError):
        AnnotationSearchParams(deployment="dive")

    with pytest.raises(ValidationError):
        AnnotationSearchParams(q="cod")
