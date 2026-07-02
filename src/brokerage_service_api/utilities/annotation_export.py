"""Utilities for building annotation export ZIP files."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Iterable
from typing import Any

ANNOTATIONS_COLUMNS = [
    ("image-handle", "image_handle"),
    ("image-uuid", "image_uuid"),
    ("annotation-platform", "annotation_platform"),
    ("image-filename", "image_filename"),
    ("annotation-human-creator", "annotation_human_creator"),
    ("annotation-creation-datetime", "annotation_creation_datetime"),
    ("annotation-label-name", "annotation_label_name"),
    ("annotation-shape-name", "annotation_shape_name"),
    ("annotation-coordinates", "annotation_coordinates"),
    ("annotation-set-name", "annotation_set_name"),
]


IMAGES_COLUMNS = [
    ("image-filename", "image_filename"),
    ("image-datetime", "image_datetime"),
    ("image-longitude", "image_longitude"),
    ("image-latitude", "image_latitude"),
    ("image-depth", "image_depth"),
    ("image-uuid", "image_uuid"),
    ("image-hash-sha256", "image_hash_sha256"),
    ("image-area-square-meter", "image_area_square_meter"),
    ("image-meters-above-ground", "image_meters_above_ground"),
    ("image-acquisition-settings", "image_acquisition_settings"),
    ("image-set-name", "image_set_name"),
]


ANNOTATION_SET_FIELDS = [
    ("annotation-set-name", "", "annotation_set_name"),
    ("annotation-project", "name", "annotation_project_name"),
    ("", "uri", "annotation_project_uri"),
    ("annotation-context", "name", "annotation_context_name"),
    ("", "uri", "annotation_context_uri"),
    ("annotation-abstract", "", "annotation_abstract"),
    ("annotation-objective", "", "annotation_objective"),
    ("annotation-target-environment", "", "annotation_target_environment"),
    ("annotation-target-timescale", "", "annotation_target_timescale"),
    ("annotation-curation-protocol", "", "annotation_curation_protocol"),
    ("annotation-creators", "name", "annotation_creators_names"),
    ("", "uri", "annotation_creators_uris"),
    ("annotation-pi", "name", "annotation_pi_name"),
    ("", "uri", "annotation_pi_uri"),
    ("annotation-license", "name", "annotation_license_name"),
    ("", "uri", "annotation_license_uri"),
    ("annotation-copyright", "", "annotation_copyright"),
    ("annotation-set-uuid", "", "annotation_set_uuid"),
    ("annotation-set-handle", "", "annotation_set_handle"),
    ("annotation-set-version", "", "annotation_set_version"),
    ("annotation-image-set-name", "", "annotation_image_set_name"),
    ("annotation-image-set-uuid", "", "annotation_image_set_uuid"),
    ("annotation-image-set-handle", "", "annotation_image_set_handle"),
]


IMAGE_SET_FIELDS = [
    ("image-set-name", "", "image_set_name"),
    ("image-project", "name", "image_project_name"),
    ("", "uri", "image_project_uri"),
    ("image-context", "name", "image_context_name"),
    ("", "uri", "image_context_uri"),
    ("image-abstract", "", "image_abstract"),
    ("image-event", "name", "image_event_name"),
    ("", "uri", "image_event_uri"),
    ("image-platform", "name", "image_platform_name"),
    ("", "uri", "image_platform_uri"),
    ("image-sensor", "name", "image_sensor_name"),
    ("", "uri", "image_sensor_uri"),
    ("image-set-uuid", "", "image_set_uuid"),
    ("image-set-handle", "", "image_set_handle"),
    ("image-creators", "name", "image_creators_names"),
    ("", "uri", "image_creators_uris"),
    ("image-pi", "name", "image_pi_name"),
    ("", "uri", "image_pi_uri"),
    ("image-license", "name", "image_license_name"),
    ("", "uri", "image_license_uri"),
    ("image-copyright", "", "image_copyright"),
    ("image-acquisition", "", "image_acquisition"),
    ("image-quality", "", "image_quality"),
    ("image-deployment", "", "image_deployment"),
    ("image-navigation", "", "image_navigation"),
    ("image-scale-reference", "", "image_scale_reference"),
    ("image-illumination", "", "image_illumination"),
    ("image-resolution", "", "image_resolution"),
    ("image-marine-zone", "", "image_marine_zone"),
    ("image-spectral-resolution", "", "image_spectral_resolution"),
    ("image-capture-mode", "", "image_capture_mode"),
    ("image-spatial-constraints", "", "image_spatial_constraints"),
    ("image-temporal-constraints", "", "image_temporal_constraints"),
    ("image-target-environment", "", "image_target_environment"),
    ("image-objective", "", "image_objective"),
    ("image-time-synchronisation", "", "image_time_synchronisation"),
    ("image-item-identification-scheme", "", "image_item_identification_scheme"),
    ("image-curation-protocol", "", "image_curation_protocol"),
    ("image-acquisition-settings", "", "image_acquisition_settings"),
    ("image-set-start-datetime", "", "image_set_start_datetime"),
    ("image-set-lat-min", "", "image_set_lat_min"),
    ("image-set-lat-max", "", "image_set_lat_max"),
    ("image-set-long-min", "", "image_set_long_min"),
    ("image-set-long-max", "", "image_set_long_max"),
]

def build_annotation_export_zip(
    *,
    annotations: list[dict[str, Any]],
    images: list[dict[str, Any]],
    annotation_sets: list[dict[str, Any]],
    image_sets: list[dict[str, Any]],
) -> bytes:
    """Build a ZIP file containing annotation export CSVs.

    Args:
        annotations: Annotation export rows.
        images: Image export rows.
        annotation_sets: Annotation set export rows.
        image_sets: Image set export rows.

    Returns:
        ZIP file bytes.
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "annotations.csv",
            _build_flat_csv(rows=annotations, columns=ANNOTATIONS_COLUMNS),
        )
        archive.writestr(
            "images.csv",
            _build_flat_csv(rows=images, columns=IMAGES_COLUMNS),
        )
        archive.writestr(
            "annotation_set.csv",
            _build_annotation_set_csv(annotation_sets),
        )
        archive.writestr(
            "image_set.csv",
            _build_image_set_csv(image_sets),
        )

    return zip_buffer.getvalue()


