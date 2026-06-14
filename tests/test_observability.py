"""Observability: SQLite sink + log handler + queries + dashboard blueprint."""

from __future__ import annotations

import logging
import time

import pytest

from loom.observability import LoomLogHandler, SQLiteSink, make_dashboard
from loom.observability import queries as q


# ---------- sink ----------


def _mk_sink():
    return SQLiteSink(":memory:")


def test_sink_schema_init_no_events():
    sink = _mk_sink()
    assert sink.count() == 0


def test_sink_write_and_count():
    sink = _mk_sink()
    sink.write({
        "provider": "openai", "modality": "text", "model": "gpt-4o-mini",
        "latency_ms": 123.0, "ok": True,
    })
    assert sink.count() == 1


def test_sink_write_defaults_ts_when_missing():
    sink = _mk_sink()
    before = time.time()
    sink.write({
        "provider": "openai", "modality": "text", "model": "x",
        "latency_ms": 10.0,
    })
    after = time.time()
    rows = sink.fetch(sql="SELECT ts FROM loom_events")
    assert before - 0.1 <= rows[0]["ts"] <= after + 0.1


def test_sink_persists_optional_fields_as_none():
    sink = _mk_sink()
    sink.write({
        "provider": "openai", "modality": "text", "model": "x",
        "latency_ms": 1.0,
    })
    rows = sink.fetch(sql="SELECT cost_usd, error_type FROM loom_events")
    assert rows[0]["cost_usd"] is None
    assert rows[0]["error_type"] is None


# ---------- handler ----------


def test_handler_writes_record_loom_payload_to_sink():
    sink = _mk_sink()
    h = LoomLogHandler(sink)
    logger = logging.getLogger("loom.test.handler")
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

    logger.info(
        "loom.generate ok",
        extra={"loom": {
            "provider": "openai", "modality": "text", "model": "gpt-4o-mini",
            "latency_ms": 200.0, "ok": True, "cached": False, "deduped": False,
            "cost_usd": 0.0001,
        }},
    )
    rows = sink.fetch(sql="SELECT * FROM loom_events")
    assert len(rows) == 1
    assert rows[0]["provider"] == "openai"
    assert rows[0]["cost_usd"] == 0.0001

    logger.removeHandler(h)


def test_handler_ignores_records_without_loom_payload():
    sink = _mk_sink()
    h = LoomLogHandler(sink)
    logger = logging.getLogger("loom.test.handler.skip")
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

    logger.info("just a plain log line, no loom dict")
    assert sink.count() == 0
    logger.removeHandler(h)


def test_handler_integrates_with_log_call():
    """End-to-end: loom._logging.log_call -> handler -> sink."""
    from loom._logging import log_call, logger as loom_logger

    sink = _mk_sink()
    h = LoomLogHandler(sink)
    loom_logger.addHandler(h)
    loom_logger.setLevel(logging.INFO)
    try:
        log_call(
            provider="openai", modality="text", model="gpt-4o-mini",
            upstream_model="gpt-4o-mini",
            latency_ms=42.0,
            result={
                "kind": "text", "text": "hi",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                "cost": {"usd": 0.0002, "local": 0.017, "local_currency": "INR"},
            },
        )
    finally:
        loom_logger.removeHandler(h)

    rows = sink.fetch(sql="SELECT * FROM loom_events")
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 10
    assert rows[0]["cost_usd"] == 0.0002
    assert rows[0]["ok"] == 1


# ---------- queries ----------


def _seed(sink: SQLiteSink, *, ts: float | None = None, **fields):
    ev = {
        "provider": "openai", "modality": "text", "model": "gpt-4o-mini",
        "latency_ms": 100.0, "ok": True, "cached": False, "deduped": False,
        "input_tokens": 10, "output_tokens": 5,
        "cost_usd": 0.001,
    }
    ev.update(fields)
    if ts is not None:
        ev["ts"] = ts
    sink.write(ev)


