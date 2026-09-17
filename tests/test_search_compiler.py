"""Tests for the JNCC/BODC search compiler."""

from http import HTTPStatus
from types import SimpleNamespace

import httpx
import pytest
from brokerage_service_api.models.search_model import Result, SearchResults, Summary
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationSearchRequest
from brokerage_service_api.upstream.annotations import AnnotationApiClient
from brokerage_service_api.utilities.search_compiler import (
    AnnotationsAPIFetcher,
    fetch_combined_results_from_annotation_apis,
)
from fastapi import HTTPException
from pydantic import HttpUrl
from pytest_mock import MockerFixture
from starlette.requests import Request


@pytest.fixture(name="mock_response_for_558")
def mock_response_for_558() -> dict:
    """Example API response for a single Aphia ID (558)."""
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
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
    }


@pytest.fixture(name="mock_response_for_558_with_summary")
def mock_response_for_558_with_summary() -> dict:
    """Example API response for a single Aphia ID with summary data."""
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
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
        "meta": {"summary": {"n_annotations": 1, "n_images": 1, "n_annotation_sets": 1, "n_image_sets": 1}},
    }


@pytest.fixture(name="mock_source_config")
def mock_source_config_fixture() -> SourceConfig:
    """An example source config."""
    return SourceConfig(
        name="some_source",
        label="some_label",
        base_url=HttpUrl("http://some_url"),
    )


def test_annotations_api_fetcher_with_single_aphia_id(
    mock_annotation_client: MockerFixture, mock_response_for_558: dict, mock_source_config: MockerFixture
) -> None:
    """Test that a single Aphia ID request returns expected annotation results."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=[mock_response_for_558["results"][0]],
            count=len([mock_response_for_558["results"][0]]),
            next=None,
            meta=SimpleNamespace(summary=None, info=None),
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(aphia_ids=[588]),
    )
    instance._make_request()

    assert isinstance(instance.results[0], Result)

    assert instance.results == [
        Result.construct_instance_from_raw_response(
            raw_response=mock_response_for_558["results"][0],
            source="some_source",
        )
    ]

    assert instance.summary is None


def test_annotations_api_fetcher_with_summary(
    mock_annotation_client: MockerFixture, mock_response_for_558_with_summary: dict, mock_source_config: MockerFixture
) -> None:
    """Test that summary data is returned when requested."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=[mock_response_for_558_with_summary["results"][0]],
            count=len([mock_response_for_558_with_summary["results"][0]]),
            next=None,
            meta=SimpleNamespace(summary=Summary(**mock_response_for_558_with_summary["meta"]["summary"]), info=None),
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            add_summary=True,
        ),
    )
    instance._make_request()

    assert instance.summary == Summary(
        n_annotations=1,
        n_images=1,
        n_annotation_sets=1,
        n_image_sets=1,
    )


def test_annotations_api_fetcher_with_failed_request(
    mock_annotation_client: MockerFixture,
    mock_source_config: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that upstream request failures are handled gracefully."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=False,
        data=None,
        error=SimpleNamespace(message="500 Server Error"),
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            add_summary=True,
        ),
    )
    with pytest.raises(HTTPException) as exc:
        instance._make_request()

    assert instance.results == []
    assert exc.value.status_code == HTTPStatus.BAD_GATEWAY


def test_annotations_api_fetcher_with_failed_request_and_missing_error(
    mock_annotation_client: MockerFixture,
    mock_source_config: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that upstream request failure is handled correcly when 'error' is missing in the response."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=False,
        data=None,
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(
            aphia_ids=[588],
            add_summary=True,
        ),
    )
    with pytest.raises(HTTPException) as exc:
        instance._make_request()

    assert instance.results == []
    assert exc.value.status_code == HTTPStatus.BAD_GATEWAY


def test_annotations_api_fetcher_with_response_data_none_returns_no_results(
    mock_annotation_client: MockerFixture,
    mock_source_config: MockerFixture,
) -> None:
    """Test that a valid upstream response with no data returns no results."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=None,
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(aphia_ids=[588]),
    )
    with pytest.raises(HTTPException) as exc:
        instance._make_request()
    assert exc.value.status_code == HTTPStatus.BAD_GATEWAY

    assert instance.results == []
    assert instance.summary is None


def test_annotations_api_fetcher_with_response_results_none_returns_no_results(
    mock_annotation_client: MockerFixture,
    mock_source_config: MockerFixture,
) -> None:
    """Test that a valid upstream response with no results returns no results."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(results=None),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(aphia_ids=[588]),
    )
    with pytest.raises(HTTPException) as exc:
        instance._make_request()
    assert exc.value.status_code == HTTPStatus.BAD_GATEWAY

    assert instance.results == []
    assert instance.summary is None


