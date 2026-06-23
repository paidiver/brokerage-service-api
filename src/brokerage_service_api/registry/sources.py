"""Registry for configured upstream data sources."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from brokerage_service_api.models.sources import SourceConfig

DEFAULT_SOURCES_FILE = Path(__file__).parents[1] / "fixtures" / "sources.json"


class SourcesFile(BaseModel):
    """Top-level structure of the sources JSON file."""

    model_config = ConfigDict(frozen=True)

    sources: list[SourceConfig] = Field(default_factory=list)


class SourceRegistry:
    """Registry of configured upstream sources."""

    def __init__(self, sources: list[SourceConfig]) -> None:
        self._sources = {source.name: source for source in sources if source.enabled}

    def get(self, name: str) -> SourceConfig:
        """Return the enabled source with the given name."""
        source_name = name.strip().lower()

        try:
            return self._sources[source_name]
        except KeyError as exc:
            allowed = ", ".join(sorted(self._sources))
            raise UnknownSourceError(f"Unknown source '{name}'. Allowed sources: {allowed}") from exc

    def list(self) -> list[SourceConfig]:
        """Return all enabled sources."""
        return list(self._sources.values())

    def names(self) -> list[str]:
        """Return enabled source names in stable order."""
        return sorted(self._sources)


class UnknownSourceError(ValueError):
    """Raised when a requested source is not configured."""


def load_sources(path: Path = DEFAULT_SOURCES_FILE) -> SourceRegistry:
    """Load source configuration from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    bodc_url = os.environ.get("BODC_ANNOTATIONS_API_URL")
    jncc_url = os.environ.get("JNCC_ANNOTATIONS_API_URL")
    for source in data.get("sources", []):
        if source.get("name") == "bodc" and bodc_url:
            source["base_url"] = bodc_url
        elif source.get("name") == "jncc" and jncc_url:
            source["base_url"] = jncc_url
    sources_file = SourcesFile.model_validate(data)
    return SourceRegistry(sources_file.sources)


@lru_cache
def get_source_registry() -> SourceRegistry:
    """Return the cached source registry."""
    return load_sources()
