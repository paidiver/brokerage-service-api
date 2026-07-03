"""Tests for the JNCC/BODC search compiler."""

from types import SimpleNamespace

import pytest
from _pytest.capture import CaptureFixture
from brokerage_service_api.models.search_model import Result, ResultMetadata, SearchResults, Summary
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.utilities.search_compiler import (
    AnnotationsAPIFetcher,
    UnknownFlavourError,
    fetch_combined_results_from_annotation_apis,
)
from pytest_mock import MockerFixture


@pytest.fixture(name="mock_annotation_client")
def mock_annotation_client_fixture(mocker: MockerFixture) -> MockerFixture:
    """Mock the shared upstream annotations client used by the search compiler."""
    client = mocker.Mock()
    client.search_annotations = mocker.AsyncMock()
    client.aclose = mocker.AsyncMock()
    mocker.patch("brokerage_service_api.utilities.search_compiler.AnnotationApiClient", return_value=client)
    return client


@pytest.fixture(name="mock_response_for_558")
def mock_response_for_558() -> dict:
    """Example API response for a single Aphia ID (558)."""
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "results": {
            "annotations": [
                {
                    "creation_datetime": "2012-12-31T23:59:59Z",
                    "uuid": "987ba073-fcca-4242-85c6-c8ae990a0480",
                    "annotation_set_uuid": "36c33463-16fe-4ba4-bf1c-490a0b0c1653",
                    "annotation_set_name": "Trial Data",
                    "image_set_name": "some_image_nhame",
                    "image_set_uuid": "822731b4-a6b7-476f-887e-debf00bfa6ba",
                    "image_filename": "M58_10441297_12987745240267.jpg",
                    "image_handle": "image_url.jpg",
                    "image_uuid": "1345c48a-d360-4d48-8737-2f94a1c9517b",
                    "label_name": "porifera_03",
                    "label_aphia_id": 558,
                    "annotation_platform": "ImagePro",
                    "annotation_creation_datetime": "2012-12-31T23:59:59Z",
                    "annotation_shape": "single-pixel",
                    "annotation_coordinates": [[1359.0, 2909.0]],
                    "annotation_dimension_pixels": 366.9346,
                    "annotator_name": "Jane Doe",
                }
            ]
        },
    }


@pytest.fixture(name="mock_response_for_558_with_summary")
def mock_response_for_558_with_summary() -> dict:
    """Example API response for a single Aphia ID with summary data."""
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "results": {
            "summary": {
                "n_annotations": 1,
                "n_images": 1,
                "n_annotation_sets": 1,
                "n_image_sets": 1,
            },
            "annotations": [
                {
                    "creation_datetime": "2012-12-31T23:59:59Z",
                    "uuid": "987ba073-fcca-4242-85c6-c8ae990a0480",
                    "annotation_set_uuid": "36c33463-16fe-4ba4-bf1c-490a0b0c1653",
                    "annotation_set_name": "Trial Data",
                    "image_set_name": "some_image_nhame",
                    "image_set_uuid": "822731b4-a6b7-476f-887e-debf00bfa6ba",
                    "image_filename": "M58_10441297_12987745240267.jpg",
                    "image_handle": "image_url.jpg",
                    "image_uuid": "1345c48a-d360-4d48-8737-2f94a1c9517b",
                    "label_name": "porifera_03",
                    "label_aphia_id": 558,
                    "annotation_platform": "ImagePro",
                    "annotation_creation_datetime": "2012-12-31T23:59:59Z",
                    "annotation_shape": "single-pixel",
                    "annotation_coordinates": [[1359.0, 2909.0]],
                    "annotation_dimension_pixels": 366.9346,
                    "annotator_name": "Jane Doe",
                }
            ],
        },
    }


def test_annotations_api_fetcher_with_single_aphia_id(
    mock_annotation_client: MockerFixture,
    mock_response_for_558: dict,
) -> None:
    """Test that a single Aphia ID request returns expected annotation results."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=SimpleNamespace(summary=None, annotations=[mock_response_for_558["results"]["annotations"][0]])
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(aphia_ids=[588]),
    )

    assert isinstance(instance.results[0], Result)

    assert instance.results == [
        Result.construct_instance_from_raw_response(
            raw_response=mock_response_for_558["results"]["annotations"][0],
            source="BODC",
        )
    ]

    assert instance.summary is None


def test_annotations_api_fetcher_with_summary(
    mock_annotation_client: MockerFixture,
    mock_response_for_558_with_summary: dict,
) -> None:
    """Test that summary data is returned when requested."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=SimpleNamespace(
                summary=mock_response_for_558_with_summary["results"]["summary"],
                annotations=[mock_response_for_558_with_summary["results"]["annotations"][0]],
            )
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            calculate_summary=True,
        ),
    )

    assert instance.summary == Summary(
        n_annotations=1,
        n_images=1,
        n_annotation_sets=1,
        n_image_sets=1,
    )


