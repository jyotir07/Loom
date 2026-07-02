"""compare() — provider benchmarking (issue #58). Fully offline."""

import asyncio
import time

import pytest

from loom import AsyncLoom, Candidate, InMemoryCache, Loom
from loom._compare import CompareReport, CompareResult
from loom.catalog import Catalog
from loom.errors import ProviderError

# alpha: cheap + fast + standard quality. beta: pricey + slow + frontier.
_DATA = {
    "alpha": {
        "label": "Alpha",
        "modalities": {
            "text": [
                {"id": "a1", "name": "A1",
                 "input_inr_per_1m": 10.0, "output_inr_per_1m": 10.0,
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
                 "input_inr_per_1m": 100.0, "output_inr_per_1m": 100.0,
                 "quality_tier": "frontier", "latency_class": "slow",
                 "capabilities": ["text"]},
            ],
        },
    },
}


def _catalog():
    return Catalog(data=_DATA)


def _fake(*, sleep=None, fail=(), calls=None):
    """Build a provider fake. `sleep` maps provider->seconds; `fail` is a
    set of providers that should raise; `calls` records invocations."""
    sleep = sleep or {}
    fail = set(fail)

    def fake(provider, modality, model, params, prompt):
        if calls is not None:
            calls.append(provider)
        secs = sleep.get(provider)
        if secs:
            time.sleep(secs)
        if provider in fail:
            raise ProviderError(f"{provider} boom")
        return {
            "kind": "text",
            "text": f"ok:{provider}",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

    return fake


# ---------- rows ----------


def test_compare_returns_row_per_provider(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    report = client.compare(prompt="hi", providers=["alpha", "beta"])
    assert isinstance(report, CompareReport)
    assert len(report) == 2
    assert [r.provider for r in report] == ["alpha", "beta"]
    assert all(r.ok for r in report)


def test_compare_reports_metrics(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    report = client.compare(prompt="hi", providers=["alpha"])
    row = report[0]
    assert row.model == "a1"
    assert row.tokens == 150
    assert row.cost_usd is not None and row.cost_usd > 0
    assert row.output == "ok:alpha"
    assert row.latency_ms >= 0


def test_compare_summary_picks_winners(monkeypatch):
    # beta sleeps so alpha is measurably fastest as well as cheapest.
    monkeypatch.setattr(
        "loom._loom._providers.generate", _fake(sleep={"beta": 0.06})
    )
    client = Loom(catalog=_catalog(), api_keys={})
    report = client.compare(prompt="hi", providers=["alpha", "beta"])
    assert report.summary.cheapest.provider == "alpha"
    assert report.summary.fastest.provider == "alpha"
    assert report.summary.highest_quality.provider == "beta"


# ---------- partial failure ----------


def test_compare_partial_failure_is_captured(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate", _fake(fail={"beta"})
    )
    client = Loom(catalog=_catalog(), api_keys={})
    report = client.compare(prompt="hi", providers=["alpha", "beta"])
    by_provider = {r.provider: r for r in report}
    assert by_provider["alpha"].ok is True
    beta = by_provider["beta"]
    assert beta.ok is False
    assert beta.output is None
    assert "beta boom" in beta.error
    # Summary is built only from the successful row.
    assert report.summary.cheapest.provider == "alpha"
    assert report.summary.fastest.provider == "alpha"


def test_compare_all_failing_has_empty_summary(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate", _fake(fail={"alpha", "beta"})
    )
    client = Loom(catalog=_catalog(), api_keys={})
    report = client.compare(prompt="hi", providers=["alpha", "beta"])
    assert all(not r.ok for r in report)
    assert report.summary.cheapest is None
    assert report.summary.fastest is None
    assert report.summary.highest_quality is None


# ---------- concurrency ----------


def test_compare_runs_concurrently(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate",
        _fake(sleep={"alpha": 0.1, "beta": 0.1}),
    )
    client = Loom(catalog=_catalog(), api_keys={})
    started = time.perf_counter()
    client.compare(prompt="hi", providers=["alpha", "beta"])
    elapsed = time.perf_counter() - started
    # Serial would be ~0.2s; parallel should be well under.
    assert elapsed < 0.18


# ---------- input coercion ----------


def test_compare_accepts_candidate_and_tuple(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    report = client.compare(
        prompt="hi",
        providers=[Candidate("alpha", "text", "a1"), ("beta", "b1")],
    )
    assert [(r.provider, r.model) for r in report] == [
        ("alpha", "a1"),
        ("beta", "b1"),
    ]


def test_compare_empty_providers_raises(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(ValueError):
        client.compare(prompt="hi", providers=[])


def test_compare_provider_without_modality_raises(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(ValueError):
        client.compare(prompt="hi", providers=["alpha"], modality="image")


def test_compare_bad_entry_type_raises(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(TypeError):
        client.compare(prompt="hi", providers=[123])


# ---------- cache bypass ----------


def test_compare_bypasses_cache_by_default(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("loom._loom._providers.generate", _fake(calls=calls))
    client = Loom(catalog=_catalog(), api_keys={}, cache=InMemoryCache())
    client.compare(prompt="hi", providers=["alpha"])
    client.compare(prompt="hi", providers=["alpha"])
    # No cache reuse: the provider is hit on both runs.
    assert calls == ["alpha", "alpha"]


# ---------- async ----------


def _afake(*, sleep=None, fail=()):
    sleep = sleep or {}
    fail = set(fail)

    async def fake(provider, modality, model, params, prompt):
        secs = sleep.get(provider)
        if secs:
            await asyncio.sleep(secs)
        if provider in fail:
            raise ProviderError(f"{provider} boom")
        return {
            "kind": "text",
            "text": f"ok:{provider}",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

    return fake


def test_acompare_returns_rows(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.agenerate", _afake())
    client = AsyncLoom(catalog=_catalog(), api_keys={})
    report = asyncio.run(
        client.compare(prompt="hi", providers=["alpha", "beta"])
    )
    assert [r.provider for r in report] == ["alpha", "beta"]
    assert all(r.ok for r in report)
    assert report.summary.highest_quality.provider == "beta"


def test_acompare_partial_failure_is_captured(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.agenerate", _afake(fail={"beta"}))
    client = AsyncLoom(catalog=_catalog(), api_keys={})
    report = asyncio.run(
        client.compare(prompt="hi", providers=["alpha", "beta"])
    )
    by_provider = {r.provider: r for r in report}
    assert by_provider["alpha"].ok is True
    assert by_provider["beta"].ok is False
    assert "beta boom" in by_provider["beta"].error


def test_acompare_runs_concurrently(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.agenerate",
        _afake(sleep={"alpha": 0.1, "beta": 0.1}),
    )
    client = AsyncLoom(catalog=_catalog(), api_keys={})
    started = time.perf_counter()
    asyncio.run(client.compare(prompt="hi", providers=["alpha", "beta"]))
    elapsed = time.perf_counter() - started
    assert elapsed < 0.18
