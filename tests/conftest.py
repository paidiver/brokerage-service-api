"""Pytest fixtures for testing the PostGIS API."""

from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from brokerage_service_api.api.app import create_app
from brokerage_service_api.models.sources import SourceConfig
from fastapi import FastAPI

DEFAULT_PORT = 8000


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio."""
    return "asyncio"


@pytest.fixture
def app() -> Generator[FastAPI, None, None]:
    """Create a FastAPI app with the DB dependency overridden.

    Yields:
        FastAPI: A FastAPI application instance
    """
    app = create_app()
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide a FastAPI test client.

    Args:
        app (FastAPI): The FastAPI application to test.

    Yields:
        AsyncClient: A test client for the FastAPI application.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url=f"http://testserver:{DEFAULT_PORT}",
    ) as test_client:
        yield test_client


@pytest.fixture
def bodc_source() -> SourceConfig:
    """Provide a BODC test source configuration.

    Returns:
        SourceConfig: A test configuration for the BODC source.
    """
    return SourceConfig(
        name="bodc",
        label="British Oceanographic Data Centre",
        base_url="http://bodc-api:8000/",
        enabled=True,
    )


@pytest.fixture
def jncc_source() -> SourceConfig:
    """Provide a JNCC test source configuration.

    Returns:
        SourceConfig: A test configuration for the JNCC source.
    """
    return SourceConfig(
        name="jncc",
        label="Joint Nature Conservation Committee",
        base_url="http://jncc-api:8000/",
        enabled=True,
    )


@pytest.fixture(name="mock_assorted_aphia_ids_response")
def mock_response_with_differing_aphia_ids() -> dict:
    """An assortment of uniform responses with varying Aphia ID's."""
    return {
        "count": 1,
        "next": None,
        "previous": None,
        "results": {
            "annotations": [
                {
                    "creation_datetime": "2012-12-31T23:59:59Z",
                    "uuid": "987ba073-fcca-4242-85c6-c8ae990a0480",
                    "annotation_set_uuid": "36c33463-16fe-4ba4-bf1c-490a0b0c1653",
                    "annotation_set_name": "Trial Data",
                    "image_set_name": "image_set_1",
                    "image_set_uuid": "822731b4-a6b7-476f-887e-debf00bfa6ba",
                    "image_filename": "image_001.jpg",
                    "image_handle": "image_001_url.jpg",
                    "image_uuid": "1345c48a-d360-4d48-8737-2f94a1c9517b",
                    "label_name": "porifera_01",
                    "label_aphia_id": 558,
                    "annotation_platform": "ImagePro",
                    "annotation_creation_datetime": "2012-12-31T23:59:59Z",
                    "annotation_shape": "single-pixel",
                    "annotation_coordinates": [[1359.0, 2909.0]],
                    "annotation_dimension_pixels": 366.9346,
                    "annotator_name": "Jane Doe",
                },
                {
                    "creation_datetime": "2013-01-01T10:15:00Z",
                    "uuid": "d2d6bc83-10d6-4bd6-a0f0-c5fd52275f8d",
                    "annotation_set_uuid": "76d4cc1f-458e-4b71-b3f2-2d7e00dfe491",
                    "annotation_set_name": "Survey A",
                    "image_set_name": "image_set_2",
                    "image_set_uuid": "2a75a2ef-d04f-4d1b-a4a0-f29c8db5a4b9",
                    "image_filename": "image_002.jpg",
                    "image_handle": "image_002_url.jpg",
                    "image_uuid": "b8d2b1d8-9861-4707-a0c3-8eb6a65d9635",
                    "label_name": "porifera_02",
                    "label_aphia_id": 17,
                    "annotation_platform": "SQUIDLE+",
                    "annotation_creation_datetime": "2013-01-01T10:15:00Z",
                    "annotation_shape": "bounding-box",
                    "annotation_coordinates": [[500.0, 700.0], [650.0, 850.0]],
                    "annotation_dimension_pixels": 212.5,
                    "annotator_name": "John Smith",
                },
                {
                    "creation_datetime": "2014-05-22T14:33:45Z",
                    "uuid": "55f7d8f6-1e82-4c45-9b4e-f87d64b930d5",
                    "annotation_set_uuid": "f2dc6cb3-587f-47d4-9d2b-24346a4329ef",
                    "annotation_set_name": "Survey B",
                    "image_set_name": "image_set_3",
                    "image_set_uuid": "e40a7f4e-88c8-4654-a4b8-8fd7b83f4db3",
                    "image_filename": "image_003.jpg",
                    "image_handle": "image_003_url.jpg",
                    "image_uuid": "93b0df8c-1d7b-40e0-bcb4-9fd3e2c9d2df",
                    "label_name": "porifera_03",
                    "label_aphia_id": 84,
                    "annotation_platform": "BIIGLE",
                    "annotation_creation_datetime": "2014-05-22T14:33:45Z",
                    "annotation_shape": "polygon",
                    "annotation_coordinates": [[100.0, 100.0], [120.0, 180.0], [180.0, 140.0]],
                    "annotation_dimension_pixels": 154.2,
                    "annotator_name": "Alice Brown",
                },
                {
                    "creation_datetime": "2015-07-09T09:22:11Z",
                    "uuid": "5c4a3b28-cdf7-4a70-a5b5-5bb7c96d4fd1",
                    "annotation_set_uuid": "4fd15d79-15fd-4c47-8c5e-fcbecb4c6fa2",
                    "annotation_set_name": "Survey C",
                    "image_set_name": "image_set_4",
                    "image_set_uuid": "8f7297d7-52f4-4af9-b5a5-73d5fd91315c",
                    "image_filename": "image_004.jpg",
                    "image_handle": "image_004_url.jpg",
                    "image_uuid": "b08eb17b-4ca9-4e37-b66e-fec4ebad82dc",
                    "label_name": "cnidaria_01",
                    "label_aphia_id": 129,
                    "annotation_platform": "ImagePro",
                    "annotation_creation_datetime": "2015-07-09T09:22:11Z",
                    "annotation_shape": "circle",
                    "annotation_coordinates": [[640.0, 480.0]],
                    "annotation_dimension_pixels": 98.4,
                    "annotator_name": "Emily White",
                },
                {
                    "creation_datetime": "2016-03-18T16:05:09Z",
                    "uuid": "c5d8f86f-0561-4898-a2f7-6768579c839d",
                    "annotation_set_uuid": "6db21e83-8a79-45a5-8b84-8446a8e58db4",
                    "annotation_set_name": "Survey D",
                    "image_set_name": "image_set_5",
                    "image_set_uuid": "05e89998-d741-4b9b-91e5-9c613d6b68b2",
                    "image_filename": "image_005.jpg",
                    "image_handle": "image_005_url.jpg",
                    "image_uuid": "cf34ca2c-2339-478c-9034-6aabbe5d9d1d",
                    "label_name": "echinodermata_01",
                    "label_aphia_id": 246,
                    "annotation_platform": "SQUIDLE+",
                    "annotation_creation_datetime": "2016-03-18T16:05:09Z",
                    "annotation_shape": "line",
                    "annotation_coordinates": [[200.0, 300.0], [450.0, 600.0]],
                    "annotation_dimension_pixels": 275.8,
                    "annotator_name": "Chris Green",
                },
                {
                    "creation_datetime": "2017-11-02T12:47:30Z",
                    "uuid": "9d923ef4-7098-42d0-b4fd-f519d2e4870d",
                    "annotation_set_uuid": "95f624af-f851-40b4-bd1c-08c278ad6f67",
                    "annotation_set_name": "Survey E",
                    "image_set_name": "image_set_6",
                    "image_set_uuid": "dd60fb60-4d5f-49ec-9237-dc2c89ef2f5b",
                    "image_filename": "image_006.jpg",
                    "image_handle": "image_006_url.jpg",
                    "image_uuid": "6b53f4df-c5cb-45c4-bdc5-c81c7a97db75",
                    "label_name": "annelida_01",
                    "label_aphia_id": 377,
                    "annotation_platform": "BIIGLE",
                    "annotation_creation_datetime": "2017-11-02T12:47:30Z",
                    "annotation_shape": "rectangle",
                    "annotation_coordinates": [[250.0, 250.0], [500.0, 500.0]],
                    "annotation_dimension_pixels": 330.1,
                    "annotator_name": "Sarah Black",
                },
                {
                    "creation_datetime": "2018-08-14T08:18:55Z",
                    "uuid": "dc91b9a5-23d7-4b9e-84ec-36a94dd7a329",
                    "annotation_set_uuid": "0b9cbb2d-12cb-4d7f-b6c4-b40fef93a6db",
                    "annotation_set_name": "Survey F",
                    "image_set_name": "image_set_7",
                    "image_set_uuid": "24a98f5d-fdbe-43c3-a42d-97f8bbec7335",
                    "image_filename": "image_007.jpg",
                    "image_handle": "image_007_url.jpg",
                    "image_uuid": "6a858d46-cf65-4e87-ae69-6c66020d98dd",
                    "label_name": "mollusca_01",
                    "label_aphia_id": 491,
                    "annotation_platform": "ImagePro",
                    "annotation_creation_datetime": "2018-08-14T08:18:55Z",
                    "annotation_shape": "ellipse",
                    "annotation_coordinates": [[800.0, 900.0]],
                    "annotation_dimension_pixels": 142.7,
                    "annotator_name": "David Gray",
                },
                {
                    "creation_datetime": "2019-06-25T15:10:41Z",
                    "uuid": "af8f17f3-cc28-4c63-a26b-b76758d53ef4",
                    "annotation_set_uuid": "718f06d4-5717-4835-aacb-dcc1dbce5e5d",
                    "annotation_set_name": "Survey G",
                    "image_set_name": "image_set_8",
                    "image_set_uuid": "983e5277-15e9-41b8-b19b-9d2b780f42b6",
                    "image_filename": "image_008.jpg",
                    "image_handle": "image_008_url.jpg",
                    "image_uuid": "adf9df55-a1f7-4794-b8e9-ff0f76dbb1c2",
                    "label_name": "arthropoda_01",
                    "label_aphia_id": 612,
                    "annotation_platform": "SQUIDLE+",
                    "annotation_creation_datetime": "2019-06-25T15:10:41Z",
                    "annotation_shape": "point",
                    "annotation_coordinates": [[1024.0, 768.0]],
                    "annotation_dimension_pixels": 12.0,
                    "annotator_name": "Laura King",
                },
                {
                    "creation_datetime": "2020-02-29T20:55:14Z",
                    "uuid": "cbcbde98-7c0b-4b98-a6b0-85d2c4c4d882",
                    "annotation_set_uuid": "f37643d5-b66d-4c55-9d9d-56e29fb3bafe",
                    "annotation_set_name": "Survey H",
                    "image_set_name": "image_set_9",
                    "image_set_uuid": "879d617d-fb0d-4b73-9d77-b64f246e32bb",
                    "image_filename": "image_009.jpg",
                    "image_handle": "image_009_url.jpg",
                    "image_uuid": "1e71b4ef-f0c3-4708-b3db-9b83d8ca8fd5",
                    "label_name": "bryozoa_01",
                    "label_aphia_id": 745,
                    "annotation_platform": "BIIGLE",
                    "annotation_creation_datetime": "2020-02-29T20:55:14Z",
                    "annotation_shape": "polygon",
                    "annotation_coordinates": [[400.0, 400.0], [450.0, 480.0], [500.0, 420.0]],
                    "annotation_dimension_pixels": 183.9,
                    "annotator_name": "Michael Lee",
                },
                {
                    "creation_datetime": "2021-09-17T11:03:27Z",
                    "uuid": "5e97df42-dfa2-4d64-86e7-67cceeb145fd",
                    "annotation_set_uuid": "d2b84b7e-c54b-4692-a8dd-3a907615a0c1",
                    "annotation_set_name": "Survey I",
                    "image_set_name": "image_set_10",
                    "image_set_uuid": "cf48d0cb-c46f-4724-9c8d-4f7589b84e2b",
                    "image_filename": "image_010.jpg",
                    "image_handle": "image_010_url.jpg",
                    "image_uuid": "b15b49b4-90a7-432f-94dc-a4e7e6f5e24b",
                    "label_name": "chordata_01",
                    "label_aphia_id": 999,
                    "annotation_platform": "ImagePro",
                    "annotation_creation_datetime": "2021-09-17T11:03:27Z",
                    "annotation_shape": "bounding-box",
                    "annotation_coordinates": [[700.0, 600.0], [850.0, 760.0]],
                    "annotation_dimension_pixels": 255.6,
                    "annotator_name": "Olivia Turner",
                },
            ]
        },
    }
