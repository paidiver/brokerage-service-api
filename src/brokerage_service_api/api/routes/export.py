"""Brokerage annotation export endpoint."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response

from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.schemas.upstream import AnnotationExportData, AnnotationSearchParams, AnnotationSearchRequest
from brokerage_service_api.upstream.annotations import AnnotationApiClient, UpstreamResponse
from brokerage_service_api.utilities.annotation_export import build_annotation_export_zip
from brokerage_service_api.utilities.source import calculate_available_sources

router = APIRouter()


class AnnotationExportRequest(AnnotationSearchRequest):
    """Query parameters for annotation export requests."""

    sources: list[str] | None = None


@router.get(
    "/annotations/export",
    summary="Export annotation search results",
    description="Export matching annotation data as a ZIP containing CSV files.",
    response_class=Response,
    responses={200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def export_annotations(
    request: Request,
    params: Annotated[AnnotationExportRequest, Query()],
) -> Response:
    """Export matching annotations from one or more upstream annotation APIs."""
    available_sources = calculate_available_sources(request, params.sources)

    upstream_params = AnnotationSearchParams(**params.model_dump(exclude={"sources"}, exclude_none=True))

    async def fetch(source: SourceConfig) -> UpstreamResponse[AnnotationExportData]:
        async with AnnotationApiClient(source) as client:
            return await client.export_annotation_data(params=upstream_params)

    upstream_responses = await asyncio.gather(*(fetch(source) for source in available_sources))

    annotations = []
    images = []
    annotation_sets = []
    image_sets = []

    for upstream_response in upstream_responses:
        export_data = upstream_response.data

        if not upstream_response.ok or export_data is None:
            raise HTTPException(
                502, detail={"code": "upstream_failed", "message": "An export source failed. Please retry."}
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