def test_fetch_combined_results_with_empty_annotations_returns_empty_search_results(
    mock_annotation_client: MockerFixture,
) -> None:
    """Test that pagination handles empty upstream results without crashing."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(results=[], count=len([]), next=None, meta=SimpleNamespace(summary=None, info=None)),
        error=None,
    )

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/annotations/search",
        "query_string": b"aphia_ids=588&page_size=5",
        "headers": [],
    }
    request = Request(scope)

    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588]), request=request
    )

    assert isinstance(combined_results, SearchResults)
    assert combined_results.count == 0
    assert combined_results.results == []
    assert combined_results.meta.summary is None
    assert combined_results.previous is None
    assert combined_results.next is None
    assert combined_results.count == 0


def test_aggregation_of_both_upstream_apis(
    mock_annotation_client: MockerFixture, mock_response_for_558: dict, mock_request_for_pagination: MockerFixture
) -> None:
    """Test that results from both upstream APIs are combined correctly."""
    expected_count = 2
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=[mock_response_for_558["results"][0]],
            count=len([mock_response_for_558["results"][0]]),
            next=None,
            meta=SimpleNamespace(summary=None, info=None),
        ),
        error=None,
    )

    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588]), request=mock_request_for_pagination
    )

    assert isinstance(combined_results, SearchResults)
    assert combined_results.count == expected_count


def test_fetch_combined_results_appends_source_summaries(
    mocker: MockerFixture,
    mock_annotation_client: MockerFixture,
    mock_response_for_558: dict,
    mock_request_for_pagination: MockerFixture,
) -> None:
    """Test that summary objects from each source are appended and combined."""
    summary = Summary(n_annotations=1, n_images=1, n_annotation_sets=1, n_image_sets=1)
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=[mock_response_for_558["results"][0]],
            count=len([mock_response_for_558["results"][0]]),
            next=None,
            meta=SimpleNamespace(summary=summary, info=None),
        ),
        error=None,
    )

    source_a = SourceConfig(name="bodc", label="BODC", base_url="http://bodc-api:8000/api", enabled=True)
    source_b = SourceConfig(name="jncc", label="JNCC", base_url="http://jncc-api:8000/api", enabled=True)
    mocker.patch(
        "brokerage_service_api.utilities.search_compiler.get_source_registry",
        return_value=SimpleNamespace(list=lambda: [source_a, source_b]),
    )

    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588]), request=mock_request_for_pagination
    )
    expected_result = 2
    assert combined_results.meta.summary == Summary(
        n_annotations=expected_result,
        n_images=expected_result,
        n_annotation_sets=expected_result,
        n_image_sets=expected_result,
    )
    assert combined_results.count == expected_result


def test_search_compiler_with_ordering_by_aphia_id(
    mock_annotation_client: MockerFixture,
    mock_assorted_aphia_ids_response: MockerFixture,
    mock_source_config: MockerFixture,
) -> None:
    """Test that ordering by aphia_id works as expected."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=mock_assorted_aphia_ids_response["results"],
            count=len(mock_assorted_aphia_ids_response["results"]),
            next=None,
            meta=SimpleNamespace(summary=None, info=None),
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(
            aphia_ids=[1],  # the 1 is irrelevant, as the mocked response intentionally returns 10 unordered results.
            order_by="label_aphia_id",
        ),
    )
    instance._make_request()

    returned_aphia_ids = [result.label_aphia_id for result in instance.results]
    assert returned_aphia_ids == sorted(returned_aphia_ids)


