"""Cross-vendor failover — EquivalenceMap + Router.failover()."""

import pytest

import loom
from loom import EquivalenceMap, Loom, Router
from loom._equivalents import DEFAULT_TIERS, default_map
from loom.errors import ProviderError, RateLimitError


# ---------- EquivalenceMap ----------


def test_default_map_has_expected_tiers():
    m = default_map()
    tiers = m.tiers()
    assert "text/cheap" in tiers
    assert "text/standard" in tiers
    assert "text/frontier" in tiers


def test_equivalents_of_excludes_self():
    m = default_map()
    eqs = m.equivalents_of("openai", "text", "gpt-4o-mini")
    assert ("openai", "text", "gpt-4o-mini") not in eqs
    assert ("anthropic", "text", "claude-haiku-4-5") in eqs
    assert ("gemini", "text", "gemini-2.5-flash") in eqs


def test_equivalents_of_unknown_model_returns_empty():
    m = default_map()
    assert m.equivalents_of("openai", "text", "no-such-model") == []
    assert m.equivalents_of("ghost", "text", "x") == []


def test_tier_of_returns_tier_name_or_none():
    m = default_map()
    assert m.tier_of("openai", "text", "gpt-4o-mini") == "text/cheap"
    assert m.tier_of("openai", "text", "nonsense") is None


def test_custom_equivalence_map():
    m = EquivalenceMap(
        {
            "custom/tier": [
                ("openai", "text", "gpt-4o-mini"),
                ("deepseek", "text", "deepseek-v3"),
            ]
        }
    )
    assert m.tier_of("openai", "text", "gpt-4o-mini") == "custom/tier"
    eqs = m.equivalents_of("openai", "text", "gpt-4o-mini")
    assert eqs == [("deepseek", "text", "deepseek-v3")]


def test_default_tiers_constant_is_not_mutated_by_map():
    """Constructing an EquivalenceMap shouldn't leak mutations back into
    DEFAULT_TIERS — the map should hold its own copy."""
    before = {k: list(v) for k, v in DEFAULT_TIERS.items()}
    m = EquivalenceMap()
    # Pull internal storage by exercising the API; isolation matters for
    # tests that run in any order.
    m.equivalents_of("openai", "text", "gpt-4o-mini")
    assert {k: list(v) for k, v in DEFAULT_TIERS.items()} == before


# ---------- Router.failover ----------


def test_failover_router_starts_with_given_model():
    r = Router.failover(provider="openai", modality="text", model="gpt-4o-mini")
    assert r.candidates[0].provider == "openai"
    assert r.candidates[0].model == "gpt-4o-mini"
    # And then the equivalents follow.
    fallbacks = [(c.provider, c.modality, c.model) for c in r.candidates[1:]]
    assert ("anthropic", "text", "claude-haiku-4-5") in fallbacks


def test_failover_router_with_no_known_model_has_only_starting_candidate():
    r = Router.failover(
        provider="openai", modality="text", model="custom-fine-tune"
    )
    assert len(r.candidates) == 1
    assert r.candidates[0].model == "custom-fine-tune"


def test_failover_router_accepts_custom_equivalence_map():
    m = EquivalenceMap(
        {
            "tier": [
                ("openai", "text", "gpt-4o-mini"),
                ("xai", "text", "grok-4-fast"),
            ]
        }
    )
    r = Router.failover(
        provider="openai", modality="text", model="gpt-4o-mini",
        equivalence=m,
    )
    keys = [(c.provider, c.model) for c in r.candidates]
    assert keys == [("openai", "gpt-4o-mini"), ("xai", "grok-4-fast")]


def test_failover_router_accepts_extra_candidates():
    r = Router.failover(
        provider="openai", modality="text", model="gpt-4o-mini",
        extra_candidates=[("openai", "text", "gpt-4o")],
    )
    assert r.candidates[-1].model == "gpt-4o"


# ---------- end-to-end ----------


def test_failover_skips_first_vendor_on_error(monkeypatch):
    calls: list[str] = []

    def fake(provider, modality, model, params, prompt):
        calls.append(f"{provider}:{model}")
        if provider == "openai":
            raise RateLimitError("over quota")
        return {"kind": "text", "text": f"answered by {provider}"}

    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(
        api_keys={
            "OPENAI_API_KEY": "k",
            "ANTHROPIC_API_KEY": "k",
            "GEMINI_API_KEY": "k",
            "DEEPSEEK_API_KEY": "k",
        },
        retry=None,
    )
    router = Router.failover(
        provider="openai", modality="text", model="gpt-4o-mini",
    )
    result = client.route(router, prompt="hi")

    # First call hit openai (failed), then fell through to anthropic.
    assert calls[0].startswith("openai:")
    assert "answered by" in result["text"]
    assert result["_router"]["passed"] is True
    assert result["_router"]["used"].split(":")[0] != "openai"


def test_failover_reraises_when_all_vendors_fail(monkeypatch):
    def fake(provider, modality, model, params, prompt):
        raise ProviderError(f"{provider} is down")

    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(
        api_keys={
            "OPENAI_API_KEY": "k",
            "ANTHROPIC_API_KEY": "k",
            "GEMINI_API_KEY": "k",
            "DEEPSEEK_API_KEY": "k",
        },
        retry=None,
    )
    router = Router.failover(
        provider="openai", modality="text", model="gpt-4o-mini",
    )
    with pytest.raises(ProviderError):
        client.route(router, prompt="hi")
