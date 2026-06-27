"""LoadBalancer — configurable load balancing (issue #56). Fully offline."""

import random

import pytest

from loom import LoadBalancer, Loom
from loom.catalog import Catalog
from loom.routing import BalancingStrategy, HealthRegistry


# ---------- construction / validation ----------


def test_strategy_coerce_accepts_string_and_enum():
    assert BalancingStrategy.coerce("round_robin") is BalancingStrategy.ROUND_ROBIN
    assert (
        BalancingStrategy.coerce(BalancingStrategy.WEIGHTED)
        is BalancingStrategy.WEIGHTED
    )


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        LoadBalancer("nope", providers=["a"])


def test_weighted_requires_weights():
    with pytest.raises(ValueError):
        LoadBalancer("weighted")


def test_non_weighted_requires_providers():
    with pytest.raises(ValueError):
        LoadBalancer("round_robin")


def test_weights_must_be_positive():
    with pytest.raises(ValueError):
        LoadBalancer("weighted", weights={"a": 0})
    with pytest.raises(ValueError):
        LoadBalancer("weighted", weights={"a": -1})


def test_empty_weights_rejected():
    with pytest.raises(ValueError):
        LoadBalancer("weighted", weights={})


def test_weighted_pool_derived_from_weights():
    bal = LoadBalancer("weighted", weights={"a": 1, "b": 1})
    assert set(bal.providers) == {"a", "b"}


def test_default_strategy_is_round_robin():
    bal = LoadBalancer(providers=["a", "b"])
    assert bal.strategy is BalancingStrategy.ROUND_ROBIN


# ---------- round_robin ----------


def test_round_robin_cycles_in_order():
    bal = LoadBalancer("round_robin", providers=["a", "b", "c"])
    assert [bal.pick() for _ in range(6)] == ["a", "b", "c", "a", "b", "c"]


def test_round_robin_skips_open_circuit():
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("a")  # a -> open
    bal = LoadBalancer("round_robin", providers=["a", "b", "c"])
    # Only the two healthy providers are cycled.
    assert [bal.pick(health) for _ in range(4)] == ["b", "c", "b", "c"]


# ---------- weighted ----------


def test_weighted_respects_configured_weights():
    bal = LoadBalancer(
        "weighted", weights={"a": 1, "b": 9}, rng=random.Random(0)
    )
    picks = [bal.pick() for _ in range(2000)]
    share_b = picks.count("b") / len(picks)
    # ~0.9 expected; allow generous slack for the seeded RNG.
    assert 0.82 < share_b < 0.97
    assert set(picks) == {"a", "b"}


def test_weighted_only_picks_healthy_and_renormalizes():
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("a")  # a (the heavy one) is open
    bal = LoadBalancer(
        "weighted", weights={"a": 99, "b": 1}, rng=random.Random(0)
    )
    picks = {bal.pick(health) for _ in range(50)}
    assert picks == {"b"}  # a excluded despite its huge weight


# ---------- least_latency ----------


def test_least_latency_picks_fastest():
    health = HealthRegistry()
    health.record_success("a", latency_ms=500.0)
    health.record_success("b", latency_ms=100.0)
    health.record_success("c", latency_ms=300.0)
    bal = LoadBalancer("least_latency", providers=["a", "b", "c"])
    assert bal.pick(health) == "b"


def test_least_latency_excludes_open_even_if_fastest():
    health = HealthRegistry(failure_threshold=1)
    health.record_success("b", latency_ms=10.0)
    health.record_failure("b")  # b is fastest but now open
    health.record_success("a", latency_ms=200.0)
    bal = LoadBalancer("least_latency", providers=["a", "b"])
    assert bal.pick(health) == "a"


def test_least_latency_unknown_latency_sorts_last():
    health = HealthRegistry()
    health.record_success("b", latency_ms=400.0)
    # "a" has no latency sample yet -> treated as slowest.
    bal = LoadBalancer("least_latency", providers=["a", "b"])
    assert bal.pick(health) == "b"


# ---------- least_failures ----------


def test_least_failures_picks_most_reliable():
    health = HealthRegistry(failure_threshold=100)  # keep circuits closed
    health.record_failure("a")
    health.record_failure("a")
    health.record_failure("b")
    # c has zero failures
    health.record_success("c", latency_ms=5.0)
    bal = LoadBalancer("least_failures", providers=["a", "b", "c"])
    assert bal.pick(health) == "c"


# ---------- health filtering / no-strand ----------


def test_all_open_falls_back_to_full_pool():
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("a")
    health.record_failure("b")  # everyone open
    bal = LoadBalancer("round_robin", providers=["a", "b"])
    # Rather than return None, the unfiltered pool is used.
    assert bal.pick(health) in {"a", "b"}


def test_pick_without_health_uses_full_pool():
    bal = LoadBalancer("least_latency", providers=["a", "b"])
    # No registry -> no latency data -> deterministic first.
    assert bal.pick() == "a"


def test_providers_override_restricts_pool():
    bal = LoadBalancer("round_robin", providers=["a", "b", "c"])
    assert [bal.pick(providers=["b", "c"]) for _ in range(4)] == [
        "b",
        "c",
        "b",
        "c",
    ]


# ---------- generate() integration ----------

_DATA = {
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


def _catalog():
    return Catalog(data=_DATA)


def _recording_fake():
    calls = []

    def fake(provider, modality, model, params, prompt):
        calls.append(provider)
        return {"kind": "text", "text": f"ok:{provider}"}

    return calls, fake


def test_generate_balances_automatic_path(monkeypatch):
    calls, fake = _recording_fake()
    monkeypatch.setattr("loom._loom._providers.generate", fake)
    bal = LoadBalancer("round_robin", providers=["alpha", "beta"])
    client = Loom(catalog=_catalog(), api_keys={}, balancer=bal)
    for _ in range(4):
        client.generate(prompt="hi")
    assert calls == ["alpha", "beta", "alpha", "beta"]


def test_generate_balancer_skips_open_provider(monkeypatch):
    calls, fake = _recording_fake()
    monkeypatch.setattr("loom._loom._providers.generate", fake)
    health = HealthRegistry(failure_threshold=1)
    health.record_failure("alpha")  # alpha open
    bal = LoadBalancer("round_robin", providers=["alpha", "beta"])
    client = Loom(catalog=_catalog(), api_keys={}, health=health, balancer=bal)
    for _ in range(3):
        client.generate(prompt="hi")
    assert calls == ["beta", "beta", "beta"]


def test_explicit_path_ignores_balancer(monkeypatch):
    calls, fake = _recording_fake()
    monkeypatch.setattr("loom._loom._providers.generate", fake)
    bal = LoadBalancer("round_robin", providers=["alpha", "beta"])
    client = Loom(catalog=_catalog(), api_keys={}, balancer=bal)
    # Explicit provider/model bypasses balancing entirely.
    client.generate(provider="alpha", model="a1", prompt="hi")
    client.generate(provider="alpha", model="a1", prompt="hi")
    assert calls == ["alpha", "alpha"]


def test_no_balancer_keeps_single_best(monkeypatch):
    calls, fake = _recording_fake()
    monkeypatch.setattr("loom._loom._providers.generate", fake)
    client = Loom(catalog=_catalog(), api_keys={})  # no balancer
    for _ in range(3):
        client.generate(prompt="hi")
    # Auto-select lands on the same provider every time (alpha by label).
    assert calls == ["alpha", "alpha", "alpha"]
