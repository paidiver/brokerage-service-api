"""Tests for annotation export ZIP utilities."""

from __future__ import annotations

import csv
import io
import zipfile

from brokerage_service_api.utilities.annotation_export import build_annotation_export_zip


def _read_zip_csv(zip_bytes: bytes, filename: str) -> list[list[str]]:
    """Read a CSV file from ZIP bytes."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        with archive.open(filename) as csv_file:
            text = io.TextIOWrapper(csv_file, encoding="utf-8", newline="")
            return list(csv.reader(text))


def test_build_annotation_export_zip_contains_expected_files() -> None:
    """The export ZIP contains the four expected CSV files."""
    zip_bytes = build_annotation_export_zip(
        annotations=[],
        images=[],
        annotation_sets=[],
        image_sets=[],
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        assert sorted(archive.namelist()) == [
            "annotation_set.csv",
            "annotations.csv",
            "image_set.csv",
            "images.csv",
        ]


def test_build_annotation_export_zip_writes_flat_annotation_and_image_csvs() -> None:
    """The flat CSV files are populated from annotation and image rows."""
    zip_bytes = build_annotation_export_zip(
        annotations=[
            {
                "image_handle": "https://example.org/image",
                "image_uuid": "image-uuid-1",
                "annotation_platform": "BIIGLE",
                "image_filename": "image_1.jpg",
                "annotation_human_creator": "Annotator One",
                "annotation_creation_datetime": "2026-07-01T14:43:40Z",
                "annotation_label_name": "Label 47575acb7eae",
                "annotation_shape_name": "rectangle",
                "annotation_coordinates": [[1, 2, 3, 4]],
                "annotation_set_name": "AnnotationSet One",
            }
        ],
        images=[
            {
                "image_filename": "image_1.jpg",
                "image_datetime": "2026-07-01T14:43:40Z",
                "image_longitude": -3.1,
                "image_latitude": 57.4,
                "image_depth": -100.5,
                "image_uuid": "image-uuid-1",
                "image_hash_sha256": "abc123",
                "image_area_square_meter": 12.5,
                "image_meters_above_ground": 3.2,
                "image_acquisition_settings": {"iso": 400, "exposure": 1200},
                "image_set_name": "ImageSet One",
            }
        ],
        annotation_sets=[],
        image_sets=[],
    )

    annotations_csv = _read_zip_csv(zip_bytes, "annotations.csv")
    images_csv = _read_zip_csv(zip_bytes, "images.csv")

    assert annotations_csv[0] == [
        "image-handle",
        "image-uuid",
        "annotation-platform",
        "image-filename",
        "annotation-human-creator",
        "annotation-creation-datetime",
        "annotation-label-name",
        "annotation-shape-name",
        "annotation-coordinates",
        "annotation-set-name",
    ]
    assert annotations_csv[1][0] == "https://example.org/image"
    assert annotations_csv[1][8] == "[[1, 2, 3, 4]]"

    assert images_csv[0] == [
        "image-filename",
        "image-datetime",
        "image-longitude",
        "image-latitude",
        "image-depth",
        "image-uuid",
        "image-hash-sha256",
        "image-area-square-meter",
        "image-meters-above-ground",
        "image-acquisition-settings",
        "image-set-name",
    ]
    assert images_csv[1][0] == "image_1.jpg"
    assert images_csv[1][9] == '{"iso": 400, "exposure": 1200}'


def test_build_annotation_export_zip_writes_transposed_set_csvs_with_uris() -> None:
    """The transposed set CSVs include name and URI subfields."""
    zip_bytes = build_annotation_export_zip(
        annotations=[],
        images=[],
        annotation_sets=[
            {
                "annotation_set_name": "AnnotationSet One",
                "annotation_project_name": "Project One",
                "annotation_project_uri": "https://example.org/project",
                "annotation_context_name": "Context One",
                "annotation_context_uri": "https://example.org/context",
                "annotation_creators": [
                    {"name": "Creator One", "uri": "https://example.org/creator-one"},
                    {"name": "Creator Two", "uri": "https://example.org/creator-two"},
                ],
                "annotation_pi_name": "PI One",
                "annotation_pi_uri": "https://example.org/pi",
                "annotation_license_name": "License One",
                "annotation_license_uri": "https://example.org/license",
                "annotation_set_uuid": "annotation-set-uuid-1",
                "annotation_image_set_name": "ImageSet One",
                "annotation_image_set_uuid": "image-set-uuid-1",
            }
        ],
        image_sets=[
            {
                "image_set_name": "ImageSet One",
                "image_project_name": "Image Project One",
                "image_project_uri": "https://example.org/image-project",
                "image_context_name": "Image Context One",
                "image_context_uri": "https://example.org/image-context",
                "image_event_name": "Event One",
                "image_event_uri": "https://example.org/event",
                "image_platform_name": "Platform One",
                "image_platform_uri": "https://example.org/platform",
                "image_sensor_name": "Sensor One",
                "image_sensor_uri": "https://example.org/sensor",
                "image_creators": [{"name": "Image Creator One", "uri": "https://example.org/image-creator-one"}],
                "image_pi_name": "Image PI One",
                "image_pi_uri": "https://example.org/image-pi",
                "image_license_name": "Image License One",
                "image_license_uri": "https://example.org/image-license",
                "image_set_uuid": "image-set-uuid-1",
            }
        ],
    )

    annotation_set_csv = _read_zip_csv(zip_bytes, "annotation_set.csv")
    image_set_csv = _read_zip_csv(zip_bytes, "image_set.csv")

    assert annotation_set_csv[0] == ["iFDO fields", "subfields", "Annotation_set 1"]
    assert ["annotation-project", "name", "Project One"] in annotation_set_csv
    assert ["", "uri", "https://example.org/project"] in annotation_set_csv
    assert ["annotation-creators", "name", "Creator One; Creator Two"] in annotation_set_csv
    assert [
        "",
        "uri",
        "https://example.org/creator-one; https://example.org/creator-two",
    ] in annotation_set_csv

    assert image_set_csv[0] == ["iFDO fields", "subfields", "Image_set 1"]
    assert ["image-project", "name", "Image Project One"] in image_set_csv
    assert ["", "uri", "https://example.org/image-project"] in image_set_csv
    assert ["image-creators", "name", "Image Creator One"] in image_set_csv
    assert ["", "uri", "https://example.org/image-creator-one"] in image_set_csv
