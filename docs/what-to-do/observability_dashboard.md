# Observability Dashboard

*How to build a real-time observability dashboard on top of Loom's call data.*

---

## The idea

Loom already emits one structured record per `generate()` call. That stream
contains everything a provider-health / cost / throughput dashboard needs —
provider, model, latency, token counts, cost, and the cached/deduped flags.
The dashboard does not require any new instrumentation in your call sites; it
only requires **capturing** those records into a store and **aggregating** them.

This is the Phase 3 *"Observability dashboard"* deliverable from the
[roadmap](../roadmap.md). This page documents the design.

A target layout looks like this:

```
┌───────────────────────────────────────────────────────────────────┐
│  REQUESTS / MIN     P95 LATENCY     CACHE HIT RATE     COST SAVED   │
│     12,847            312ms             61.4%            $1,284      │
├───────────────────────────────────────┬───────────────────────────┤
│  REQUESTS OVER TIME (throughput)       │  PROVIDER HEALTH           │
│  ╱╲    ╱╲   ╱╲╱╲                       │  ● OpenAI       370ms  ✓   │
│ ╱  ╲__╱  ╲_╱    ╲___                   │  ● Anthropic    280ms  ✓   │
│                                        │  ● xAI Grok     480ms  ⚠   │
│  TOKEN USAGE · BY PROVIDER             │  ...                       │
│  OpenAI    ████████████ 82%            ├───────────────────────────┤
│  Anthropic ████████ 64%                │  RECENT RETRIES · FAILOVER │
│  Gemini    █████ 47%                   │  retry openai · 429   2s   │
│  ...                                   │  failover openai→anthropic │
├───────────────────────────────────────┴───────────────────────────┤
│  LIVE REQUEST LOG · STRUCTURED INFO                    tailing 1.3s │
│  15:50:52  ok  openai  gpt-4o-mini   483.0ms  cached   $0.0001686   │
└───────────────────────────────────────────────────────────────────┘
```

---

## What you already have

`loom/_logging.py` → `log_call()` emits one record per call at `INFO` on the
`loom` logger, with the full structured payload attached as `record.loom`
(an `extra` dict). Every dashboard panel maps onto a field that is **already
being emitted**:

| Dashboard panel                     | Loom field(s) (already emitted)                       |
| ----------------------------------- | ----------------------------------------------------- |
| Requests / min, throughput chart    | count of records over a time window                   |
| P95 latency                         | `latency_ms`                                          |
| Cache hit rate                      | `cached` (bool)                                       |
| Cost saved / Token usage by provider | `cost_usd`, `input_tokens`, `output_tokens`, `provider` |
| Provider health (latency + ✓/⚠)     | `latency_ms` + `ok`, grouped by `provider`            |
| Recent retries / failover           | `loom.retry` logger + `_router` trace in results      |
| Live request log                    | the raw `log_call` stream                             |

The provider list (OpenAI, Anthropic, Gemini, xAI Grok, Mistral, DeepSeek,
MiniMax, Z.AI, …) is simply your registered providers. The existing Flask app
(`app.py`, port `3001`) is the natural place to host the dashboard routes.

The full per-call payload available on `record.loom`:

```python
{
    "provider": str, "modality": str, "model": str, "upstream_model": str,
    "latency_ms": float,
    "input_tokens": int | None, "output_tokens": int | None, "total_tokens": int | None,
    "cost_usd": float | None, "cost_local": float | None, "cost_currency": str | None,
    "ok": bool, "cached": bool, "deduped": bool,
    "error_type": str | None, "error": str | None,   # present only on failure
}
```

---

## The one gap: nothing persists the events

By design, Loom follows a *"no surprises"* rule — the library adds **no log
handlers** by default (see the docstring in `loom/_logging.py`). `log_call`
calls `logger.info(...)` and that's it; the record is discarded unless a
consumer attaches a handler.

To power a dashboard you must **capture** those records into a store and
**aggregate** them. Keep this optional and consumer-owned so the library never
forces a sink on anyone.

---

## Architecture — four layers

### 1. A sink (logging handler)

Attach a `logging.Handler` to the `loom` logger that reads `record.loom` and
writes a row. SQLite is enough for a demo or a single-node deployment;
Postgres (you already have `seed_db.py` wiring) or a time-series store for real
load.

Recommended home: a new optional module `loom/observability/` so it never
pulls extra deps into the core import path.

```python
# loom/observability/sink.py
import logging, sqlite3, time

class SQLiteSink(logging.Handler):
    """Persist every Loom call into SQLite for the dashboard.

    Wire it once at app startup:

        import logging
        from loom.observability.sink import SQLiteSink
        logging.getLogger("loom").addHandler(SQLiteSink())

    After that, every generate() call anywhere in the process is recorded —
    no per-call-site changes.
    """

    def __init__(self, path: str = "loom_events.db") -> None:
        super().__init__()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS events(
                ts REAL, provider TEXT, model TEXT, latency_ms REAL,
                input_tokens INT, output_tokens INT, cost_usd REAL,
                ok INT, cached INT, deduped INT, error_type TEXT)"""
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        self.db.commit()

    def emit(self, record: logging.LogRecord) -> None:
        d = getattr(record, "loom", None)
        if not d:
            return
        try:
            self.db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    time.time(), d["provider"], d["model"], d["latency_ms"],
                    d.get("input_tokens"), d.get("output_tokens"), d.get("cost_usd"),
                    int(d["ok"]), int(d["cached"]), int(d["deduped"]),
                    d.get("error_type"),
                ),
            )
            self.db.commit()
        except Exception:          # a logging handler must never raise
            self.handleError(record)
```

