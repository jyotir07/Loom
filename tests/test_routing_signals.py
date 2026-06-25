"""RoutingSignals resolver tests (issue #41) — fully offline.

The resolver merges static catalog metadata with live runtime signals.
Live signals are mocked here; the real source lands in a later phase.
"""

import pytest

from loom.catalog import Catalog
from loom.errors import ModelNotFoundError
from loom.routing import LiveSignalSource, NullLiveSignals, RoutingSignals


class DictSource:
    """Mock live source keyed by (provider, modality, model)."""

    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, provider, modality, model):
        return self._mapping.get((provider, modality, model))


# --- static-only behavior --------------------------------------------------


def test_default_source_is_static_only():
    # No live source -> resolved signals equal the catalog metadata.
    c = Catalog()
    signals = RoutingSignals(c)
    resolved = signals.for_model("openai", "text", "gpt-4o-mini")
    assert resolved == c.metadata("openai", "text", "gpt-4o-mini")
    assert resolved["quality_tier"] == "cheap"
    assert "latency_ms" not in resolved


def test_default_source_is_null_live_signals():
    signals = RoutingSignals(Catalog())
    assert isinstance(signals.live, NullLiveSignals)


def test_null_live_source_returns_none():
    assert NullLiveSignals().get("openai", "text", "gpt-4o-mini") is None


# --- merge / override behavior ---------------------------------------------


def test_live_values_augment_static():
    c = Catalog()
    source = DictSource(
        {("gemini", "text", "gemini-3.1-pro"): {"latency_ms": 820, "failure_rate": 0.01}}
    )
    resolved = RoutingSignals(c, source).for_model("gemini", "text", "gemini-3.1-pro")
    # static fields preserved...
    assert resolved["context_window"] == 1_000_000
    assert resolved["quality_tier"] == "frontier"
    assert "text" in resolved["capabilities"]
    # ...and live metrics added.
    assert resolved["latency_ms"] == 820
    assert resolved["failure_rate"] == 0.01


def test_live_overrides_static_field():
    c = Catalog()
    source = DictSource(
        {("openai", "text", "gpt-4o-mini"): {"quality_tier": "standard"}}
    )
    resolved = RoutingSignals(c, source).for_model("openai", "text", "gpt-4o-mini")
    assert resolved["quality_tier"] == "standard"  # live wins
    assert resolved["latency_class"] == "fast"  # untouched static field remains


def test_none_live_values_fall_back_to_catalog():
    c = Catalog()
    # latency_ms is None (no opinion) but failure_rate is real.
    source = DictSource(
        {("openai", "text", "gpt-4o-mini"): {"latency_ms": None, "failure_rate": 0.02}}
    )
    resolved = RoutingSignals(c, source).for_model("openai", "text", "gpt-4o-mini")
    assert "latency_ms" not in resolved
    assert resolved["failure_rate"] == 0.02
    assert resolved["quality_tier"] == "cheap"  # catalog fallback intact


def test_live_source_with_no_entry_falls_back():
    c = Catalog()
    source = DictSource({})  # knows nothing about this model
    resolved = RoutingSignals(c, source).for_model("openai", "text", "gpt-4o-mini")
    assert resolved == c.metadata("openai", "text", "gpt-4o-mini")


# --- edge cases ------------------------------------------------------------


def test_model_without_static_metadata_uses_live_only():
    custom = {
        "fake": {"label": "Fake", "modalities": {"text": [{"id": "x", "name": "X"}]}}
    }
    c = Catalog(data=custom)
    source = DictSource({("fake", "text", "x"): {"latency_ms": 50}})
    resolved = RoutingSignals(c, source).for_model("fake", "text", "x")
    assert resolved == {"latency_ms": 50}


def test_unknown_model_raises():
    signals = RoutingSignals(Catalog())
    with pytest.raises(ModelNotFoundError):
        signals.for_model("openai", "text", "ghost-model")


def test_resolved_dict_is_independent():
    c = Catalog()
    signals = RoutingSignals(c)
    resolved = signals.for_model("openai", "text", "gpt-4o-mini")
    resolved["capabilities"].append("mutated")
    resolved["quality_tier"] = "frontier"
    fresh = signals.for_model("openai", "text", "gpt-4o-mini")
    assert "mutated" not in fresh["capabilities"]
    assert fresh["quality_tier"] == "cheap"


# --- interface contracts ---------------------------------------------------


def test_null_live_signals_satisfies_protocol():
    assert isinstance(NullLiveSignals(), LiveSignalSource)
    assert isinstance(DictSource({}), LiveSignalSource)


def test_static_signal_keys_are_catalog_metadata_fields():
    c = Catalog()
    resolved = RoutingSignals(c).for_model("openai", "text", "gpt-4o-mini")
    assert set(resolved).issubset(set(Catalog.METADATA_FIELDS))
