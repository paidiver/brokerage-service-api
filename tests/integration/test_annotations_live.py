"""Live content tests for Docker Compose annotations upstream APIs."""

from __future__ import annotations

import os
from collections.abc import Iterable

import pytest
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationSearchParams, PaginationParams
from brokerage_service_api.upstream import AnnotationApiClient, UpstreamResponse
from brokerage_service_api.utilities.source import get_source_registry
from dotenv import load_dotenv
from starlette import status

from tests.utils.load_seed_data import load_expected_seed_data

load_dotenv()

RUN_LIVE_UPSTREAM_TESTS = os.getenv("RUN_LIVE_UPSTREAM_TESTS") == "1"
PAGE_SIZE = 200


pytestmark = [
    pytest.mark.anyio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not RUN_LIVE_UPSTREAM_TESTS,
        reason="set RUN_LIVE_UPSTREAM_TESTS=1 to call live annotations APIs",
    ),
]


def live_sources() -> Iterable[SourceConfig]:
    """Return enabled live sources for Docker Compose annotations services."""
    live_source_names = {"bodc", "jncc"}
    for name in live_source_names:
        os.environ.setdefault(f"{name.upper()}_ANNOTATIONS_API_URL", f"http://annotations-api-{name}:8000/")

    get_source_registry.cache_clear()

    for source in get_source_registry().list():
        if live_source_names and source.name not in live_source_names:
            continue
        if source.name in {"bodc", "jncc"}:
            yield source


LIVE_SOURCES = tuple(live_sources()) if RUN_LIVE_UPSTREAM_TESTS else ()


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_rejects_image_set_uuid_as_annotation_id(source: SourceConfig) -> None:
    """The annotation endpoint should reject an image-set UUID."""
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        response = await client.list_image_sets(PaginationParams(page_size=PAGE_SIZE))

    assert_live_response_ok(response)
    assert response.data is not None
    image_sets = {str(image_set.id): image_set for image_set in response.data.results}

    assert expected.image_set_uuid in image_sets
    assert image_sets[expected.image_set_uuid].name == expected.image_set_name


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_contains_seeded_image_set(source: SourceConfig) -> None:
    """The live API should contain the seeded image set metadata.

    Args:
        source: The source configuration to test.
    """
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        response = await client.get_annotation(expected.image_set_uuid)

    assert_live_response_not_ok(response)


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_contains_seeded_images(source: SourceConfig) -> None:
    """The live API should expose images from the seeded image-set JSON.

    Args:
        source: The source configuration to test.
    """
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        response = await client.list_images(PaginationParams(page_size=PAGE_SIZE))

    assert_live_response_ok(response)
    assert response.data is not None
    assert response.data.count >= len(expected.image_filenames)

    returned_filenames = {image.filename.strip() for image in response.data.results}
    expected_filenames = {filename.strip() for filename in expected.image_filenames}
    assert expected_filenames >= returned_filenames


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_contains_seeded_annotation_set(source: SourceConfig) -> None:
    """The live API should contain the annotation set uploaded from XLSX.

    Args:
        source: The source configuration to test.
    """
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        response = await client.list_annotation_sets(PaginationParams(page_size=PAGE_SIZE))

    assert_live_response_ok(response)
    assert response.data is not None
    annotation_set_names = {annotation_set.name.strip() for annotation_set in response.data.results}
    assert expected.annotation_set_name in annotation_set_names


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_contains_seeded_labels(source: SourceConfig) -> None:
    """The live API should contain labels uploaded from the seed XLSX.

    Args:
        source: The source configuration to test.
    """
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        response = await client.list_labels(PaginationParams(page_size=PAGE_SIZE))

    assert_live_response_ok(response)
    assert response.data is not None
    assert response.data.count >= len(expected.label_names)

    returned_labels = {label.name.strip() for label in response.data.results}
    expected_label_names = {name.strip() for name in expected.label_names}
    assert len(returned_labels) >= len(expected_label_names)
    assert expected_label_names <= returned_labels


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_contains_seeded_annotations(source: SourceConfig) -> None:
    """The live API should contain annotations uploaded from the seed XLSX.

    Args:
        source: The source configuration to test.
    """
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        response = await client.list_annotations(PaginationParams(page_size=1))

    assert_live_response_ok(response)
    assert response.data is not None
    assert response.data.count >= expected.annotation_count


@pytest.mark.parametrize("source", LIVE_SOURCES, ids=lambda source: source.name)
async def test_live_source_search_returns_seeded_label(source: SourceConfig) -> None:
    """The search endpoint should return seeded annotation rows for a fixture label.

    Args:
        source: The source configuration to test.
    """
    expected = load_expected_seed_data(source.name)

    async with AnnotationApiClient(source) as client:
        print(f"Searching {source.name} for label {expected.search_label}..., page size {PAGE_SIZE}")
        response = await client.search_annotations(
            AnnotationSearchParams(name_part=expected.search_label, page_size=PAGE_SIZE),
        )

    assert_live_response_ok(response)
    assert response.data is not None
    assert response.data.count > 0
    assert any(annotation.label_name == expected.search_label for annotation in response.data.results.annotations)


def assert_live_response_ok(response: UpstreamResponse[object]) -> None:
    """Assert a live upstream response succeeded with useful failure context.

    Args:
        response: The upstream response to check.
    """
    assert response.ok is True, (
        f"{response.source.name} returned {response.status_code} from {response.url}: "
        f"{response.error.message if response.error else response.data}"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data is not None


def assert_live_response_not_ok(response: UpstreamResponse[object]) -> None:
    """Assert a live upstream response failed with useful failure context.

    Args:
        response: The upstream response to check.
    """
    assert response.ok is False, (
        f"{response.source.name} returned {response.status_code} from {response.url}: "
        f"{response.error.message if response.error else response.data}"
    )
    assert response.status_code != status.HTTP_200_OK
    assert response.error is not None