### 2. Aggregation queries

One function per panel. Examples (SQLite, last-N-seconds windows):

```python
# loom/observability/metrics.py — sketch
def requests_per_min(db, window=60):
    (n,) = db.execute(
        "SELECT COUNT(*) FROM events WHERE ts > ?", (time.time() - window,)
    ).fetchone()
    return n

def cache_hit_rate(db, window=86400):
    row = db.execute(
        "SELECT AVG(cached) FROM events WHERE ts > ?", (time.time() - window,)
    ).fetchone()
    return (row[0] or 0) * 100

def p95_latency(db, window=86400):
    rows = [r[0] for r in db.execute(
        "SELECT latency_ms FROM events WHERE ts > ? ORDER BY latency_ms",
        (time.time() - window,)).fetchall()]
    if not rows:
        return 0
    return rows[int(len(rows) * 0.95) - 1]

def provider_health(db, window=86400):
    return db.execute(
        """SELECT provider, AVG(latency_ms) AS lat, AVG(ok) AS ok_rate
           FROM events WHERE ts > ? GROUP BY provider ORDER BY lat""",
        (time.time() - window,)).fetchall()
```

- **Requests / min** → `COUNT(*) WHERE ts > now-60`
- **Cache hit rate** → `AVG(cached)`
- **P95 latency** → 95th percentile of `latency_ms`
- **Provider health** → `GROUP BY provider` on `AVG(latency_ms)` + `AVG(ok)`
  (map `ok_rate` to ✓ / ⚠ thresholds, e.g. `⚠` when avg latency is high or
  `ok_rate < 1.0`)
- **Token usage by provider** → `SUM(input_tokens + output_tokens) GROUP BY provider`,
  rendered as a share of the busiest provider
- **Throughput chart** → bucket counts by minute (`GROUP BY CAST(ts/60 AS INT)`)

### 3. JSON API endpoints

Add read-only routes to `app.py`, behind the existing login wall:

| Route                          | Returns                                            |
| ------------------------------ | -------------------------------------------------- |
| `GET /api/metrics/summary`     | the four top cards (req/min, p95, cache %, cost)   |
| `GET /api/metrics/providers`   | per-provider latency + health status               |
| `GET /api/metrics/timeseries`  | per-minute request counts for the throughput chart |
| `GET /api/metrics/tokens`      | token usage by provider                            |
| `GET /api/logs/tail?n=50`      | most recent N raw events for the live log          |

Each one just calls an aggregation function and `jsonify`s the result.

### 4. Frontend

A new Jinja template (e.g. `templates/dashboard.html`) plus CSS/JS that polls
the endpoints (summary/providers/tokens every ~2 s; log tail every ~1.3 s) and
renders:

- four metric cards
- a sparkline / area chart for throughput (Chart.js, or a hand-rolled SVG
  polyline to stay dependency-free)
- the provider-health list with status dots
- horizontal bars for token usage
- a tailing, monospaced request log

The dark / monospace aesthetic of the mockup is pure CSS — no special tooling.

---

## Two honest caveats

### "Cost saved" needs a baseline

Loom logs *actual* cost (`cost_usd`). **Saved** means
`cost_without_optimization − cost_with_optimization`. To populate that card
truthfully you must also record the **avoided** cost — for a `cached` or
`deduped` hit, the price that *would* have been paid upstream; for a router
downgrade, the delta between the expensive candidate and the one that actually
answered. That is a small addition to `log_call` (e.g. a `cost_saved_usd`
field) plus a column in the sink. Until then, treat "cost saved" as an estimate
derived from `cached`/`deduped` counts × average call cost, and label it as
such.

### Retries / failover aren't in `log_call` yet

The "Recent retries · failover" panel needs events that today live in the
`loom.retry` logger (`loom/_retry.py`) and the `_router` trace attached to
routed results (`loom/_router.py`). To feed that panel, emit structured records
from those modules into the **same sink** (e.g. a second table `retries(ts,
provider, reason, kind)` where `kind ∈ {retry, failover}`).

---

## Suggested build order

Each stage is independently runnable and testable:

1. **Sink + schema + aggregation functions** — testable on its own against
   seeded rows, no web layer required.
2. **Flask JSON endpoints** — verify with `curl` / browser.
3. **Dashboard template + CSS + JS** — the visual layer matching the mockup.

Optional follow-ups, in priority order:

4. Add `cost_saved_usd` to `log_call` + sink for a truthful "Cost saved" card.
5. Emit retry/failover events into the sink for that panel.
6. Swap the SQLite sink for Postgres (reuse `seed_db.py`) for multi-node
   deployments, or push to a time-series backend for long retention.

---

## Design principles to preserve

- **Library stays handler-free.** The sink is opt-in and lives under
  `loom/observability/`; importing `loom` must not start writing a database.
- **No per-call-site changes.** Capturing happens entirely through the logging
  handler, so existing `generate()` calls light up the dashboard for free.
- **Endpoints are read-only** and sit behind the app's existing auth.
