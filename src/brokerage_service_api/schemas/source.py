"""Models for configured upstream data sources."""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class UpstreamTimeout(BaseModel):
    """Timeout settings for an upstream API."""

    model_config = ConfigDict(frozen=True)

    connect: float = Field(default=5.0, gt=0)
    read: float = Field(default=30.0, gt=0)
    write: float = Field(default=30.0, gt=0)
    pool: float = Field(default=5.0, gt=0)

    def to_httpx_timeout(self) -> httpx.Timeout:
        """Convert to an httpx.Timeout object.

        Returns:
            httpx.Timeout: The equivalent httpx.Timeout object.
        """
        return httpx.Timeout(
            connect=self.connect,
            read=self.read,
            write=self.write,
            pool=self.pool,
        )


class SourceConfig(BaseModel):
    """Configuration for one upstream API source."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z0-9_-]+$")
    label: str
    base_url: HttpUrl
    enabled: bool = True
    kind: Literal["annotations_v1"] = "annotations_v1"
    timeout: UpstreamTimeout = Field(default_factory=UpstreamTimeout)

    @field_validator("name")
    @classmethod
    def normalise_name(cls, value: str) -> str:
        """Normalise the name to lowercase and strip whitespace.

        Args:
            value (str): The name to normalise.

        Returns:
            str: The normalised name.
        """
        return value.strip().lower()
