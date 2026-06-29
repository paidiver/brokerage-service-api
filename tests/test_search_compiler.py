"""Tests for the JNCC/BODC search compiler."""

import pytest
import requests as rq
from _pytest.capture import CaptureFixture
from brokerage_service_api.models.search_model import Result, SearchResults, Summary
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.utilities.search_compiler import (
    AnnotationsAPIFetcher,
    UnknownFlavourError,
    fetch_combined_results_from_annotation_apis,
)
from pytest_mock import MockerFixture


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
    mocker: MockerFixture,
    mock_response_for_558: dict,
) -> None:
    """Test that a single Aphia ID request returns expected annotation results."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_response_for_558

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
    mocker: MockerFixture,
    mock_response_for_558_with_summary: dict,
) -> None:
    """Test that summary data is returned when requested."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_response_for_558_with_summary

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
    mocker: MockerFixture,
    capsys: CaptureFixture[str],
) -> None:
    """Test that upstream request failures are handled gracefully."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")

    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = rq.HTTPError("500 Server Error")
    mock_request.return_value = mock_response

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
    mocker: MockerFixture,
    capsys: CaptureFixture[str],
) -> None:
    """Test handling of invalid JSON responses from upstream API."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.side_effect = ValueError

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            calculate_summary=True,
        ),
    )

    assert instance.results == []
    assert "BODC returned invalid JSON." in capsys.readouterr().out


def test_annotations_api_fetcher_with_empty_results(
    mocker: MockerFixture,
) -> None:
    """Test that an empty API response returns no results."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = {}

    instance = AnnotationsAPIFetcher(
        flavour="BODC",
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            calculate_summary=True,
        ),
    )

    assert instance.results == []


def test_aggregation_of_both_upstream_apis(
    mocker: MockerFixture,
    mock_response_for_558: dict,
) -> None:
    """Test that results from both upstream APIs are combined correctly."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    expected_count = 2
    mock_request.return_value.json.return_value = mock_response_for_558

    combined_results = fetch_combined_results_from_annotation_apis(params=AnnotationSearchRequest(aphia_ids=[588]))

    assert isinstance(combined_results, SearchResults)
    assert combined_results.count == expected_count
