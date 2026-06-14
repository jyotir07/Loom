"""Aggregation queries that power the dashboard.

These run against the EventSink protocol (SQL today, anything else
that speaks SQL tomorrow). Each function returns a plain dict / list
of dicts — easy to JSON-serialize, easy to test.

Time window: `window_seconds` defaults to None ("all time"). If passed,
queries filter to `ts >= now - window_seconds`.
"""

from __future__ import annotations

import time
from typing import Any

from loom.observability.sink import EventSink


# --- well-known time windows for the UI ---
WINDOWS: dict[str, int | None] = {
    "1h": 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
    "all": None,
}


def _ts_clause(window_seconds: int | None) -> tuple[str, tuple[Any, ...]]:
    """Build the WHERE-clause fragment and bound params for a time filter."""
    if window_seconds is None:
        return "1=1", ()
    cutoff = time.time() - window_seconds
    return "ts >= ?", (cutoff,)


def summary(sink: EventSink, *, window_seconds: int | None = None) -> dict[str, Any]:
    """Top-line rollup: calls, cost, latency, cache hit %, dedup %, error %."""
    where, params = _ts_clause(window_seconds)
    sql = f"""
        SELECT
            COUNT(*) AS calls,
            COALESCE(SUM(cost_usd), 0.0) AS cost_usd,
            COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            SUM(CASE WHEN cached = 1 THEN 1 ELSE 0 END) AS cached_calls,
            SUM(CASE WHEN deduped = 1 THEN 1 ELSE 0 END) AS deduped_calls,
            SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS failed_calls
        FROM loom_events
        WHERE {where}
    """
    row = sink.fetch(sql=sql, params=params)[0]
    calls = int(row["calls"] or 0)

    def _pct(numerator: Any) -> float:
        n = int(numerator or 0)
        return round(100.0 * n / calls, 2) if calls else 0.0

    return {
        "calls": calls,
        "cost_usd": round(float(row["cost_usd"] or 0.0), 6),
        "avg_latency_ms": round(float(row["avg_latency_ms"] or 0.0), 2),
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "cache_hit_pct": _pct(row["cached_calls"]),
        "dedup_pct": _pct(row["deduped_calls"]),
        "error_pct": _pct(row["failed_calls"]),
    }


def by_provider(
    sink: EventSink, *, window_seconds: int | None = None
) -> list[dict[str, Any]]:
    where, params = _ts_clause(window_seconds)
    sql = f"""
        SELECT
            provider,
            COUNT(*) AS calls,
            COALESCE(SUM(cost_usd), 0.0) AS cost_usd,
            COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms,
            SUM(CASE WHEN cached = 1 THEN 1 ELSE 0 END) AS cached_calls,
            SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS failed_calls
        FROM loom_events
        WHERE {where}
        GROUP BY provider
        ORDER BY cost_usd DESC
    """
    rows = sink.fetch(sql=sql, params=params)
    out: list[dict[str, Any]] = []
    for r in rows:
        calls = int(r["calls"] or 0)
        out.append({
            "provider": r["provider"],
            "calls": calls,
            "cost_usd": round(float(r["cost_usd"] or 0.0), 6),
            "avg_latency_ms": round(float(r["avg_latency_ms"] or 0.0), 2),
            "cache_hit_pct": round(100.0 * int(r["cached_calls"] or 0) / calls, 2) if calls else 0.0,
            "error_pct": round(100.0 * int(r["failed_calls"] or 0) / calls, 2) if calls else 0.0,
        })
    return out


def by_model(
    sink: EventSink, *, window_seconds: int | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    where, params = _ts_clause(window_seconds)
    sql = f"""
        SELECT
            provider,
            modality,
            model,
            COUNT(*) AS calls,
            COALESCE(SUM(cost_usd), 0.0) AS cost_usd,
            COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms,
            SUM(CASE WHEN cached = 1 THEN 1 ELSE 0 END) AS cached_calls
        FROM loom_events
        WHERE {where}
        GROUP BY provider, modality, model
        ORDER BY cost_usd DESC
        LIMIT ?
    """
    rows = sink.fetch(sql=sql, params=(*params, int(limit)))
    out: list[dict[str, Any]] = []
    for r in rows:
        calls = int(r["calls"] or 0)
        out.append({
            "provider": r["provider"],
            "modality": r["modality"],
            "model": r["model"],
            "calls": calls,
            "cost_usd": round(float(r["cost_usd"] or 0.0), 6),
            "avg_latency_ms": round(float(r["avg_latency_ms"] or 0.0), 2),
            "cache_hit_pct": round(100.0 * int(r["cached_calls"] or 0) / calls, 2) if calls else 0.0,
        })
    return out


def recent(
    sink: EventSink, *, limit: int = 50
) -> list[dict[str, Any]]:
    sql = """
        SELECT ts, provider, modality, model, upstream_model,
               latency_ms, input_tokens, output_tokens, cost_usd,
               ok, cached, deduped, error_type, error
        FROM loom_events
        ORDER BY id DESC
        LIMIT ?
    """
    rows = sink.fetch(sql=sql, params=(int(limit),))
    return rows
