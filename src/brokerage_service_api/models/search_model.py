"""Models for the brokerage search endpoint."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field



class Result(BaseModel):
    """A representation of an individual result."""
    source: Literal["BODC", "JNCC"]
    uuid: str
    image_filename: str
    image_handle:  str
    image_uuid: UUID
    label_name: str
    label_aphia_id: int
    annotation_platform: str
    annotation_creation_datetime: datetime
    annotation_shape: str
    annotation_coordinates: list[str]
    annotation_dimension_pixels: int
    annotation_dimension_pixels: int
    annotator_name: str
    annotation_set_uuid: UUID
    annotation_set_name: str
    image_set_uuid: UUID
    image_set_name:str


class SearchResults(BaseModel):
    """A representation of an aggregation of individual results."""
    results: list[Result]