def test_annotations_api_fetcher_with_invalid_flavour() -> None:
    """Test that an invalid flavour raises UnknownFlavourError."""
    with pytest.raises(UnknownFlavourError) as exc:
        AnnotationsAPIFetcher(
            flavour="INVALID",
            params=AnnotationSearchRequest(
                aphia_ids=[588],
                calculate_summary=True,
            ),
        )

    assert str(exc.value) == "INVALID is not recognised."


def test_annotations_api_fetcher_with_failed_request(
    mock_annotation_client: MockerFixture,
    capsys: CaptureFixture[str],
) -> None:
    """Test that upstream request failures are handled gracefully."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=False,
        data=None,
        error=SimpleNamespace(message="500 Server Error"),
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            calculate_summary=True,
        ),
    )

    assert instance.results == []

    assert "Something went wrong calling the BODC annotations API 500 Server Error." in capsys.readouterr().out


def test_annotations_api_fetcher_with_json_decode_error(
    mock_annotation_client: MockerFixture,
    capsys: CaptureFixture[str],
) -> None:
    """Test handling of missing data from the upstream client."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(ok=True, data=None, error=None)

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            calculate_summary=True,
        ),
    )

    assert instance.results == []
    assert "Something went wrong calling the BODC annotations API" not in capsys.readouterr().out


def test_annotations_api_fetcher_with_empty_results(
    mock_annotation_client: MockerFixture,
) -> None:
    """Test that an empty API response returns no results."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True, data=SimpleNamespace(results=None), error=None
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            calculate_summary=True,
        ),
    )

    assert instance.results == []


def test_aggregation_of_both_upstream_apis(
    mock_annotation_client: MockerFixture, mock_response_for_558: dict, mock_request_for_pagination: MockerFixture
) -> None:
    """Test that results from both upstream APIs are combined correctly."""
    expected_count = 2
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=SimpleNamespace(summary=None, annotations=[mock_response_for_558["results"]["annotations"][0]])
        ),
        error=None,
    )

    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588]), request=mock_request_for_pagination
    )

    assert isinstance(combined_results, SearchResults)
    assert combined_results.count == expected_count


def test_search_compiler_with_ordering_by_aphia_id(
    mock_annotation_client: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture
) -> None:
    """Test that ordering by aphia_id works as expected."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(results=SimpleNamespace(summary=None, annotations=mock_assorted_aphia_ids_response)),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[1],  # the 1 is irrelevant, as the mocked response intentionally returns 10 unordered results.
            order_by="label_aphia_id",
        ),
    )

    returned_aphia_ids = [result.label_aphia_id for result in instance.results]
    assert returned_aphia_ids == sorted(returned_aphia_ids)


def test_search_compiler_with_ordering_by_annotation_creation_datetime(
    mock_annotation_client: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture
) -> None:
    """Test that ordering by annotation_creation_datetime works as expected."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(results=SimpleNamespace(summary=None, annotations=mock_assorted_aphia_ids_response)),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[1],  # the 1 is irrelevant, as the mocked response intentionally returns 10 unordered results.
            order_by="annotation_creation_datetime",
        ),
    )
    returned_datetimes = [result.annotation_creation_datetime for result in instance.results]
    assert returned_datetimes == sorted(returned_datetimes)


def test_search_compiler_with_ordering_by_label_name(
    mock_annotation_client: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture
) -> None:
    """Test that ordering by annotation_creation_datetime works as expected."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(results=SimpleNamespace(summary=None, annotations=mock_assorted_aphia_ids_response)),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[1],  # the 1 is irrelevant, as the mocked response intentionally returns 10 unordered results.
            order_by="label_name",
        ),
    )
    returned_label_names = [result.label_name for result in instance.results]
    assert returned_label_names == sorted(returned_label_names)


def test_search_compiler_result_metadata(
    mock_annotation_client: MockerFixture,
    mock_assorted_aphia_ids_response: MockerFixture,
    mock_request_for_pagination: MockerFixture,
) -> None:
    """Test that the result metadata is formed and returned correctly."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(results=SimpleNamespace(summary=None, annotations=mock_assorted_aphia_ids_response)),
        error=None,
    )

    # The '588' does nothing in this test case as the BODC/JNCC api's are mocked to return the same 10 results.
    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588]), request=mock_request_for_pagination
    )

    # The mocker is set to return 10 results, so this is whats expected in the outputted model.
    expected_individual_result_count = 10

    assert isinstance(combined_results.result_metadata, ResultMetadata)

    assert combined_results.result_metadata.bodc_results == expected_individual_result_count
    assert combined_results.result_metadata.jncc_results == expected_individual_result_count

    # Check that the overall count is the combination of the two.
    assert (
        combined_results.result_metadata.total_results
        == combined_results.result_metadata.bodc_results + combined_results.result_metadata.jncc_results
    )
