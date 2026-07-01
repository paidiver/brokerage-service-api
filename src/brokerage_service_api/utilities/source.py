"""Registry for configured upstream data sources."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import httpx
import yaml
from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from brokerage_service_api.fixtures.constants import ENV_SOURCE_URL_MAP
from brokerage_service_api.schemas.source import SourceConfig
from brokerage_service_api.upstream.annotations import AnnotationApiClient

DEFAULT_SOURCES_FILE = Path(__file__).resolve().parent.parent / "fixtures" / "source.yaml"


class SourcesFile(BaseModel):
    """Top-level structure of the sources YAML file."""

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
    """Load source configuration from a YAML file.

    Args:
        path: Path to the YAML source configuration file .

    Returns:
        SourceRegistry: Registry of validated and configured sources.
    """
    yaml_content = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources_data = []

    for source_name, source_config in yaml_content.get("sources", {}).items():
        source_config["name"] = source_name

        if source_name in ENV_SOURCE_URL_MAP:
            env_var, default_url = ENV_SOURCE_URL_MAP[source_name]
            base_url = os.environ.get(env_var, default_url)
            source_config["base_url"] = base_url

        sources_data.append(source_config)

    validated_sources = [SourceConfig.model_validate(source) for source in sources_data]
    return SourceRegistry(validated_sources)


@lru_cache
def get_source_registry() -> SourceRegistry:
    """Return the cached source registry.

    Returns:
        SourceRegistry: The validated and cached registry of sources.
    """
    return load_sources()


async def check_source_health(source: SourceConfig) -> dict:
    """Check the health status of a source API.

    Args:
        source (SourceConfig): The source configuration object.

    Returns:
        dict: A dictionary with the health status of the source.
    """
    try:
        response = await AnnotationApiClient(source).health_check()
        response.raise_for_status()

        status = response.data.get("status", "unknown")

        return {"source_name": source.name, "source_label": source.label, "base_url": source.base_url, "status": status}
    except httpx.HTTPStatusError:
        return {
            "source_name": source.name,
            "source_label": source.label,
            "base_url": source.base_url,
            "status": "unhealthy",
        }


def calculate_available_sources(request: Request, sources: list[str] | None) -> list[SourceConfig]:
    """Calculate the available sources based on the request and provided source names.

    Args:
        request: The incoming request object.
        sources: Optional list of source names to filter the search.

    Returns:
        List of SourceConfig: The list of available sources based on the request and provided source names.
    """
    configured_sources = request.app.state.sources
    if sources:
        return [source for source in configured_sources if source.name in sources]
    return configured_sources
