"""Cross-vendor failover — EquivalenceMap + Router.failover() + FallbackPolicy."""

import asyncio

import pytest

import loom
from loom import AsyncLoom, EquivalenceMap, FallbackPolicy, Loom, RetryPolicy, Router
from loom._equivalents import DEFAULT_TIERS, default_map
from loom.errors import AuthError, ProviderError, RateLimitError
from loom.routing import StrategySelector


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


# ====================================================================
# Configurable provider fallback (issue #50)
# ====================================================================


_ALL_KEYS = {
    "OPENAI_API_KEY": "k",
    "ANTHROPIC_API_KEY": "k",
    "GEMINI_API_KEY": "k",
    "DEEPSEEK_API_KEY": "k",
}


def _by_provider_fake(behavior: dict):
    """Fake dispatch keyed by provider: value is an exception to raise, or
    None to succeed."""
    calls: list[str] = []

    def fake(provider, modality, model, params, prompt):
        calls.append(f"{provider}:{model}")
        exc = behavior.get(provider)
        if exc is not None:
            raise exc
        return {"kind": "text", "text": f"answered by {provider}"}

    return calls, fake


def test_fallback_policy_rejects_non_positive_retries():
    with pytest.raises(ValueError):
        FallbackPolicy(retries=0, providers=["openai"])


def test_fallback_switches_provider_on_retryable(monkeypatch):
    calls, fake = _by_provider_fake({"gemini": RateLimitError("429")})
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys=_ALL_KEYS, retry=None)
    result = client.generate(
        prompt="hi",
        fallback=FallbackPolicy(providers=["gemini", "openai"]),
    )
    assert result["text"] == "answered by openai"
    assert result["_router"]["used"].startswith("openai:")
    # Metadata reflects the failover chain, gemini first.
    assert calls[0].startswith("gemini:")
    assert result["_router"]["tried"][0].startswith("gemini:")
    assert result["_router"]["tried"][1].startswith("openai:")


def test_fallback_raises_immediately_on_non_retryable(monkeypatch):
    calls, fake = _by_provider_fake({"gemini": AuthError("bad key")})
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys=_ALL_KEYS, retry=None)
    with pytest.raises(AuthError):
        client.generate(
            prompt="hi",
            fallback=FallbackPolicy(providers=["gemini", "openai"]),
        )
    # openai was never tried — a non-retryable error stops the chain.
    assert len(calls) == 1
    assert calls[0].startswith("gemini:")


def test_fallback_reraises_when_all_retryable_fail(monkeypatch):
    calls, fake = _by_provider_fake(
        {"gemini": RateLimitError("429"), "openai": RateLimitError("429")}
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys=_ALL_KEYS, retry=None)
    with pytest.raises(RateLimitError):
        client.generate(
            prompt="hi",
            fallback=FallbackPolicy(providers=["gemini", "openai"]),
        )
    assert len(calls) == 2


def test_fallback_respects_retries_cap(monkeypatch):
    calls, fake = _by_provider_fake(
        {"gemini": RateLimitError("429"), "openai": RateLimitError("429")}
        # anthropic would succeed, but it is beyond the retries cap.
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys=_ALL_KEYS, retry=None)
    with pytest.raises(RateLimitError):
        client.generate(
            prompt="hi",
            fallback=FallbackPolicy(
                providers=["gemini", "openai", "anthropic"], retries=2
            ),
        )
    assert [c.split(":")[0] for c in calls] == ["gemini", "openai"]


def test_fallback_uses_router_strategy_for_model(monkeypatch):
    calls, fake = _by_provider_fake({})
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys=_ALL_KEYS, retry=None)
    result = client.generate(
        prompt="hi",
        router="cheapest",
        fallback=FallbackPolicy(providers=["openai"]),
    )
    best = StrategySelector(client.catalog).best("cheapest", providers=["openai"])
    upstream, _ = client.catalog.resolve("openai", "text", best.model)
    assert calls == [f"openai:{upstream}"]
    assert result["text"] == "answered by openai"


def test_fallback_rejects_explicit_provider():
    client = Loom(api_keys=_ALL_KEYS)
    with pytest.raises(ValueError):
        client.generate(
            provider="openai", model="gpt-4o", prompt="hi",
            fallback=FallbackPolicy(providers=["gemini"]),
        )


def test_fallback_preserves_per_provider_retry(monkeypatch):
    calls, fake = _by_provider_fake({"gemini": RateLimitError("429")})
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(
        api_keys=_ALL_KEYS,
        retry=RetryPolicy(max_attempts=2, base_delay=0.0, jitter=0.0),
    )
    result = client.generate(
        prompt="hi",
        fallback=FallbackPolicy(providers=["gemini", "openai"]),
    )
    # gemini is retried (max_attempts=2) before failover kicks in.
    assert [c.split(":")[0] for c in calls] == ["gemini", "gemini", "openai"]
    assert result["text"] == "answered by openai"


def test_async_fallback_switches_provider(monkeypatch):
    async def fake_agenerate(provider, modality, model, params, prompt):
        if provider == "gemini":
            raise RateLimitError("429")
        return {"kind": "text", "text": f"answered by {provider}"}

    monkeypatch.setattr("loom._loom._providers.agenerate", fake_agenerate)
    client = AsyncLoom(api_keys=_ALL_KEYS, retry=None)
    result = asyncio.run(
        client.generate(
            prompt="hi",
            fallback=FallbackPolicy(providers=["gemini", "openai"]),
        )
    )
    assert result["text"] == "answered by openai"
    assert result["_router"]["used"].startswith("openai:")
