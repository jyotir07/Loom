"""Analytics API + event recording (issue #66). Fully offline."""

import asyncio

import pytest

from loom import Analytics, AsyncLoom, InMemorySink, Loom
from loom.catalog import Catalog
from loom.errors import ProviderError
from loom._retry import RetryPolicy

_DATA = {
    "alpha": {
        "label": "Alpha",
        "modalities": {"text": [{"id": "a1", "name": "A1"}]},
    },
    "beta": {
        "label": "Beta",
        "modalities": {"text": [{"id": "b1", "name": "B1"}]},
    },
}


def _catalog():
    return Catalog(data=_DATA)


def _fake(text="ok", *, usage=None):
    def fake(provider, modality, model, params, prompt):
        out = {"kind": "text", "text": text}
        if usage is not None:
            out["usage"] = usage
        return out

    return fake


# ---------- default sink + accessor ----------


def test_analytics_enabled_by_default():
    client = Loom(catalog=_catalog(), api_keys={})
    assert isinstance(client.analytics(), Analytics)


def test_analytics_disabled_raises():
    client = Loom(catalog=_catalog(), api_keys={}, analytics=False)
    with pytest.raises(RuntimeError):
        client.analytics()


def test_custom_sink_is_used():
    sink = InMemorySink()
    client = Loom(catalog=_catalog(), api_keys={}, analytics=sink)
    assert client.analytics()._sink is sink


# ---------- event recording ----------


def test_generate_records_event(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate",
        _fake(usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}),
    )
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="alpha", model="a1", prompt="hi")

    summary = client.analytics().summary()
    assert summary["calls"] == 1
    assert summary["input_tokens"] == 100
    assert summary["output_tokens"] == 50


def test_summary_and_by_provider(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="alpha", model="a1", prompt="one")
    client.generate(provider="alpha", model="a1", prompt="two")
    client.generate(provider="beta", model="b1", prompt="three")

    a = client.analytics()
    assert a.summary()["calls"] == 3
    by_provider = {r["provider"]: r for r in a.by_provider()}
    assert by_provider["alpha"]["calls"] == 2
    assert by_provider["beta"]["calls"] == 1


def test_by_model_and_recent(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="alpha", model="a1", prompt="x")
    client.generate(provider="beta", model="b1", prompt="y")

    a = client.analytics()
    models = {r["model"] for r in a.by_model()}
    assert models == {"a1", "b1"}
    recent = a.recent(limit=10)
    assert len(recent) == 2
    # newest first
    assert recent[0]["provider"] == "beta"


def test_isolated_sinks_per_client(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    c1 = Loom(catalog=_catalog(), api_keys={})
    c2 = Loom(catalog=_catalog(), api_keys={})
    c1.generate(provider="alpha", model="a1", prompt="x")
    assert c1.analytics().summary()["calls"] == 1
    # A second client's sink is untouched.
    assert c2.analytics().summary()["calls"] == 0


# ---------- retries ----------


def test_retries_recorded(monkeypatch):
    calls = {"n": 0}

    def flaky(provider, modality, model, params, prompt):
        calls["n"] += 1
        if calls["n"] < 3:
            from loom.errors import RateLimitError

            raise RateLimitError("429")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", flaky)
    # No sleep between retries.
    retry = RetryPolicy(max_attempts=5, base_delay=0.0, jitter=0.0)
    client = Loom(catalog=_catalog(), api_keys={}, retry=retry)
    client.generate(provider="alpha", model="a1", prompt="x")

    recent = client.analytics().recent(limit=1)
    assert recent[0]["retries"] == 2  # 3 attempts -> 2 retries
    assert client.analytics().summary()["retries"] == 2


def test_no_retries_recorded_on_clean_call(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="alpha", model="a1", prompt="x")
    assert client.analytics().recent(limit=1)[0]["retries"] == 0


def test_failure_records_error_event(monkeypatch):
    def boom(provider, modality, model, params, prompt):
        raise ProviderError("nope")

    monkeypatch.setattr("loom._loom._providers.generate", boom)
    # Disable retry so it fails immediately.
    client = Loom(catalog=_catalog(), api_keys={}, retry=None)
    with pytest.raises(ProviderError):
        client.generate(provider="alpha", model="a1", prompt="x")

    summary = client.analytics().summary()
    assert summary["calls"] == 1
    assert summary["error_pct"] == 100.0


# ---------- tags ----------


def test_tags_recorded(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(
        provider="alpha", model="a1", prompt="x", tags={"feature": "chat"}
    )
    recent = client.analytics().recent(limit=1)
    assert recent[0]["tags"] == {"feature": "chat"}


def test_no_tags_leaves_null(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="alpha", model="a1", prompt="x")
    assert client.analytics().recent(limit=1)[0]["tags"] is None


# ---------- windows ----------


def test_summary_window_accepts_named_and_seconds(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake())
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="alpha", model="a1", prompt="x")
    a = client.analytics()
    assert a.summary(window="24h")["calls"] == 1
    assert a.summary(window=3600)["calls"] == 1
    assert a.summary(window=None)["calls"] == 1


def test_summary_window_rejects_unknown(monkeypatch):
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(ValueError):
        client.analytics().summary(window="bogus")


# ---------- async ----------


def _afake(text="ok"):
    async def fake(provider, modality, model, params, prompt):
        return {"kind": "text", "text": text}

    return fake


def test_async_generate_records_event(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.agenerate", _afake())
    client = AsyncLoom(catalog=_catalog(), api_keys={})
    asyncio.run(client.generate(provider="alpha", model="a1", prompt="x"))
    assert client.analytics().summary()["calls"] == 1


# ---------- migration ----------


def test_sqlite_sink_migrates_existing_db(tmp_path):
    """An older DB without retries/tags columns gets them added on open."""
    import sqlite3

    from loom.observability.sink import SQLiteSink

    db = tmp_path / "old.db"
    # Simulate a pre-#66 schema (no retries / tags columns).
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE loom_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL, provider TEXT NOT NULL, modality TEXT NOT NULL,
            model TEXT NOT NULL, upstream_model TEXT, latency_ms REAL NOT NULL,
            input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
            cost_usd REAL, cost_local REAL, cost_currency TEXT,
            ok INTEGER NOT NULL, cached INTEGER NOT NULL, deduped INTEGER NOT NULL,
            error_type TEXT, error TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    sink = SQLiteSink(str(db))  # opening runs the migration
    sink.write(
        {"provider": "alpha", "modality": "text", "model": "a1",
         "latency_ms": 1.0, "retries": 2, "tags": {"k": "v"}}
    )
    rows = sink.fetch(sql="SELECT retries, tags FROM loom_events")
    assert rows[0]["retries"] == 2
    sink.close()
