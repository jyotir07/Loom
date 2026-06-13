"""Cost computation + response enrichment."""

import pytest

from loom import Loom
from loom._pricing import compute_cost
from loom.catalog import Catalog


def test_compute_text_cost():
    c = Catalog()
    cost = compute_cost(
        catalog=c,
        provider="openai",
        modality="text",
        model_id="gpt-4o-mini",
        usage={"input_tokens": 1_000_000, "output_tokens": 1_000_000},
    )
    # gpt-4o-mini: input 14.4578 INR/1M, output 57.8312 INR/1M
    assert cost is not None
    assert cost["local_currency"] == "INR"
    assert cost["local"] == pytest.approx(14.4578 + 57.8312, rel=1e-3)
    assert cost["usd"] == pytest.approx(cost["local"] / 83.0, rel=1e-3)


def test_compute_image_cost():
    c = Catalog()
    cost = compute_cost(
        catalog=c,
        provider="openai",
        modality="image",
        model_id="gpt-image-1-low",
        usage=None,
        image_count=2,
    )
    assert cost is not None
    assert cost["local"] == pytest.approx(1.0602383 * 2, rel=1e-3)


def test_compute_cost_unknown_model_returns_none():
    c = Catalog()
    cost = compute_cost(
        catalog=c,
        provider="openai",
        modality="text",
        model_id="ghost-model",
        usage={"input_tokens": 100, "output_tokens": 100},
    )
    assert cost is None


def test_enrichment_adds_provider_model_cost(monkeypatch):
    """Loom.generate stitches provider/model/upstream_model + cost into the response."""

    def fake_generate(provider, modality, model, params, prompt):
        return {
            "kind": "text",
            "text": "hello",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        }

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    result = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
    )
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o-mini"
    assert result["upstream_model"] == "gpt-4o-mini"
    assert result["usage"]["input_tokens"] == 100
    assert "cost" in result
    assert result["cost"]["usd"] > 0
    assert result["cost"]["local"] > 0


def test_custom_local_to_usd():
    """local_to_usd knob controls the conversion."""
    c = Catalog()
    cost = compute_cost(
        catalog=c,
        provider="openai",
        modality="text",
        model_id="gpt-4o-mini",
        usage={"input_tokens": 1_000_000, "output_tokens": 0},
        local_to_usd=0.5,
        local_currency="XYZ",
    )
    assert cost is not None
    assert cost["local_currency"] == "XYZ"
    assert cost["usd"] == pytest.approx(cost["local"] * 0.5, rel=1e-6)