def _build_flat_csv(
    *,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
) -> str:
    """Build a normal row-oriented CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([header for header, _field_name in columns])

    for row in rows:
        writer.writerow([_format_value(row.get(field_name)) for _header, field_name in columns])

    return output.getvalue()


def _build_annotation_set_csv(annotation_sets: list[dict[str, Any]]) -> str:
    """Build the transposed annotation_set.csv."""
    prepared_rows = [_with_creator_fields(row, "annotation_creators") for row in annotation_sets]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "iFDO fields",
            "subfields",
            *[f"Annotation_set {index}" for index in range(1, len(prepared_rows) + 1)],
        ]
    )

    for ifdo_field, subfield, field_name in ANNOTATION_SET_FIELDS:
        writer.writerow(
            [
                ifdo_field,
                subfield,
                *[_format_value(row.get(field_name)) for row in prepared_rows],
            ]
        )

    return output.getvalue()


def _build_image_set_csv(image_sets: list[dict[str, Any]]) -> str:
    """Build the transposed image_set.csv."""
    prepared_rows = [_with_creator_fields(row, "image_creators") for row in image_sets]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "iFDO fields",
            "subfields",
            *[f"Image_set {index}" for index in range(1, len(prepared_rows) + 1)],
        ]
    )

    for ifdo_field, subfield, field_name in IMAGE_SET_FIELDS:
        writer.writerow(
            [
                ifdo_field,
                subfield,
                *[_format_value(row.get(field_name)) for row in prepared_rows],
            ]
        )

    return output.getvalue()


def _with_creator_fields(row: dict[str, Any], creators_field: str) -> dict[str, Any]:
    """Add flattened creator name/URI fields to a row."""
    row = dict(row)
    creators = row.get(creators_field) or []

    row[f"{creators_field}_names"] = _join_creator_values(creators, "name")
    row[f"{creators_field}_uris"] = _join_creator_values(creators, "uri")

    return row


def _join_creator_values(creators: Iterable[dict[str, Any]], field_name: str) -> str:
    """Join creator values into a single CSV cell."""
    values = [str(creator.get(field_name)) for creator in creators if creator.get(field_name)]
    return "; ".join(values)


def _format_value(value: Any) -> str:
    """Format a Python value for CSV output."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, bool | int | float):
        return str(value)

    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False)

    return str(value)
