"""Tests for the JNCC/BODC search compiler pagination logic."""

from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.utilities.search_compiler import (
    fetch_combined_results_from_annotation_apis,
)
from pytest_mock import MockerFixture


def test_search_compiler_pagination_with_page_size_1_to_10(
    mocker: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture
) -> None:
    """Call upon the search endpoint requesting a range of differing page sizes, and verify they are correct."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_assorted_aphia_ids_response

    # The '588' does nothing in this test case as the BODC/JNCC api's are mocked to return the same 10 results.
    for page_size in range(1, 11):
        combined_results = fetch_combined_results_from_annotation_apis(
            params=AnnotationSearchRequest(aphia_ids=[588], page_size=page_size)
        )
        assert len(combined_results.results.annotations) == page_size


def test_search_compiler_pagination_with_varying_page_numbers(
    mocker: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture
) -> None:
    """Call upon the search endpoint requesting a range of differing page numbers, and verify they are different.

    The purpose of this test is to request a page_size of 1, but then request page numbers 1 - 10.
    The test will check that the results on each page are unique, and give some validation that the
    pagination system is working.
    """
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_assorted_aphia_ids_response

    # The '588' does nothing in this test case as the BODC/JNCC api's are mocked to return the same 10 results.
    uuids = [
        fetch_combined_results_from_annotation_apis(
            params=AnnotationSearchRequest(aphia_ids=[588], page=page_number, page_size=1)
        )
        .results.annotations[0]
        .uuid
        for page_number in range(1, 11)
    ]

    assert len(uuids) == len(set(uuids)), "Duplicate UUID's detected!"
