"""Tests for the JNCC/BODC search compiler pagination logic."""

import pytest
from starlette.requests import Request
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.utilities.search_compiler import (
    fetch_combined_results_from_annotation_apis,
)
from pytest_mock import MockerFixture


@pytest.fixture(name="mock_request_for_pagination")
def mock_request_fixture():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/annotations/search",
        "query_string": b"aphia_ids=588&page_size=5&page=2",
        "headers": [],
    }
    return Request(scope)

def test_search_compiler_pagination_with_page_size_1_to_10(
    mocker: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture, mock_request_for_pagination: MockerFixture
) -> None:
    """Call upon the search endpoint requesting a range of differing page sizes, and verify they are correct."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_assorted_aphia_ids_response

    # The '588' does nothing in this test case as the BODC/JNCC api's are mocked to return the same 10 results.
    for page_size in range(1, 11):
        combined_results = fetch_combined_results_from_annotation_apis(
            params=AnnotationSearchRequest(aphia_ids=[588], page_size=page_size), request=mock_request_for_pagination
        )
        assert len(combined_results.results.annotations) == page_size


def test_search_compiler_pagination_with_varying_page_numbers(
    mocker: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture, mock_request_for_pagination: MockerFixture
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
            params=AnnotationSearchRequest(aphia_ids=[588], page=page_number, page_size=1), request=mock_request_for_pagination
        )
        .results.annotations[0]
        .uuid
        for page_number in range(1, 11)
    ]

    assert len(uuids) == len(set(uuids)), "Duplicate UUID's detected!"




def test_search_compiler_pagination_prev_and_next_fields(
    mocker: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture, mock_request_for_pagination: MockerFixture
) -> None:
    """Call upon the search endpoint requesting a range of differing page sizes, and verify they are correct."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_assorted_aphia_ids_response

    # The '588' does nothing in this test case as the BODC/JNCC api's are mocked to return the same 10 results.
    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588], page_size=10, page=1), request=mock_request_for_pagination
    )
    print(combined_results)

