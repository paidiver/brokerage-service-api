"""Main brokerage search endpoint."""

from pathlib import Path
import requests as rq
import tempfile

from fastapi import APIRouter, Request


router = APIRouter()


def fetch_images(image_url: str):
    """Download the images and save to a temporary directory."""
    response = rq.get(image_url)
    response.raise_for_status()

    if (image_bytes := response.content):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = image_url.rsplit("/")[-1]
            full_file_path = Path(temp_dir) / file_name
            full_file_path.write_bytes(image_bytes)

@router.get("/download_zip_demo",)
async def brokerage_search(request: Request):
    """Demo endpoint to investigate image downloads.
    Raises:
        Exception
      
    """
    fetch_images(
        image_url="https://dap.ceda.ac.uk/bodc/deposits01/USO230175/GHF_Mosaicked_Tiles_2012/M58_10441297_12987744811443.jpg")
    return "hello world."