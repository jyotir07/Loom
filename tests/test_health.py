"""HealthRegistry — provider health tracking (issue #52). Fully offline."""

import pytest

from loom import FallbackPolicy, Loom
from loom.catalog import Catalog
from loom.errors import AuthError, ProviderError, RateLimitError
from loom.routing import (
    CircuitState,
    HealthRegistry,
    ProviderHealth,
    StrategySelector,
)


class _Clock:
    """Manually-advanced clock for deterministic cooldown tests."""

    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


# ---------- latency / rates ----------


def test_unknown_provider_is_healthy():
    r = HealthRegistry()
    assert r.is_available("openai") is True
    assert r.state("openai") is CircuitState.CLOSED
    h = r.status("openai")
    assert h.total == 0
    assert h.failure_rate == 0.0
    assert h.latency_ms is None


def test_ewma_latency():
    r = HealthRegistry(ewma_alpha=0.5)
    r.record_success("openai", latency_ms=100.0)
    assert r.status("openai").latency_ms == 100.0
    r.record_success("openai", latency_ms=200.0)
    # 0.5*200 + 0.5*100 = 150
    assert r.status("openai").latency_ms == 150.0


def test_success_and_failure_rates():
    r = HealthRegistry(failure_threshold=10)
    r.record_success("openai", latency_ms=10.0)
    r.record_success("openai", latency_ms=10.0)
    r.record_failure("openai", error="boom")
    h = r.status("openai")
    assert h.successes == 2
    assert h.failures == 1
    assert h.total == 3
    assert round(h.failure_rate, 3) == round(1 / 3, 3)
    assert round(h.success_rate, 3) == round(2 / 3, 3)
    assert h.last_error == "boom"


# ---------- circuit breaker ----------


def test_breaker_trips_after_threshold():
    r = HealthRegistry(failure_threshold=3)
    r.record_failure("openai")
    r.record_failure("openai")
    assert r.state("openai") is CircuitState.CLOSED  # not yet
    r.record_failure("openai")
    assert r.state("openai") is CircuitState.OPEN
    assert r.is_available("openai") is False


def test_success_resets_consecutive_failures():
    r = HealthRegistry(failure_threshold=3)
    r.record_failure("openai")
    r.record_failure("openai")
    r.record_success("openai", latency_ms=5.0)
    r.record_failure("openai")
    r.record_failure("openai")
    # only two consecutive failures since the success -> still closed
    assert r.state("openai") is CircuitState.CLOSED


def test_open_transitions_to_half_open_after_cooldown():
    clock = _Clock()
    r = HealthRegistry(failure_threshold=1, recovery_timeout=30.0, time_fn=clock)
    r.record_failure("openai")
    assert r.state("openai") is CircuitState.OPEN
    clock.advance(29.0)
    assert r.state("openai") is CircuitState.OPEN  # cooldown not elapsed
    clock.advance(2.0)  # now 31s
    assert r.state("openai") is CircuitState.HALF_OPEN
    assert r.is_available("openai") is True  # a trial is allowed


def test_half_open_success_closes_breaker():
    clock = _Clock()
    r = HealthRegistry(failure_threshold=1, recovery_timeout=10.0, time_fn=clock)
    r.record_failure("openai")
    clock.advance(11.0)
    assert r.state("openai") is CircuitState.HALF_OPEN
    r.record_success("openai", latency_ms=5.0)
    assert r.state("openai") is CircuitState.CLOSED
    assert r.status("openai").cooldown_until is None


def test_half_open_failure_reopens_breaker():
    clock = _Clock()
    r = HealthRegistry(failure_threshold=1, recovery_timeout=10.0, time_fn=clock)
    r.record_failure("openai")
    clock.advance(11.0)
    assert r.state("openai") is CircuitState.HALF_OPEN
    r.record_failure("openai")  # trial fails
    assert r.state("openai") is CircuitState.OPEN
    # cooldown reset relative to "now" (11s) -> opens again until 21s
    clock.advance(11.0)  # now 22s
    assert r.state("openai") is CircuitState.HALF_OPEN


# ---------- rate limit cooldown ----------


