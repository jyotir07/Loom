"""Smart model routing — Router + Loom.route() + AsyncLoom.route()."""

import asyncio

import pytest

import loom
from loom import AsyncLoom, Candidate, Loom, Router
from loom.errors import AuthError, ProviderError, RateLimitError


# ---------- Router construction ----------


def test_router_requires_candidates():
    with pytest.raises(ValueError):
        Router(candidates=[])


def test_router_accepts_tuple_shorthand():
    r = Router(candidates=[("openai", "text", "gpt-4o-mini")])
    assert len(r.candidates) == 1
    assert r.candidates[0].provider == "openai"
    assert r.candidates[0].modality == "text"
    assert r.candidates[0].model == "gpt-4o-mini"
    assert r.candidates[0].params is None


def test_router_accepts_four_tuple_with_params():
    r = Router(candidates=[("openai", "text", "gpt-4o", {"temperature": 0.7})])
    assert r.candidates[0].params == {"temperature": 0.7}


def test_router_accepts_candidate_objects():
    c = Candidate(provider="openai", modality="text", model="gpt-4o-mini")
    r = Router(candidates=[c])
    assert r.candidates[0] is c


def test_router_rejects_invalid_candidate():
    with pytest.raises(TypeError):
        Router(candidates=["openai/text/gpt-4o-mini"])


# ---------- sync routing ----------


def _fake_provider_factory(responses_by_model: dict, raise_for: dict | None = None):
    """Build a (calls, fake_generate) pair.

    `responses_by_model` maps upstream model -> response dict.
    `raise_for` maps upstream model -> exception instance to raise instead.
    """
    calls: list[dict] = []
    raise_for = raise_for or {}

    def fake_generate(provider, modality, model, params, prompt):
        calls.append({"provider": provider, "model": model, "params": dict(params)})
        if model in raise_for:
            raise raise_for[model]
        return responses_by_model[model]

    return calls, fake_generate


