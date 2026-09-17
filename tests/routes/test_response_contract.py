"""Cross-endpoint contract regressions, including failure and pagination semantics."""

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from brokerage_service_api.api.app import create_app
from brokerage_service_api.models.search_model import Result, Results
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationExportData, TaxaCollection
from brokerage_service_api.utilities.search_compiler import results_with_pagination_applied
from fastapi import Request


@pytest.mark.anyio
async def test_errors_have_one_shape_and_media_type(client: httpx.AsyncClient) -> None:
    """Routing and validation failures use the same safe contract."""
    for path, code in (
        ("/api/missing", HTTPStatus.NOT_FOUND),
        ("/api/annotations/search", HTTPStatus.UNPROCESSABLE_ENTITY),
    ):
        response = await client.get(path)
        assert response.status_code == code
        assert response.headers["content-type"] == "application/problem+json"
        data = response.json()
        assert data["status"] == code
        assert isinstance(data["detail"], str)
        assert {"type", "title", "status", "detail", "code"} <= data.keys()
    assert response.json()["errors"]


@pytest.mark.anyio
async def test_taxonomy_does_not_hide_partial_failure(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even one failed source prevents an apparently complete success."""
    sources = [SourceConfig(name=name, label=name, base_url=f"https://{name}.example") for name in ("a", "b")]
    client._transport.app.state.sources = sources
    monkeypatch.setattr(
        "brokerage_service_api.upstream.annotations.AnnotationApiClient.search_taxa_by_name_part",
        AsyncMock(
            side_effect=[
                SimpleNamespace(ok=True, data=TaxaCollection(count=0, results=[])),
                SimpleNamespace(ok=False, data=None),
            ]
        ),
    )
    response = await client.get("/api/taxonomy/worms/taxa/cod")
    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert response.json()["code"] == "upstream_failed"
    assert "results" not in response.json()


@pytest.mark.anyio
async def test_export_remains_binary_and_errors_are_problems(
    client: httpx.AsyncClient, bodc_source: SourceConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The export is a ZIP on success, a problem document on failure."""
    client._transport.app.state.sources = [bodc_source]
    mock = AsyncMock(return_value=SimpleNamespace(ok=True, data=AnnotationExportData()))
    monkeypatch.setattr("brokerage_service_api.upstream.annotations.AnnotationApiClient.export_annotation_data", mock)
    response = await client.get("/api/annotations/export", params={"name_part": "cod"})
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "application/zip"
    assert response.content.startswith(b"PK")
    mock.return_value = SimpleNamespace(ok=False, data=None)
    response = await client.get("/api/annotations/export", params={"name_part": "cod"})
    assert response.status_code == HTTPStatus.BAD_GATEWAY
    assert response.headers["content-type"] == "application/problem+json"


def test_pagination_links_preserve_filters_and_terminate(mock_assorted_aphia_ids_response: dict) -> None:
    """Clients can follow absolute URLs to the last page without repeats."""
    rows = [
        Result.construct_instance_from_raw_response(row, "bodc") for row in mock_assorted_aphia_ids_response["results"]
    ]
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("api.example", 443),
            "path": "/api/annotations/search",
            "headers": [],
            "query_string": b"page=1&aphia_ids=1&aphia_ids=2&page_size=3",
        }
    )
    all_results = Results(annotations=rows)
    first = results_with_pagination_applied(len(rows), all_results, 3, 1, request)
    assert first.previous is None
    assert first.next.startswith("https://api.example/api/annotations/search?")
    assert parse_qs(urlsplit(first.next).query)["aphia_ids"] == ["1", "2"]
    last = results_with_pagination_applied(len(rows), all_results, 3, 4, request)
    assert last.next is None
    assert parse_qs(urlsplit(last.previous).query)["page"] == ["3"]
    assert isinstance(last.results, list)
    assert last.meta.source_counts == {"bodc": len(rows)}


def test_openapi_matches_collection_and_problem_contracts() -> None:
    """Generated documentation references real models and actual media types."""
    schema = create_app().openapi()
    for path in ("/api/sources", "/api/annotations/search", "/api/taxonomy/worms/taxa/{name_part}"):
        responses = schema["paths"][path]["get"]["responses"]
        ref = responses["200"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        assert schema["components"]["schemas"][ref]["properties"]["results"]["type"] == "array"
        assert set(responses["422"]["content"]) == {"application/problem+json"}
    assert "FieldError" in schema["components"]["schemas"]
    assert set(schema["paths"]["/api/annotations/export"]["get"]["responses"]["200"]["content"]) == {"application/zip"}