def test_rate_limit_trips_immediately_with_its_own_cooldown():
    clock = _Clock()
    r = HealthRegistry(
        failure_threshold=5, recovery_timeout=10.0, rate_limit_cooldown=60.0,
        time_fn=clock,
    )
    r.record_failure("openai", rate_limited=True)
    # tripped on a single rate-limit, despite threshold=5
    assert r.state("openai") is CircuitState.OPEN
    clock.advance(11.0)  # past recovery_timeout but not rate_limit_cooldown
    assert r.state("openai") is CircuitState.OPEN
    clock.advance(50.0)  # now 61s > 60s
    assert r.state("openai") is CircuitState.HALF_OPEN


# ---------- snapshot / reset ----------


def test_snapshot_and_reset():
    r = HealthRegistry()
    r.record_success("openai", latency_ms=10.0)
    r.record_failure("gemini")
    snap = r.snapshot()
    assert set(snap) == {"openai", "gemini"}
    assert isinstance(snap["openai"], ProviderHealth)
    r.reset("openai")
    assert set(r.snapshot()) == {"gemini"}
    r.reset()
    assert r.snapshot() == {}


def test_status_returns_a_copy():
    r = HealthRegistry()
    r.record_success("openai", latency_ms=10.0)
    h = r.status("openai")
    h.successes = 999
    assert r.status("openai").successes == 1


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        HealthRegistry(ewma_alpha=0.0)
    with pytest.raises(ValueError):
        HealthRegistry(failure_threshold=0)


# ---------- integration with generate() ----------


def _provider_fake(behavior):
    def fake(provider, modality, model, params, prompt):
        exc = behavior.get(provider)
        if exc is not None:
            raise exc
        return {"kind": "text", "text": f"ok:{provider}"}

    return fake


def test_generate_records_success(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _provider_fake({}))
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    client.generate(provider="openai", model="gpt-4o-mini", prompt="hi")
    h = client.health.status("openai")
    assert h.successes == 1
    assert h.latency_ms is not None


def test_generate_records_failure_and_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate",
        _provider_fake({"openai": RateLimitError("429")}),
    )
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    with pytest.raises(RateLimitError):
        client.generate(provider="openai", model="gpt-4o-mini", prompt="hi")
    assert client.health.state("openai") is CircuitState.OPEN
    assert client.health.is_available("openai") is False


def test_generate_health_disabled(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _provider_fake({}))
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, health=None)
    client.generate(provider="openai", model="gpt-4o-mini", prompt="hi")
    assert client.health is None


def test_cache_hit_does_not_record_health(monkeypatch):
    from loom import InMemoryCache

    monkeypatch.setattr("loom._loom._providers.generate", _provider_fake({}))
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, cache=InMemoryCache())
    client.generate(provider="openai", model="gpt-4o-mini", prompt="hi")
    client.generate(provider="openai", model="gpt-4o-mini", prompt="hi")  # cache hit
    # Only the real upstream call recorded a success, not the cache hit.
    assert client.health.status("openai").successes == 1


# ---------- health-aware routing (issue #54) ----------

# Two interchangeable providers, one model each, identical price/quality/
# latency — so without health the order is purely label-sorted
# (alpha < beta). That makes any health-driven reordering observable.
_ROUTING_DATA = {
    "alpha": {
        "label": "Alpha",
        "modalities": {
            "text": [
                {"id": "a1", "name": "A1",
                 "input_inr_per_1m": 1.0, "output_inr_per_1m": 1.0,
                 "quality_tier": "standard", "latency_class": "fast",
                 "capabilities": ["text"]},
            ],
        },
    },
    "beta": {
        "label": "Beta",
        "modalities": {
            "text": [
                {"id": "b1", "name": "B1",
                 "input_inr_per_1m": 1.0, "output_inr_per_1m": 1.0,
                 "quality_tier": "standard", "latency_class": "fast",
                 "capabilities": ["text"]},
            ],
        },
    },
}


def _routing_catalog():
    return Catalog(data=_ROUTING_DATA)


def _labels(candidates):
    return [c.label() for c in candidates]


# -- selector-level --


