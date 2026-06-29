"""Tests for the upstream schemas."""

import pytest
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from pydantic import ValidationError


def test_annotation_search_request_with_missing_fields() -> None:
    """Test that a ValueError is raised when aphia_ids/name_parts are missing."""
    # pass nothing to the constructor, which should make the 'check_required_fields' validator fail.
    with pytest.raises(ValidationError) as exc:
        AnnotationSearchRequest()
    assert "At least one of 'aphia_ids' or 'name_part' must be provided" in str(exc.value)


def test_aphia_ids_in_query_string_property() -> None:
    """Test that the aphia_id joining property functions correctly."""
    instance = AnnotationSearchRequest(aphia_ids=[123, 456])
    assert instance.aphia_ids_in_query_string == "aphia_ids[]=123&aphia_ids[]=456"


def test_model_as_query_string_with_aphia_ids() -> None:
    """Test that the model with aphia_ids represented as a query string looks as expected."""
    # A simple case with aphia_ids only.
    instance = AnnotationSearchRequest(aphia_ids=[123, 456])
    assert instance.to_query_string() == "?aphia_ids[]=123&aphia_ids[]=456&"

    # A more complex case with some additional fields prepared.
    complex_instance = AnnotationSearchRequest(aphia_ids=[123, 456], calculate_summary=True, deployment="sampling")
    assert (
        complex_instance.to_query_string()
        == "?aphia_ids[]=123&aphia_ids[]=456&calculate_summary=true&deployment=sampling"
    )


def test_model_as_query_string_with_name_parts() -> None:
    """Test that the model with name_parts represented as a query string looks as expected."""
    # A simple case with name_parts only.
    instance = AnnotationSearchRequest(name_part="abc")
    assert instance.to_query_string() == "?name_part=abc"

    # A more complex case with some additional fields prepared.
    complex_instance = AnnotationSearchRequest(name_part="abc", calculate_summary=True, deployment="sampling")
    assert complex_instance.to_query_string() == "?calculate_summary=true&deployment=sampling&name_part=abc"
