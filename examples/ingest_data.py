"""Example code for data ingestion."""
#!/usr/bin/env python3

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
    """Build and return the default HTTP headers used for API requests.

    Returns:
        dict[str, str]: A dictionary containing standard headers including
        JSON acceptance and Bearer authentication token.
    """
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }


def ingest_image_set(json_path: Path) -> dict:
    """Upload an image set JSON file to the ingestion API endpoint.

    This function:
    - Validates that the JSON file exists
    - Loads and parses the JSON payload
    - Sends a POST request to the image-set ingestion endpoint
    - Prints response status and body for debugging
    - Returns the parsed JSON response

    Args:
        json_path (Path): Path to the image-set JSON file.

    Returns:
        dict: JSON response from the API.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        requests.HTTPError: If the API request fails.
    """
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
    """Upload an annotation Excel (.xlsx) file to the annotation API endpoint.

    This function:
    - Validates file existence
    - Ensures file is .xlsx format
    - Uploads file using multipart/form-data
    - Sends request with authentication headers
    - Returns parsed JSON response

    Args:
        excel_path (Path): Path to the annotation Excel file.

    Returns:
        dict: JSON response from the API.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file is not .xlsx format.
        requests.HTTPError: If upload request fails.
    """
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
    """CLI entry point for ingesting an image set and uploading annotations.

    Workflow:
    1. Parse command-line arguments
    2. Send image set JSON to API
    3. Upload annotation Excel file
    4. Print formatted responses

    Args:
        None

    Returns:
        None
    """
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