def test_selector_excludes_open_circuit():
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("alpha")  # alpha -> open
    sel = StrategySelector(_routing_catalog(), health=health)
    assert _labels(sel.select("cheapest")) == ["beta:text:b1"]
    assert sel.best("cheapest").provider == "beta"


def test_selector_deprioritizes_half_open():
    clock = _Clock()
    health = HealthRegistry(
        failure_threshold=1, recovery_timeout=10.0, time_fn=clock
    )
    health.record_failure("alpha")  # alpha -> open
    clock.advance(11.0)  # alpha -> half_open (a trial is allowed)
    sel = StrategySelector(_routing_catalog(), health=health)
    # Healthy beta ranks ahead of recovering alpha despite alpha's label
    # sorting first.
    assert _labels(sel.select("cheapest")) == ["beta:text:b1", "alpha:text:a1"]


def test_selector_all_open_keeps_full_pool():
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("alpha")
    health.record_failure("beta")  # everyone is open
    sel = StrategySelector(_routing_catalog(), health=health)
    # Rather than strand the caller, fall back to the unfiltered order.
    assert _labels(sel.select("cheapest")) == ["alpha:text:a1", "beta:text:b1"]


def test_selector_without_health_is_unchanged():
    sel = StrategySelector(_routing_catalog())  # no health
    assert _labels(sel.select("cheapest")) == ["alpha:text:a1", "beta:text:b1"]


# -- generate() integration --


def _routing_client(health):
    return Loom(catalog=_routing_catalog(), api_keys={}, health=health)


def test_router_strategy_skips_open_provider(monkeypatch):
    calls = []

    def fake(provider, modality, model, params, prompt):
        calls.append(provider)
        return {"kind": "text", "text": f"ok:{provider}"}

    monkeypatch.setattr("loom._loom._providers.generate", fake)
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("alpha")  # alpha -> open
    client = _routing_client(health)
    result = client.generate(router="cheapest", prompt="hi")
    assert result["provider"] == "beta"
    assert calls == ["beta"]  # alpha never attempted


def test_providers_list_skips_open_provider(monkeypatch):
    calls = []

    def fake(provider, modality, model, params, prompt):
        calls.append(provider)
        return {"kind": "text", "text": f"ok:{provider}"}

    monkeypatch.setattr("loom._loom._providers.generate", fake)
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("alpha")  # alpha -> open
    client = _routing_client(health)
    # Caller prefers alpha first, but it's degraded -> routed to beta.
    result = client.generate(providers=["alpha", "beta"], prompt="hi")
    assert result["provider"] == "beta"
    assert calls == ["beta"]


def test_providers_list_preserves_order_when_healthy(monkeypatch):
    calls = []

    def fake(provider, modality, model, params, prompt):
        calls.append(provider)
        return {"kind": "text", "text": f"ok:{provider}"}

    monkeypatch.setattr("loom._loom._providers.generate", fake)
    client = _routing_client(HealthRegistry())  # no failures recorded
    result = client.generate(providers=["beta", "alpha"], prompt="hi")
    # All healthy -> caller's order wins; beta is attempted first.
    assert result["provider"] == "beta"


def test_fallback_chain_skips_open_provider(monkeypatch):
    calls = []

    def fake(provider, modality, model, params, prompt):
        calls.append(provider)
        return {"kind": "text", "text": f"ok:{provider}"}

    monkeypatch.setattr("loom._loom._providers.generate", fake)
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("alpha")  # alpha -> open
    client = _routing_client(health)
    result = client.generate(
        prompt="hi",
        fallback=FallbackPolicy(providers=["alpha", "beta"], retries=3),
    )
    assert result["provider"] == "beta"
    assert calls == ["beta"]


def test_routing_unaffected_when_health_disabled(monkeypatch):
    calls = []

    def fake(provider, modality, model, params, prompt):
        calls.append(provider)
        return {"kind": "text", "text": f"ok:{provider}"}

    monkeypatch.setattr("loom._loom._providers.generate", fake)
    client = Loom(catalog=_routing_catalog(), api_keys={}, health=None)
    # No health data at all -> plain strategy order (alpha first by label).
    result = client.generate(router="cheapest", prompt="hi")
    assert result["provider"] == "alpha"
