#!/usr/bin/env python3
"""Ingest image-set metadata and annotation spreadsheets into the annotations API."""

import argparse
import json
import os
from pathlib import Path

import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")

IMAGE_SET_ENDPOINT = f"{BASE_URL}/api/ingest/image-set"
ANNOTATION_ENDPOINT = f"{BASE_URL}/api/annotations/upload_annotation/"

XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def get_headers() -> dict[str, str]:
    """Build common headers for annotations API requests."""
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }


def ingest_image_set(json_path: Path) -> dict:
    """Submit an image-set JSON file to the annotations API."""
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    headers = {
        **get_headers(),
        "Content-Type": "application/json",
    }
    response = requests.post(
        IMAGE_SET_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=60,
    )
    print(f"Image set ingestion response status code: {response.status_code}")
    print(f"Image set ingestion response content: {response.text}")

    response.raise_for_status()
    return response.json()


def upload_annotation_file(excel_path: Path) -> dict:
    """Upload an annotation spreadsheet to the annotations API."""
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    if excel_path.suffix.lower() != ".xlsx":
        raise ValueError(f"Expected a .xlsx file, got: {excel_path}")

    headers = get_headers()

    with excel_path.open("rb") as file:
        files = {
            "file": (
                excel_path.name,
                file,
                XLSX_MIME_TYPE,
            )
        }

        response = requests.post(
            ANNOTATION_ENDPOINT,
            headers=headers,
            files=files,
            timeout=600,
        )

    response.raise_for_status()
    return response.json()


def main() -> None:
    """Run the ingestion script from command-line arguments."""
    parser = argparse.ArgumentParser(description="Ingest image-set JSON and upload annotation Excel file.")

    parser.add_argument(
        "image_json",
        type=Path,
        help="Path to the image-set JSON file.",
    )

    parser.add_argument(
        "annotation_xlsx",
        type=Path,
        help="Path to the annotation Excel .xlsx file.",
    )

    args = parser.parse_args()

    print("Sending image set JSON...")
    image_response = ingest_image_set(args.image_json)
    print("Image set response:")
    print(json.dumps(image_response, indent=2))

    print("Uploading annotation Excel file...")
    annotation_response = upload_annotation_file(args.annotation_xlsx)
    print("Annotation response:")
    print(json.dumps(annotation_response, indent=2))

    print("Done.")


if __name__ == "__main__":
    main()

# export API_AUTH_TOKEN="70bb17dd3ff2ae653a61025c7a5c7d0d984c3f6c"
# export API_AUTH_TOKEN="9617726de74f8093b4ba3dfb466d018a21b2d42a"
# export API_BASE_URL="https://annotations-api.paidiver.site"
# export API_BASE_URL="https://annotationsdev.bodc.ac.uk"
# python ingest_data.py sample_jncc.json sample_jncc_annotations.xlsx
