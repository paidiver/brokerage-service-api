"""Demo endpoint for downloading images as a zip file."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse


router = APIRouter()


def fetch_images(image_urls: list[str]) -> BytesIO:
    """Download the images and return them in an in-memory zip file."""
    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for image_url in image_urls:
            print(f"Downloading file: {image_url}")
            response = httpx.get(image_url, follow_redirects=True)
            response.raise_for_status()

            file_name = image_url.rsplit("/", maxsplit=1)[-1] or "image"
            zip_file.writestr(file_name, response.content)
            print(f"Added file to zip: {file_name}")

    zip_buffer.seek(0)
    return zip_buffer


@router.get("/download_zip_demo")
async def brokerage_search() -> StreamingResponse:
    """Demo endpoint to investigate image downloads."""
    image_urls = [
        "https://dap.ceda.ac.uk/bodc/deposits01/USO230175/GHF_Mosaicked_Tiles_2012/M58_10441297_12987744811443.jpg",
        "https://jncc.resourcespace.com/iiif/image/8552/full/max/0/default.jpg",
    ]

    zip_file = fetch_images(image_urls=image_urls)

    return StreamingResponse(
        zip_file,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=requested_images.zip"},
    )
