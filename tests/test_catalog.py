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


# --- routing metadata (issue #40) ------------------------------------------


def test_metadata_returns_seeded_fields():
    c = Catalog()
    meta = c.metadata("openai", "text", "gpt-4o-mini")
    assert meta["quality_tier"] == "cheap"
    assert meta["latency_class"] == "fast"
    assert meta["context_window"] == 128000
    assert "structured_output" in meta["capabilities"]


def test_metadata_covers_all_quality_tiers():
    c = Catalog()
    tiers = {
        c.metadata("openai", "text", "gpt-5-nano")["quality_tier"],
        c.metadata("openai", "text", "gpt-4o-mini")["quality_tier"],
        c.metadata("openai", "text", "gpt-4o")["quality_tier"],
        c.metadata("openai", "text", "gpt-5")["quality_tier"],
    }
    assert tiers == {"nano", "cheap", "standard", "frontier"}


def test_metadata_empty_for_model_without_metadata():
    # kimi's entry carries no routing metadata -> empty dict, not an error.
    c = Catalog()
    assert c.metadata("kimi", "text", "kimi-k2-0905-preview") == {}


def test_metadata_empty_for_custom_catalog():
    custom = {
        "fake": {"label": "Fake", "modalities": {"text": [{"id": "x", "name": "X"}]}}
    }
    c = Catalog(data=custom)
    assert c.metadata("fake", "text", "x") == {}


def test_metadata_unknown_model_raises():
    c = Catalog()
    with pytest.raises(ModelNotFoundError):
        c.metadata("openai", "text", "ghost-model")


def test_metadata_unknown_provider_raises():
    c = Catalog()
    with pytest.raises(ModelNotFoundError):
        c.metadata("nope", "text", "x")


def test_metadata_returns_a_copy():
    # Mutating the returned metadata (incl. the capabilities list) must not
    # leak back into the catalog.
    c = Catalog()
    meta = c.metadata("openai", "text", "gpt-4o-mini")
    meta["capabilities"].append("mutated")
    meta["quality_tier"] = "frontier"
    fresh = c.metadata("openai", "text", "gpt-4o-mini")
    assert "mutated" not in fresh["capabilities"]
    assert fresh["quality_tier"] == "cheap"


def test_resolve_unaffected_by_metadata():
    # Adding metadata to an entry must not change resolve()'s contract:
    # metadata keys never leak into the merged params.
    c = Catalog()
    upstream, params = c.resolve("openai", "text", "gpt-4o-mini")
    assert upstream == "gpt-4o-mini"
    assert params == {}
