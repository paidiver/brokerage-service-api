"""Public collection and error contracts."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CollectionResponse(BaseModel, Generic[T]):
    """A page or complete collection with a stable array payload."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[T]


class FieldError(BaseModel):
    """A validation message associated with a request field."""

    field: str
    message: str


class ProblemDetails(BaseModel):
    """RFC 9457 error with a stable code and optional field errors."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    errors: list[FieldError] | None = None
