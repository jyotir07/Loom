"""Catalog unit tests — fully offline."""

import pytest

from loom.catalog import Catalog, resolve
from loom.errors import ModelNotFoundError


def test_default_catalog_loads():
    c = Catalog()
    providers = c.providers()
    assert "openai" in providers
    assert "anthropic" in providers
    assert len(providers) >= 10


def test_resolve_text_passthrough():
    c = Catalog()
    upstream, params = c.resolve("openai", "text", "gpt-4o-mini")
    assert upstream == "gpt-4o-mini"
    assert params == {}


def test_resolve_image_with_params():
    # "gpt-image-1-high" is sugar for ("gpt-image-1", {"quality": "high"})
    c = Catalog()
    upstream, params = c.resolve("openai", "image", "gpt-image-1-high")
    assert upstream == "gpt-image-1"
    assert params == {"quality": "high"}


def test_resolve_uses_explicit_upstream_model():
    # Anthropic catalog entry has a versioned upstream model id.
    c = Catalog()
    upstream, _ = c.resolve("anthropic", "text", "claude-haiku-4-5")
    assert upstream == "claude-haiku-4-5-20251001"


def test_resolve_unknown_provider():
    c = Catalog()
    with pytest.raises(ModelNotFoundError):
        c.resolve("nope", "text", "x")


def test_resolve_unknown_modality():
    c = Catalog()
    with pytest.raises(ModelNotFoundError):
        c.resolve("openai", "video", "gpt-4o-mini")


def test_resolve_unknown_model():
    c = Catalog()
    with pytest.raises(ModelNotFoundError):
        c.resolve("openai", "text", "ghost-model")


def test_module_resolve_matches_default_catalog():
    assert resolve("openai", "text", "gpt-4o-mini") == ("gpt-4o-mini", {})


def test_models_listing():
    c = Catalog()
    items = c.models("openai", "text")
    assert isinstance(items, list)
    assert any(m["id"] == "gpt-4o-mini" for m in items)


def test_custom_data():
    custom = {
        "fake": {
            "label": "Fake",
            "modalities": {"text": [{"id": "x", "name": "X"}]},
        }
    }
    c = Catalog(data=custom)
    assert c.providers() == ["fake"]
    assert c.resolve("fake", "text", "x") == ("x", {})
