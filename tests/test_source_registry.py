"""Tests for the upstream annotations API client."""

from __future__ import annotations

import pytest
from brokerage_service_api.utilities.source import get_source_registry


def test_get_source() -> None:
    """Test getting a source from the registry."""
    sources = get_source_registry()

    jncc = sources.get("jncc")
    assert jncc.name == "jncc"

    bodc = sources.get("bodc")
    assert bodc.name == "bodc"

    with pytest.raises(ValueError):
        sources.get("invalid_source")

    names = sources.names()
    assert "jncc" in names
    assert "bodc" in names

    source_list = sources.list()
    assert any(source.name == "jncc" for source in source_list)
