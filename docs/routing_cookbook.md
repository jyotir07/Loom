# Loom v2 — routing cookbook

v2 folds intelligent routing into the one call you already use. The guiding
idea is unchanged from day one:

> Applications should not care which LLM provider they are talking to.

Everything below is **additive**. The explicit form still works:

```python
client.generate(provider="openai", modality="text", model="gpt-4o-mini",
                prompt="Say hi.")
```

The new parameters (`providers=`, `router=`, `fallback=`, `schema=`,
`tags=`) are optional and mutually-exclusive with `provider=`/`model=`.
Omit them and behavior is exactly 1.x.

---

## 1. Let Loom pick the model

Give it a prompt and nothing else. Loom ranks every task-capable model in
the catalog with the default `balanced` strategy (quality vs cost vs
latency) and calls the winner.

```python
client.generate(prompt="Summarize this contract in three bullets.")
```

`modality` defaults to `"text"`; pass `modality="image"` to auto-select an
image model instead.

---

## 2. Named strategies

When you have an opinion about the trade-off but not the model:

```python
client.generate(router="cheapest", prompt=...)          # lowest price
client.generate(router="fastest", prompt=...)           # lowest latency
client.generate(router="highest_quality", prompt=...)   # best tier
client.generate(router="balanced", prompt=...)          # the default blend
```

Or with the enum, if you prefer symbols over strings:

```python
from loom import RoutingStrategy
client.generate(router=RoutingStrategy.CHEAPEST, prompt=...)
```

The strategies read optional catalog metadata — `quality_tier`,
`latency_class`, `context_window`, `capabilities` — blended with live
signals from health/observability once traffic exists. A sparsely-seeded
catalog still produces a stable order (unknown price = most expensive,
unknown latency = slowest, unknown quality = lowest).

---

## 3. Provider preference order

When you want *these* providers, in *this* order, best model each:

```python
client.generate(providers=["gemini", "openai", "anthropic"], prompt=...)
```

Loom picks each provider's best model and tries them in order, skipping any
whose circuit is currently open (see health, below). Combine with a
strategy to control *which* model per provider:

```python
client.generate(providers=["gemini", "openai"], router="cheapest", prompt=...)
```

---

## 4. Automatic fallback

`fallback=` walks a provider chain when a call fails with a *retryable*
error (rate limit, timeout, 5xx, connection). Each attempt still runs under
the client's `RetryPolicy`; non-retryable errors (auth, bad model) bubble
immediately.

```python
from loom import FallbackPolicy

client.generate(
    prompt=...,
    router="balanced",
    fallback=FallbackPolicy(retries=3, providers=["gemini", "openai", "anthropic"]),
)
```

`FallbackPolicy(providers=[...])` sets the chain explicitly; omit it and the
chain is built from the whole catalog ranked by the strategy. The result
carries a `_router` trace (`used`, `tried`, `passed`).

`Router` / `Candidate` / `client.route(...)` from 1.x are unchanged — use
them when you want a hand-built escalation list with a custom validator.

---

## 5. Health monitoring

Every client tracks provider health by default — EWMA latency, rolling
failure counts, rate-limit cooldown, and a circuit breaker. Routing
consumes it automatically: open-circuit providers are skipped and
recovering (half-open) ones deprioritized. If *every* candidate is
unhealthy, Loom uses the full pool anyway — a degraded provider beats no
provider.

```python
client.health.status("openai")   # ProviderHealth: latency, failures, state...
client.health.state("openai")    # CircuitState.CLOSED / OPEN / HALF_OPEN
client.health.snapshot()         # every tracked provider
```

Disable it with `Loom(health=None)`.

---

## 6. Load balancing

Spread the fully-automatic path across a pool instead of always hitting the
single best model:

```python
from loom import LoadBalancer

client = Loom.from_env(
    balancer=LoadBalancer(strategy="weighted",
                          weights={"openai": 40, "gemini": 35, "anthropic": 25}),
)
client.generate(prompt=...)   # provider chosen by the balancer, model by strategy
```

Strategies: `round_robin`, `weighted`, `least_latency`, `least_failures`.
The balancer consumes the same `HealthRegistry`, so open-circuit providers
are skipped (with the same no-strand fallback). It only affects the
fully-automatic `generate(prompt=...)` path; explicit / `providers=` /
`router=` / `fallback=` calls are untouched.

---

## 7. Benchmarking providers

Run one prompt across several providers at once and compare:

```python
report = client.compare(providers=["openai", "anthropic", "gemini"], prompt=...)
for row in report:
    print(row.provider, row.model, row.latency_ms, row.tokens, row.cost_usd)

print("cheapest:", report.summary.cheapest.provider)
print("fastest:", report.summary.fastest.provider)
```

Candidates run concurrently (threads for sync, `asyncio.gather` for async).
Each entry may be a provider name, a `(provider, model)` pair, or a
`Candidate`. A provider that fails becomes a row with `ok=False` and an
`error` string — the rest of the comparison still returns. The cache is
bypassed so latency reflects a real call. `await client.compare(...)` on
`AsyncLoom`.

---

## 8. Structured outputs

Get a validated object instead of a dict, provider-agnostic:

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

user = client.generate(prompt="Extract the user from: ...", schema=User)
assert isinstance(user, User)
```

Pydantic is an optional dependency — `pip install loom[structured]`. Passing
`schema=` without it raises a clear `StructuredOutputError`, as does a reply
that fails validation.

Under the hood, native modes are used where available — OpenAI
`response_format`, Anthropic tool-based JSON, Gemini `response_schema` — and
every other provider falls back to prompt-driven JSON plus the same
validation. The return type is identical across all of them.

---

## 9. Analytics

Every client records call metrics to a zero-config in-memory sink. No wiring
needed:

```python
a = client.analytics()
a.summary()                 # calls, cost, latency, tokens, retries, hit rates
a.summary(window="24h")     # 1h / 24h / 7d / 30d / all, or seconds, or None
a.by_provider()             # per-provider rollup
a.by_model()                # per-model rollup
a.recent(limit=20)          # newest calls first
```

Tag calls to slice usage later:

```python
client.generate(prompt=..., tags={"feature": "chat", "tenant": "acme"})
```

Recording goes straight to the client's own sink — the global `loom` logger
is untouched, so any handler/dashboard you wired in 1.x keeps working.
`Loom(analytics=False)` opts out, or pass a custom `EventSink` via
`analytics=my_sink`. For a persistent, queryable store plus the Flask
dashboard, keep using `SQLiteSink` + `LoomLogHandler` as in the migration
guide.

---

## Cheat sheet

| You want… | Call |
|---|---|
| A specific model | `generate(provider=, model=, prompt=)` |
| Loom to choose | `generate(prompt=)` |
| Cheapest / fastest / best | `generate(router="cheapest" \| "fastest" \| "highest_quality")` |
| Preferred providers, in order | `generate(providers=[...], prompt=)` |
| Survive an outage | `generate(fallback=FallbackPolicy(retries=3), prompt=)` |
| A typed object | `generate(schema=Model, prompt=)` |
| Compare providers | `compare(providers=[...], prompt=)` |
| Spread the load | `Loom(balancer=LoadBalancer(...))` |
| See usage | `client.analytics().summary()` |