def test_search_compiler_with_ordering_by_annotation_creation_datetime(
    mock_annotation_client: MockerFixture,
    mock_assorted_aphia_ids_response: MockerFixture,
    mock_source_config: MockerFixture,
) -> None:
    """Test that ordering by annotation_creation_datetime works as expected."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=mock_assorted_aphia_ids_response["results"],
            count=len(mock_assorted_aphia_ids_response["results"]),
            next=None,
            meta=SimpleNamespace(summary=None, info=None),
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(
            aphia_ids=[1],  # the 1 is irrelevant, as the mocked response intentionally returns 10 unordered results.
            order_by="annotation_creation_datetime",
        ),
    )
    instance._make_request()
    returned_datetimes = [result.annotation_creation_datetime for result in instance.results]
    assert returned_datetimes == sorted(returned_datetimes)


def test_search_compiler_with_ordering_by_label_name(
    mock_annotation_client: MockerFixture,
    mock_assorted_aphia_ids_response: MockerFixture,
    mock_source_config: MockerFixture,
) -> None:
    """Test that ordering by annotation_creation_datetime works as expected."""
    mock_annotation_client.search_annotations.return_value = SimpleNamespace(
        ok=True,
        data=SimpleNamespace(
            results=mock_assorted_aphia_ids_response["results"],
            count=len(mock_assorted_aphia_ids_response["results"]),
            next=None,
            meta=SimpleNamespace(summary=None, info=None),
        ),
        error=None,
    )

    instance = AnnotationsAPIFetcher(
        source=mock_source_config,
        params=AnnotationSearchRequest(
            aphia_ids=[1],  # the 1 is irrelevant, as the mocked response intentionally returns 10 unordered results.
            order_by="label_name",
        ),
    )
    instance._make_request()
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
        data=SimpleNamespace(
            results=mock_assorted_aphia_ids_response["results"],
            count=len(mock_assorted_aphia_ids_response["results"]),
            next=None,
            meta=SimpleNamespace(summary=None, info=None),
        ),
        error=None,
    )

    # The '588' does nothing in this test case as the BODC/JNCC api's are mocked to return the same 10 results.
    combined_results = fetch_combined_results_from_annotation_apis(
        params=AnnotationSearchRequest(aphia_ids=[588]), request=mock_request_for_pagination
    )

    # The mocker is set to return 10 results, so this is whats expected in the outputted model.
    expected_individual_result_count = 10

    assert isinstance(combined_results.meta.source_counts, dict)

    assert combined_results.meta.source_counts["bodc"] == expected_individual_result_count
    assert combined_results.meta.source_counts["jncc"] == expected_individual_result_count

    # Check that the overall count is the combination of the two.
    assert combined_results.count == expected_individual_result_count * 2


@pytest.mark.parametrize("order_by", [None, "label_aphia_id", "annotation_creation_datetime", "label_name"])
def test_fetcher_forwards_ordering_to_each_upstream(
    mocker: MockerFixture, mock_request_for_pagination: Request, order_by: str | None
) -> None:
    """Ordering survives brokerage conversion and reaches both upstream HTTP requests."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"count": 0, "results": []})

    sources = [SourceConfig(name=name, label=name, base_url=f"http://{name}-api:8000/api") for name in ("bodc", "jncc")]
    mocker.patch(
        "brokerage_service_api.utilities.search_compiler.get_source_registry",
        return_value=SimpleNamespace(list=lambda: sources),
    )
    mocker.patch(
        "brokerage_service_api.utilities.search_compiler.AnnotationApiClient",
        side_effect=lambda source: AnnotationApiClient(source, transport=httpx.MockTransport(handler)),
    )

    fetch_combined_results_from_annotation_apis(
        AnnotationSearchRequest(aphia_ids=[588], order_by=order_by), mock_request_for_pagination
    )

    assert {request.url.host for request in requests} == {"bodc-api", "jncc-api"}
    for request in requests:
        assert request.url.params.get("order_by") == order_by
        assert request.url.params.get_list("aphia_ids[]") == ["588"]


@pytest.mark.parametrize("add_info", [True, False])
def test_compiler_carries_info_through_empty_pagination(
    monkeypatch: pytest.MonkeyPatch, mock_source_config: SourceConfig, add_info: bool
) -> None:
    """The regular search keeps the upstream Info contract when requested."""
    from brokerage_service_api.schemas.upstream import SearchResultInfo
    from brokerage_service_api.utilities.source import SourceRegistry

    info = SearchResultInfo(
        image_sets=[{"uuid": "00000000-0000-0000-0000-000000000001", "name": "Images"}],
        annotation_sets=[],
        aphia_ids=[{"aphia_id": 558, "scientific_name": "Porifera", "rank": "Phylum"}],
    )

    async def fetch(self: object, source: object, params: object) -> SimpleNamespace:
        assert params.add_info is add_info
        return SimpleNamespace(
            ok=True,
            data=SimpleNamespace(results=[], count=len([]), next=None, meta=SimpleNamespace(summary=None, info=info)),
        )

    monkeypatch.setattr(AnnotationsAPIFetcher, "_request_annotations", fetch)
    monkeypatch.setattr(
        "brokerage_service_api.utilities.search_compiler.get_source_registry",
        lambda: SourceRegistry([mock_source_config]),
    )
    request = Request({"type": "http", "query_string": b"name_part=cod"})
    result = fetch_combined_results_from_annotation_apis(
        AnnotationSearchRequest(name_part="cod", add_info=add_info), request
    )
    assert result.meta.info == (info if add_info else None)


def test_merge_info_deduplicates_identifiers_and_preserves_first_source() -> None:
    """Shared IDs yield one stable option, distinct IDs with the same name remain distinct."""
    from brokerage_service_api.schemas.upstream import SearchResultInfo
    from brokerage_service_api.utilities.search_compiler import merge_search_info

    first = SearchResultInfo(
        image_sets=[{"uuid": "00000000-0000-0000-0000-000000000001", "name": "Images"}],
        annotation_sets=[{"uuid": "00000000-0000-0000-0000-000000000002", "name": "Annotations"}],
        aphia_ids=[{"aphia_id": 558, "scientific_name": "Porifera", "rank": "Phylum"}],
    )
    second = first.model_copy(deep=True)
    second.aphia_ids[0] = second.aphia_ids[0].model_copy(update={"scientific_name": "Other name"})
    second.image_sets[0] = second.image_sets[0].model_copy(update={"uuid": second.annotation_sets[0].uuid})
    merged = merge_search_info([None, first, second])
    assert [item.name for item in merged.image_sets] == ["Images", "Images"]
    assert merged.annotation_sets == first.annotation_sets
    assert merged.aphia_ids == first.aphia_ids
    assert merge_search_info([None]) is None
    empty = SearchResultInfo(image_sets=[], annotation_sets=[], aphia_ids=[])
    assert merge_search_info([empty]) == empty
