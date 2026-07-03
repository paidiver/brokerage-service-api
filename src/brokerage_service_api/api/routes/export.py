"""Brokerage annotation export endpoint."""

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

from brokerage_service_api.schemas.upstream import AnnotationSearchParams, AnnotationSearchRequest
from brokerage_service_api.upstream.annotations import AnnotationApiClient
from brokerage_service_api.utilities.annotation_export import build_annotation_export_zip

router = APIRouter()


class AnnotationExportRequest(AnnotationSearchRequest):
    """Query parameters for annotation export requests."""

    sources: list[str] | None = None


@router.get(
    "/annotations/export",
    summary="Export annotation search results",
    description="Export matching annotation data as a ZIP containing CSV files.",
)
async def export_annotations(
    request: Request,
    params: Annotated[AnnotationExportRequest, Query()],
) -> Response:
    """Export matching annotations from one or more upstream annotation APIs."""
    configured_sources = request.app.state.sources

    if params.sources:
        available_sources = [source for source in configured_sources if source.name in params.sources]
    else:
        available_sources = configured_sources

    if not available_sources:
        raise HTTPException(
            status_code=400,
            detail="No matching upstream sources found.",
        )

    upstream_params = AnnotationSearchParams(**params.model_dump(exclude={"sources"}, exclude_none=True))

    try:
        tasks = [
            AnnotationApiClient(source).export_annotation_data(params=upstream_params) for source in available_sources
        ]
        upstream_responses = await asyncio.gather(*tasks)
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred whilst fetching the export data. {exc}",
        ) from None

    annotations = []
    images = []
    annotation_sets = []
    image_sets = []

    for upstream_response in upstream_responses:
        export_data = upstream_response.data

        if export_data is None:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Upstream annotations export returned no data.",
                    "upstream_response": upstream_response.model_dump()
                    if hasattr(upstream_response, "model_dump")
                    else str(upstream_response),
                },
            )

        annotations.extend(export_data.annotations)
        images.extend(export_data.images)
        annotation_sets.extend(export_data.annotation_sets)
        image_sets.extend(export_data.image_sets)

    zip_bytes = build_annotation_export_zip(
        annotations=annotations,
        images=images,
        annotation_sets=annotation_sets,
        image_sets=image_sets,
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="annotation_export.zip"',
        },
    )
