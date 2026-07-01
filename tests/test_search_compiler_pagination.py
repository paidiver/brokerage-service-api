"""Tests for the JNCC/BODC search compiler pagination logic."""

import pytest
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.utilities.search_compiler import (
    InvalidPageNumberError,
    construct_prev_and_next_response_fields,
    fetch_combined_results_from_annotation_apis,
)
from pytest_mock import MockerFixture
from starlette.requests import Request


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


def test_search_compiler_pagination_with_invalid_page_number(
    mocker: MockerFixture, mock_assorted_aphia_ids_response: MockerFixture, mock_request_for_pagination: MockerFixture
) -> None:
    """Call upon the search endpoint with an invalid page number to check the correct error is raised."""
    mock_request = mocker.patch("brokerage_service_api.utilities.search_compiler.rq.get")
    mock_request.return_value.json.return_value = mock_assorted_aphia_ids_response

    with pytest.raises(InvalidPageNumberError):
        fetch_combined_results_from_annotation_apis(
            params=AnnotationSearchRequest(aphia_ids=[588], page_size=5, page=100), request=mock_request_for_pagination
        )


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
            params=AnnotationSearchRequest(aphia_ids=[588], page=page_number, page_size=1),
            request=mock_request_for_pagination,
        )
        .results.annotations[0]
        .uuid
        for page_number in range(1, 11)
    ]

    assert len(uuids) == len(set(uuids)), "Duplicate UUID's detected!"


def test_search_compiler_pagination_prev_and_next_fields() -> None:
    """Call upon 'construct_prev_and_next_response_fields' with differing page sizes, and verify the response."""
    # With the max page of 1, and current page set to 1. Previous=None, next=1
    url = "http://localhost:8080/api?aphia_ids=588&page_size=5&page=1"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=1)
    assert response == (None, "1")

    # With the max page of 5, and current page set to 2. Previous=2, next=3
    url = "http://localhost:8080/api?aphia_ids=588&page_size=5&page=2"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=5)
    assert response == ("1", "3")

    # With the max page of 5, and current page set to 3. Previous=2, next=4
    url = "http://localhost:8080/api?aphia_ids=588&page_size=5&page=3"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=5)
    assert response == ("2", "4")

    # With the max page of 5, and current page set to 4. Previous=3, next=5
    url = "http://localhost:8080/api?aphia_ids=588&page_size=5&page=4"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=5)
    assert response == ("3", "5")

    # With the max page of 5, and current page set to 5. Previous=4, next=5
    url = "http://localhost:8080/api?aphia_ids=588&page_size=5&page=5"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=5)
    assert response == ("4", "5")


def test_search_compiler_pagination_prev_and_next_fields_with_malformed_query_string() -> None:
    """Request prev/next fields with an incorrect query string, forcing a KeyError."""
    url = "http://localhost:8080/api?aphia_ids=588&page_size_wrong=5&page_wrong=1"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=1)

    # In an error state, we expect None for both 'prev' and 'next'.
    assert response == (None, None)


def test_search_compiler_pagination_prev_and_next_fields_with_generic_exception() -> None:
    """Request prev/next fields with an incorrect query string, and ensure the default of None is returned for both."""
    url = "http://localhost:8080/api?aphia_ids=588&page_size=5&page=ten"
    response = construct_prev_and_next_response_fields(request_url=url, maximum_allowed_page=1)
    # In an error state, we expect None for both 'prev' and 'next'.
    assert response == (None, None)