def test_route_first_candidate_passes_validator(monkeypatch):
    calls, fake = _fake_provider_factory(
        {
            "gpt-4o-mini": {"kind": "text", "text": "a sufficiently long answer here"},
            "gpt-4o": {"kind": "text", "text": "should not be reached"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 10,
    )
    result = client.route(router, prompt="hi")
    assert result["text"].startswith("a sufficiently")
    assert result["_router"]["used"] == "openai:text:gpt-4o-mini"
    assert result["_router"]["passed"] is True
    assert result["_router"]["tried"] == ["openai:text:gpt-4o-mini"]
    assert len(calls) == 1


def test_route_escalates_on_validator_failure(monkeypatch):
    calls, fake = _fake_provider_factory(
        {
            "gpt-4o-mini": {"kind": "text", "text": "short"},
            "gpt-4o": {"kind": "text", "text": "much more elaborate answer"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 10,
    )
    result = client.route(router, prompt="hi")
    assert result["text"] == "much more elaborate answer"
    assert result["_router"]["used"] == "openai:text:gpt-4o"
    assert result["_router"]["passed"] is True
    assert result["_router"]["tried"] == [
        "openai:text:gpt-4o-mini",
        "openai:text:gpt-4o",
    ]
    assert len(calls) == 2


def test_route_returns_last_result_when_all_fail_validator(monkeypatch):
    _, fake = _fake_provider_factory(
        {
            "gpt-4o-mini": {"kind": "text", "text": "no"},
            "gpt-4o": {"kind": "text", "text": "nope"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 50,
    )
    result = client.route(router, prompt="hi")
    assert result["text"] == "nope"
    assert result["_router"]["used"] == "openai:text:gpt-4o"
    assert result["_router"]["passed"] is False


def test_route_skips_candidate_on_loom_error(monkeypatch):
    _, fake = _fake_provider_factory(
        {
            "gpt-4o": {"kind": "text", "text": "fallback worked"},
        },
        raise_for={"gpt-4o-mini": RateLimitError("hit cap")},
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
    )
    result = client.route(router, prompt="hi")
    assert result["text"] == "fallback worked"
    assert result["_router"]["used"] == "openai:text:gpt-4o"


def test_route_reraises_last_error_when_all_candidates_fail(monkeypatch):
    _, fake = _fake_provider_factory(
        {},
        raise_for={
            "gpt-4o-mini": AuthError("missing key A"),
            "gpt-4o": ProviderError("upstream went home"),
        },
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
    )
    with pytest.raises(ProviderError) as ei:
        client.route(router, prompt="hi")
    assert "upstream went home" in str(ei.value)


def test_route_merges_per_candidate_params(monkeypatch):
    calls, fake = _fake_provider_factory(
        {
            "gpt-4o": {"kind": "text", "text": "ok"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            Candidate(
                provider="openai",
                modality="text",
                model="gpt-4o",
                params={"temperature": 0.9},
            ),
        ],
    )
    client.route(router, prompt="hi", params={"temperature": 0.1, "top_p": 0.5})
    # candidate params win on conflict
    assert calls[0]["params"]["temperature"] == 0.9
    # caller params still flow through
    assert calls[0]["params"]["top_p"] == 0.5


# ---------- async routing ----------


def test_async_route_escalates(monkeypatch):
    async def fake_agenerate(provider, modality, model, params, prompt):
        if model == "gpt-4o-mini":
            return {"kind": "text", "text": "tiny"}
        return {"kind": "text", "text": "this one is properly long"}

    monkeypatch.setattr("loom._loom._providers.agenerate", fake_agenerate)
    client = AsyncLoom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 10,
    )
    result = asyncio.run(client.route(router, prompt="hi"))
    assert result["text"].startswith("this one")
    assert result["_router"]["used"] == "openai:text:gpt-4o"
    assert result["_router"]["passed"] is True


# ====================================================================
# Routing strategies + StrategySelector (issue #44)
# ====================================================================

from loom import Catalog
from loom.routing import RoutingSignals, RoutingStrategy, StrategySelector


# A small controlled catalog so strategy ordering is unambiguous.
#   a-nano:     price 1,   latency fast,   quality nano      [text]
#   a-frontier: price 100, latency slow,   quality frontier  [text, vision]
#   b-standard: price 10,  latency medium, quality standard  [text, structured_output]
#   b-free:     free (0),  latency fast,   quality cheap     [text]
_SELECTOR_DATA = {
    "alpha": {
        "label": "Alpha",
        "modalities": {
            "text": [
                {"id": "a-nano", "name": "A nano",
                 "input_inr_per_1m": 1.0, "output_inr_per_1m": 1.0,
                 "quality_tier": "nano", "latency_class": "fast",
                 "capabilities": ["text"]},
                {"id": "a-frontier", "name": "A frontier",
                 "input_inr_per_1m": 100.0, "output_inr_per_1m": 100.0,
                 "quality_tier": "frontier", "latency_class": "slow",
                 "capabilities": ["text", "vision"]},
            ],
        },
    },
    "beta": {
        "label": "Beta",
        "modalities": {
            "text": [
                {"id": "b-standard", "name": "B standard",
                 "input_inr_per_1m": 10.0, "output_inr_per_1m": 10.0,
                 "quality_tier": "standard", "latency_class": "medium",
                 "capabilities": ["text", "structured_output"]},
                {"id": "b-free", "name": "B free", "free": True,
                 "quality_tier": "cheap", "latency_class": "fast",
                 "capabilities": ["text"]},
            ],
        },
    },
}


class _DictSource:
    """Mock live-signal source keyed by (provider, modality, model)."""

    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, provider, modality, model):
        return self._mapping.get((provider, modality, model))


def _selector(live=None):
    catalog = Catalog(data=_SELECTOR_DATA)
    signals = RoutingSignals(catalog, live) if live is not None else None
    return StrategySelector(catalog, signals)


def _labels(candidates):
    return [c.label() for c in candidates]


# ---------- enum ----------


def test_strategy_coerce_accepts_string_and_enum():
    assert RoutingStrategy.coerce("cheapest") is RoutingStrategy.CHEAPEST
    assert RoutingStrategy.coerce(RoutingStrategy.FASTEST) is RoutingStrategy.FASTEST


def test_strategy_is_string_valued():
    assert RoutingStrategy.CHEAPEST == "cheapest"


def test_strategy_coerce_rejects_unknown():
    with pytest.raises(ValueError):
        RoutingStrategy.coerce("smartest")


# ---------- per-strategy ordering ----------


def test_select_cheapest_orders_by_price():
    order = _labels(_selector().select("cheapest"))
    assert order == [
        "beta:text:b-free",       # free -> 0
        "alpha:text:a-nano",      # 1
        "beta:text:b-standard",   # 10
        "alpha:text:a-frontier",  # 100
    ]


def test_select_fastest_orders_by_latency_with_label_tiebreak():
    order = _labels(_selector().select("fastest"))
    # a-nano and b-free both "fast" -> tie broken by label (alpha < beta)
    assert order == [
        "alpha:text:a-nano",
        "beta:text:b-free",
        "beta:text:b-standard",
        "alpha:text:a-frontier",
    ]


def test_select_highest_quality_orders_by_tier():
    order = _labels(_selector().select(RoutingStrategy.HIGHEST_QUALITY))
    assert order == [
        "alpha:text:a-frontier",  # frontier
        "beta:text:b-standard",   # standard
        "beta:text:b-free",       # cheap
        "alpha:text:a-nano",      # nano
    ]


def test_select_balanced_blends_signals():
    order = _labels(_selector().select("balanced"))
    # b-standard wins the blend (good quality, low-ish cost, medium latency);
    # a-frontier sinks (top quality can't offset worst cost+latency).
    assert order == [
        "beta:text:b-standard",
        "beta:text:b-free",
        "alpha:text:a-nano",
        "alpha:text:a-frontier",
    ]


# ---------- live signals influence ----------


def test_fastest_uses_live_latency_over_class():
    # Live latency makes the otherwise-"slow" frontier model the fastest.
    live = _DictSource({("alpha", "text", "a-frontier"): {"latency_ms": 5}})
    order = _labels(_selector(live).select("fastest"))
    assert order[0] == "alpha:text:a-frontier"


# ---------- filtering ----------


def test_select_capability_filter():
    order = _labels(_selector().select("cheapest", capabilities=["structured_output"]))
    assert order == ["beta:text:b-standard"]


def test_select_provider_subset():
    order = _labels(_selector().select("cheapest", providers=["alpha"]))
    assert order == ["alpha:text:a-nano", "alpha:text:a-frontier"]


def test_select_unknown_modality_returns_empty():
    assert _selector().select("cheapest", modality="image") == []


def test_select_skips_unknown_provider():
    # Unknown provider in the subset is skipped, not an error.
    order = _labels(_selector().select("cheapest", providers=["alpha", "ghost"]))
    assert order == ["alpha:text:a-nano", "alpha:text:a-frontier"]


# ---------- default catalog sanity ----------


def test_cheapest_is_price_monotonic_on_default_catalog():
    from loom.routing.selector import _price_of

    catalog = Catalog()
    selector = StrategySelector(catalog)
    candidates = selector.select("cheapest", modality="text")
    assert len(candidates) > 5
    prices = [
        _price_of(
            next(
                e
                for e in catalog.models(c.provider, "text")
                if e["id"] == c.model
            )
        )
        for c in candidates
    ]
    assert prices == sorted(prices)


def test_highest_quality_first_is_frontier_on_default_catalog():
    catalog = Catalog()
    selector = StrategySelector(catalog)
    top = selector.select("highest_quality", modality="text")[0]
    meta = catalog.metadata(top.provider, "text", top.model)
    assert meta["quality_tier"] == "frontier"


# ====================================================================
# Intelligent routing wired into generate() (issue #46)
# ====================================================================


def _any_provider_factory(raise_for: dict | None = None):
    """Generic fake dispatch that succeeds for any (provider, model)."""
    calls: list[dict] = []
    raise_for = raise_for or {}

    def fake_generate(provider, modality, model, params, prompt):
        calls.append({"provider": provider, "model": model})
        if model in raise_for:
            raise raise_for[model]
        return {"kind": "text", "text": f"ok:{provider}:{model}"}

    return calls, fake_generate


def test_generate_with_providers_picks_best_in_order(monkeypatch):
    calls, fake = _any_provider_factory()
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    expected = client._resolve_routing(
        provider=None, model=None,
        providers=["openai", "gemini"], router=None, modality="text",
    ).candidates
    result = client.generate(providers=["openai", "gemini"], prompt="hi")

    # First candidate (openai's best) answers; no fallback needed.
    assert result["_router"]["used"] == expected[0].label()
    assert expected[0].provider == "openai"
    assert len(calls) == 1


def test_generate_with_providers_preserves_order_not_strategy(monkeypatch):
    _, fake = _any_provider_factory()
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    # anthropic listed first -> it is tried first even though cheaper
    # providers exist elsewhere.
    result = client.generate(providers=["anthropic", "openai"], prompt="hi")
    assert result["_router"]["used"].startswith("anthropic:")


def test_generate_with_providers_fails_over(monkeypatch):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    cands = client._resolve_routing(
        provider=None, model=None,
        providers=["openai", "gemini"], router=None, modality="text",
    ).candidates
    up0, _ = client.catalog.resolve(cands[0].provider, "text", cands[0].model)

    _, fake = _any_provider_factory(raise_for={up0: RateLimitError("cap")})
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    result = client.generate(providers=["openai", "gemini"], prompt="hi")
    assert result["_router"]["used"] == cands[1].label()
    assert cands[1].provider == "gemini"


def test_generate_with_router_strategy(monkeypatch):
    calls, fake = _any_provider_factory()
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    expected = StrategySelector(client.catalog).select("cheapest")[0].label()
    result = client.generate(router="cheapest", prompt="hi")
    assert result["_router"]["used"] == expected
    assert len(calls) == 1


def test_generate_router_restricted_to_provider_subset(monkeypatch):
    _, fake = _any_provider_factory()
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    result = client.generate(router="cheapest", providers=["openai"], prompt="hi")
    assert result["_router"]["used"].startswith("openai:")


def test_generate_modality_defaults_to_text(monkeypatch):
    _, fake = _any_provider_factory()
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    # no modality passed -> defaults to "text"
    result = client.generate(provider="openai", model="gpt-4o-mini", prompt="hi")
    assert result["text"] == "ok:openai:gpt-4o-mini"
    assert "_router" not in result  # explicit path is not tagged


def test_generate_explicit_path_unchanged(monkeypatch):
    calls, fake = _any_provider_factory()
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    result = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
    )
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o-mini"
    assert len(calls) == 1


# ---------- invalid combinations ----------


def test_generate_provider_with_providers_raises():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ValueError):
        client.generate(provider="openai", model="gpt-4o", providers=["gemini"], prompt="x")


def test_generate_provider_with_router_raises():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ValueError):
        client.generate(provider="openai", model="gpt-4o", router="cheapest", prompt="x")


def test_generate_empty_providers_raises():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ValueError):
        client.generate(providers=[], prompt="x")


def test_generate_invalid_providers_type_raises():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(TypeError):
        client.generate(providers="openai", prompt="x")


def test_generate_unknown_router_raises():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ValueError):
        client.generate(router="smartest", prompt="x")


def test_generate_requires_provider_and_model_without_routing():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ValueError):
        client.generate(prompt="x")
    with pytest.raises(ValueError):
        client.generate(provider="openai", prompt="x")  # model missing


# ---------- async ----------


def test_async_generate_with_router(monkeypatch):
    async def fake_agenerate(provider, modality, model, params, prompt):
        return {"kind": "text", "text": f"ok:{provider}:{model}"}

    monkeypatch.setattr("loom._loom._providers.agenerate", fake_agenerate)
    client = AsyncLoom(api_keys={"OPENAI_API_KEY": "k"})
    expected = StrategySelector(client.catalog).select("cheapest")[0].label()
    result = asyncio.run(client.generate(router="cheapest", prompt="hi"))
    assert result["_router"]["used"] == expected


def test_async_generate_provider_with_router_raises():
    client = AsyncLoom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ValueError):
        asyncio.run(
            client.generate(provider="openai", model="gpt-4o", router="cheapest", prompt="x")
        )
