"""Models for the brokerage search endpoint."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Result(BaseModel):
    """A representation of an individual result."""

    source: Literal["BODC", "JNCC"]
    uuid: str
    image_filename: str
    image_handle: str
    image_uuid: UUID
    label_name: str
    label_aphia_id: int
    annotation_platform: str
    annotation_creation_datetime: datetime
    annotation_shape: str
    annotation_coordinates: list[list[int | float]]
    annotation_dimension_pixels: float | int
    annotator_name: str
    annotation_set_uuid: UUID
    annotation_set_name: str
    image_set_uuid: UUID
    image_set_name: str

    @classmethod
    def construct_instance_from_raw_response(cls, raw_response: dict, source: str) -> "Result":
        """Parse the raw response from the API and return a Result instance.

        Args:
            raw_response: The raw dict from the API.
            source: Either JNCC or BODC.

        Returns:
            An instance of the Result class.
        """
        return cls(
            source=source,
            uuid=raw_response.get("uuid"),
            image_filename=raw_response.get("image_filename"),
            image_handle=raw_response.get("image_handle"),
            image_uuid=raw_response.get("image_uuid"),
            label_name=raw_response.get("label_name"),
            label_aphia_id=raw_response.get("label_aphia_id"),
            annotation_platform=raw_response.get("annotation_platform"),
            annotation_creation_datetime=raw_response.get("annotation_creation_datetime"),
            annotation_shape=raw_response.get("annotation_shape"),
            annotation_coordinates=raw_response.get("annotation_coordinates"),
            annotation_dimension_pixels=raw_response.get("annotation_dimension_pixels"),
            annotator_name=raw_response.get("annotator_name"),
            annotation_set_uuid=raw_response.get("annotation_set_uuid"),
            annotation_set_name=raw_response.get("annotation_set_name"),
            image_set_uuid=raw_response.get("image_set_uuid"),
            image_set_name=raw_response.get("image_set_name"),
        )


class Summary(BaseModel):
    """A representation of the merged summaries retrieved from the upstream API's."""

    n_annotations: int
    n_images: int
    n_annotation_sets: int
    n_image_sets: int

    def __add__(self, other: "Summary") -> "Summary":
        """Override the + operator to allow for merging of Summary instances."""
        return Summary(
            n_annotations=self.n_annotations + other.n_annotations,
            n_images=self.n_images + other.n_images,
            n_annotation_sets=self.n_annotation_sets + other.n_annotation_sets,
            n_image_sets=self.n_image_sets + other.n_image_sets,
        )


class Results(BaseModel):
    """A representation of the aggregated summary and annotations."""

    summary: Summary | None = None
    annotations: list[Result]


class SearchResults(BaseModel):
    """A representation of an aggregation of individual results."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: Results