def test_summary_rollup_counts_and_rates():
    sink = _mk_sink()
    _seed(sink, cost_usd=0.001)
    _seed(sink, cost_usd=0.002, cached=True)
    _seed(sink, cost_usd=0.003, deduped=True)
    _seed(sink, cost_usd=0.0, ok=False, error_type="RateLimitError")

    s = q.summary(sink)
    assert s["calls"] == 4
    assert s["cost_usd"] == pytest.approx(0.006)
    assert s["cache_hit_pct"] == 25.0
    assert s["dedup_pct"] == 25.0
    assert s["error_pct"] == 25.0


def test_summary_with_window_filters_old_events():
    sink = _mk_sink()
    old = time.time() - 7200  # 2h ago
    recent = time.time()
    _seed(sink, ts=old, cost_usd=10.0)
    _seed(sink, ts=recent, cost_usd=0.5)

    s_1h = q.summary(sink, window_seconds=3600)
    assert s_1h["calls"] == 1
    assert s_1h["cost_usd"] == pytest.approx(0.5)

    s_all = q.summary(sink)
    assert s_all["calls"] == 2


def test_by_provider_groups_and_orders_by_cost():
    sink = _mk_sink()
    _seed(sink, provider="openai", cost_usd=0.5)
    _seed(sink, provider="anthropic", cost_usd=2.0)
    _seed(sink, provider="anthropic", cost_usd=1.0)

    rows = q.by_provider(sink)
    assert [r["provider"] for r in rows] == ["anthropic", "openai"]
    assert rows[0]["calls"] == 2
    assert rows[0]["cost_usd"] == pytest.approx(3.0)


def test_by_model_respects_limit():
    sink = _mk_sink()
    for i in range(5):
        _seed(sink, model=f"m{i}", cost_usd=float(i + 1))
    rows = q.by_model(sink, limit=3)
    assert len(rows) == 3
    assert rows[0]["model"] == "m4"
    assert rows[0]["cost_usd"] == pytest.approx(5.0)


def test_recent_orders_newest_first():
    sink = _mk_sink()
    _seed(sink, model="a")
    _seed(sink, model="b")
    _seed(sink, model="c")
    rows = q.recent(sink, limit=10)
    assert [r["model"] for r in rows] == ["c", "b", "a"]


# ---------- dashboard ----------


@pytest.fixture
def app_with_dashboard():
    flask = pytest.importorskip("flask")
    sink = _mk_sink()
    _seed(sink, cost_usd=0.05)
    _seed(sink, provider="anthropic", cost_usd=0.02, cached=True)

    app = flask.Flask(__name__)
    app.register_blueprint(make_dashboard(sink), url_prefix="/loom-admin")
    return app, sink


def test_dashboard_html_renders(app_with_dashboard):
    app, _ = app_with_dashboard
    client = app.test_client()
    resp = client.get("/loom-admin/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Loom" in body
    assert "openai" in body
    assert "anthropic" in body


def test_dashboard_window_param(app_with_dashboard):
    app, _ = app_with_dashboard
    client = app.test_client()
    resp = client.get("/loom-admin/?window=1h")
    assert resp.status_code == 200
    # The 1h pill should be the active one in the nav.
    assert 'class="active"' in resp.get_data(as_text=True)


def test_dashboard_api_summary(app_with_dashboard):
    app, _ = app_with_dashboard
    client = app.test_client()
    resp = client.get("/loom-admin/api/summary?window=all")
    data = resp.get_json()
    assert data["window"] == "all"
    assert data["calls"] == 2
    assert data["cost_usd"] == pytest.approx(0.07)


def test_dashboard_api_by_provider(app_with_dashboard):
    app, _ = app_with_dashboard
    client = app.test_client()
    resp = client.get("/loom-admin/api/by-provider?window=all")
    data = resp.get_json()
    providers = {p["provider"]: p for p in data["providers"]}
    assert set(providers) == {"openai", "anthropic"}


def test_dashboard_unknown_window_falls_back_to_default(app_with_dashboard):
    app, _ = app_with_dashboard
    client = app.test_client()
    resp = client.get("/loom-admin/api/summary?window=nonsense")
    assert resp.status_code == 200
    assert resp.get_json()["window"] == "24h"
