# Loom — API reference

This is the surface every consuming project will touch. Everything not
listed here is implementation detail and subject to change.

---

## Quick reference

| Path | What it is |
|------|-----------|
| `loom.generate(...)` | Sync convenience — runs on a default `Loom.from_env()` |
| `loom.agenerate(...)` | Async convenience — runs on a default `AsyncLoom.from_env()` |
| `loom.Loom` | The sync client class |
| `loom.AsyncLoom` | The async client class |
| `loom.Catalog` | The catalog of providers/modalities/models |
| `loom.TextResponse` / `loom.ImageResponse` | Response TypedDicts |
| `loom.LoomError` and subclasses | Error taxonomy |

---

## `loom.generate(...) -> dict`

```python
loom.generate(
    *,
    provider: str,     # catalog key, e.g. "openai"
    modality: str,     # "text" | "image"
    model: str,        # catalog model id, e.g. "gpt-4o-mini"
    prompt: str,
    params: dict | None = None,
) -> dict
```

Caller-supplied `params` are merged on top of any catalog defaults
(catalog defaults are overridden by caller values on key conflict).

Returns one of:

```python
# Text
{
    "kind": "text",
    "text": "...",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "upstream_model": "gpt-4o-mini",
    "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
    "cost": {"usd": 0.0000038, "local": 0.000316, "local_currency": "INR"},
}

# Image
{
    "kind": "image",
    "images": [{"mime_type": "image/png", "data_b64": "..."}],
    "provider": "openai",
    "model": "gpt-image-1-low",
    "upstream_model": "gpt-image-1",
    "cost": {"usd": 0.0128, "local": 1.0602, "local_currency": "INR"},
}
```

`usage` is only present when the provider reports tokens (text). `cost`
is only present when the catalog has pricing for the model.

---

## `loom.agenerate(...)`

Identical signature, returns a coroutine. Inside FastAPI / Celery /
Lambda, `await loom.agenerate(...)`.

---

## `loom.Loom` — sync client

```python
client = Loom(
    *,
    catalog: Catalog | None = None,
    api_keys: dict[str, str] | None = None,
    local_currency: str = "INR",
    local_to_usd: float = 1/83,
    retry: RetryPolicy | None = RetryPolicy(),  # set to None to disable
    cache: CacheBackend | None = None,           # off by default
    dedup: bool = True,
)
```

- `catalog` — `Catalog` instance. Defaults to the bundled in-memory catalog.
- `api_keys` — maps env-var name → key value, e.g.
  `{"OPENAI_API_KEY": "sk-..."}`. Wins over the process environment.
- `local_currency` — label used on `cost.local_currency`.
- `local_to_usd` — multiplier converting one unit of local currency
  to USD. At 1 USD ≈ 83 INR, the default is `1/83 ≈ 0.012`.
- `retry` — `RetryPolicy` instance; default is `RetryPolicy()`. Pass
  `None` to disable retries entirely. See "Optimization layer" below.
- `cache` — `CacheBackend` (e.g. `InMemoryCache()` or `RedisCache()`);
  cache is OFF unless explicitly passed in.
- `dedup` — single-flight on identical concurrent calls. On by default.

```python
Loom.from_env(
    *,
    dotenv_path: str | None = None,
    catalog: Catalog | None = None,
    api_keys: dict[str, str] | None = None,
    local_currency: str = "INR",
    local_to_usd: float = 1/83,
) -> Loom
```

Loads `.env` (the file at `dotenv_path` if given, else `./.env` if it
exists) — already-set environment variables are not overridden — and
returns a `Loom`. Use this when keys live in `.env`/the environment.

```python
client.generate(
    *, provider, modality, model, prompt, params=None
) -> dict
```

Same shape as `loom.generate(...)` above.

---

## `loom.AsyncLoom` — async client

Subclass of `Loom` with the same constructor and `from_env()`
classmethod. `generate(...)` is a coroutine.

The dispatcher prefers a provider's native `agenerate(...)` if it has
one, and falls back to running the sync `generate(...)` in a thread via
`asyncio.to_thread` for providers without native async support.

---

## `loom.Catalog` — model catalog

```python
Catalog(
    data: dict | None = None,
    *,
    backend: CatalogBackend | None = None,
)
```

`data` is an in-memory dict in Loom's schema. `backend` is anything
with a `.load() -> dict` method. With neither, the bundled catalog
is used.

Convenience constructors:

```python
Catalog.from_yaml("models.yaml")    # YamlBackend
Catalog.from_mapping(my_dict)       # MemoryBackend
```

Methods:

```python
c.providers() -> list[str]
c.modalities(provider) -> list[str]
c.models(provider, modality) -> list[dict]
c.resolve(provider, modality, model_id) -> (upstream_model, params)
```

`resolve` raises `loom.ModelNotFoundError` if the triple isn't present.

### Pluggable backends

`loom.catalog.backends` ships:

- `MemoryBackend(data)` — wraps an in-memory dict.
- `YamlBackend(path)` — reads a YAML file. Needs `pip install loom[yaml]`.

Postgres backend lands when an internal project asks for it; the
`CatalogBackend` protocol is intentionally tiny so it'll be a small
addition.

---

## Response shapes (`loom.types`)

These are `TypedDict`s — runtime-equivalent to dicts, but they give
IDE autocomplete and mypy/pyright coverage.

```python
class Usage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class Cost(TypedDict, total=False):
    usd: float
    local: float
    local_currency: str

class ImagePayload(TypedDict):
    mime_type: str
    data_b64: str

class TextResponse(TypedDict, total=False):
    kind: Literal["text"]
    text: str
    provider: str
    model: str
    upstream_model: str
    usage: Usage
    cost: Cost

class ImageResponse(TypedDict, total=False):
    kind: Literal["image"]
    images: list[ImagePayload]
    provider: str
    model: str
    upstream_model: str
    usage: Usage
    cost: Cost
```

---

## Error taxonomy

```python
loom.LoomError              # base for everything Loom raises
├── loom.ProviderError      # provider-side problem
│   ├── loom.AuthError      # missing/invalid API key
│   └── loom.RateLimitError # provider rate-limited the request
└── loom.ModelNotFoundError # catalog doesn't know that triple
```

Idiomatic usage:

```python
from loom import generate, AuthError, RateLimitError, ProviderError

try:
    result = generate(provider=..., modality=..., model=..., prompt=...)
except AuthError:
    # No key — surface a config error to your caller
    ...
except RateLimitError:
    # Back off and retry, or fall back to another provider
    ...
except ProviderError:
    # Anything else from the upstream call
    ...
```

---

## Logging

Loom emits one log line per call on the `loom` logger.

- Successful calls log at `INFO`.
- Failed calls log at `WARNING`.

Every record has a `loom` field on its `__dict__` (use
`record.__dict__["loom"]`) with the full structured payload:

```python
{
    "provider": "openai",
    "modality": "text",
    "model": "gpt-4o-mini",
    "upstream_model": "gpt-4o-mini",
    "latency_ms": 312.4,
    "input_tokens": 12,
    "output_tokens": 8,
    "total_tokens": 20,
    "cost_usd": 0.0000038,
    "cost_local": 0.000316,
    "cost_currency": "INR",
    "ok": True,
}
```

Loom does not configure handlers itself. Wire it up like any other
stdlib logger:

```python
import logging
logging.basicConfig(level=logging.INFO)
# or, for JSON output, route the "loom" logger to your JSON handler.
```

---

## Optimization layer (Phase 3)

Three primitives ship together and can be combined freely.

### Retry

```python
from loom import Loom, RetryPolicy

client = Loom(
    retry=RetryPolicy(
        max_attempts=3,        # total attempts incl. the first
        base_delay=0.5,        # seconds; doubled each attempt
        max_delay=8.0,         # ceiling for the backoff
        jitter=0.25,           # ± fraction of the computed delay
    ),
)
```

Default policy retries `RateLimitError` and transient network errors
(timeouts, `ConnectionError`, OpenAI/Anthropic SDK `APIConnectionError`
/ `APITimeoutError`). Never retries `AuthError` or `ModelNotFoundError`.
Pass `retry=None` to disable.

### Response cache

```python
from loom import Loom, InMemoryCache, RedisCache

# in-process LRU + TTL
client = Loom(cache=InMemoryCache(maxsize=10_000, ttl=3600))

# shared across processes
client = Loom(cache=RedisCache(url="redis://prod-redis:6379/0", ttl=3600))
```

Cache key is `sha256(canonical(provider, modality, model, prompt, params))` —
param ordering is normalized so dict-key order doesn't poison the key.

Per-call opt-out:

```python
client.generate(..., use_cache=False)
```

Cached responses keep their original `cost` and `usage` fields so
spend reporting can distinguish billed calls (no `cached` log flag)
from served-from-cache calls (`cached=true` on the log line).

`RedisCache` failures (connection drops, serialization issues) degrade
to "miss / no-op" with a `loom.cache` warning log, so a Redis outage
doesn't take down request handling.

### Request deduplication

On by default. When N callers issue the same `(provider, modality,
model, prompt, params)` concurrently, only the first hits the upstream
API — the rest wait on the in-flight slot and receive the same result
(or the same exception). Log lines on the deduped callers carry
`deduped=true`.

Disable with `Loom(dedup=False)` when you specifically want N
independent samples for the same prompt.

Sync and async dedup registries are separate — a sync caller and an
async caller racing the same prompt do NOT coalesce.

### Order of operations

For each `generate(...)` call:

1. Compute call key.
2. **Cache check** — if hit, return immediately (`cached=True` on log).
3. **Dedup slot** — claim it, or wait on the existing owner
   (`deduped=True` on log for waiters).
4. **Retry-wrapped provider call** — exponential backoff on retryable errors.
5. On success: enrich, **fill cache**, notify any waiters, log INFO.
6. On failure: notify waiters with the error, log WARNING, re-raise.

### Vendor-native prompt caching

Repeated system prompts and few-shot prefixes can be cached on the
vendor's side at a steep discount (50% off on OpenAI, 90% off on
Anthropic / DeepSeek cache reads). Loom surfaces cached-token telemetry
and applies the vendor discount in `cost` automatically.

**Automatic** — OpenAI and DeepSeek cache eligible prompt prefixes
without any opt-in. Loom reads the vendor's `cached_tokens` field and
discounts cost accordingly. You'll see it on responses with no code change:

```python
result = loom.generate(
    provider="openai", modality="text", model="gpt-4o-mini",
    prompt=very_long_repeated_prompt,
)
result["usage"]["cached_tokens"]   # how many input tokens hit the cache
result["cost"]["usd"]              # already discounted for cached tokens
```

**Explicit (Anthropic)** — caller marks which prompt segments are
cacheable. Two convenience knobs:

```python
result = loom.generate(
    provider="anthropic", modality="text", model="claude-haiku-4-5",
    prompt="<the small, varying part>",
    params={
        "system": "<the long static system prompt>",
        "cache_system": True,        # wrap `system` in cache_control
        # "cache_user": True,        # wrap the user message too
    },
)
result["usage"]["cached_tokens"]            # 0 on cache write, >0 on subsequent calls
result["usage"]["cache_creation_tokens"]    # >0 on the first call that creates the cache
```

For finer control (multi-block prompts, partial caching, etc.) pass
`system` as a list of Anthropic blocks directly — Loom forwards it
verbatim:

```python
params = {
    "system": [
        {"type": "text", "text": "...static...",
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "...dynamic..."},
    ],
}
```

**Pricing notes** — `cost` reflects each token bucket at its true rate:

| Provider  | cached_tokens rate | cache_creation_tokens rate |
|-----------|--------------------|-----------------------------|
| OpenAI    | 50% of input rate  | n/a (writes are free)       |
| Anthropic | 10% of input rate  | 125% of input rate          |
| DeepSeek  | 10% of input rate  | n/a (writes are free)       |
| Gemini    | 25% of input rate  | n/a (via CachedContent)     |

For Anthropic, the first call to a prompt charges `cache_creation_tokens`
at 1.25× — but subsequent calls within the cache TTL pay 0.1× on the
cached portion. Break-even is hit at ~2 reads.

**Gemini context caching** is a separate surface (see below) because
its cache is a standalone *resource* with its own lifecycle, not a
header on a single call.

### Gemini context caching

For long, repeated prompt prefixes (50-page policy docs, retrieval
contexts, persona + few-shot bundles), Gemini lets you upload the
content once as a `CachedContent` resource and reference it by ID on
subsequent calls. The cached portion of input tokens is billed at 25%
of the normal rate.

```python
from loom import Loom

client = Loom.from_env()

cache = client.create_context_cache(
    provider="gemini",
    model="gemini-2.5-flash",
    contents=long_static_document,       # str (wrapped as a user-role
                                         # text part) or list of Gemini
                                         # Content blocks
    system_instruction="You are a policy assistant.",
    ttl_seconds=600,
    display_name="policy-doc-v3",
)

# Reference the cache on subsequent calls:
result = client.generate(
    provider="gemini", modality="text", model="gemini-2.5-flash",
    prompt="Does clause 4.2 apply to subcontractors?",
    params={"cached_content": cache.id},
)
result["usage"]["cached_tokens"]   # how many input tokens hit the cache
result["cost"]["usd"]              # already discounted at 25%

client.delete_context_cache(cache)  # or cache.delete()
```

`ContextCacheHandle`:

```python
cache.id               # vendor resource name (e.g. "cachedContents/abc")
cache.provider         # "gemini"
cache.model            # the model this cache is keyed to
cache.display_name     # optional human label
cache.ttl_seconds      # what was requested at create time
cache.delete()         # best-effort delete of the vendor resource
cache.refresh()        # re-fetch raw vendor metadata (expire_time, etc.)
```

The cache is **model-scoped** — a `CachedContent` created for
`gemini-2.5-flash` can only be referenced by calls to that same model.
Loom doesn't enforce this; the vendor will reject mismatches.

Only Gemini has a registered context-cache adapter in this chunk.
Other providers raise `ProviderError("no Loom context-cache adapter
yet")`. Anthropic and OpenAI use the in-call header pattern (above)
and don't ship a standalone cache resource API.

### Batch API

For workloads that can wait (offline jobs, overnight analytics,
bulk migrations), vendor batch endpoints typically cost ~50% less
than real-time calls with a ~24h SLA.

```python
from loom import Loom, BatchRequest

client = Loom.from_env()

handle = client.submit_batch([
    BatchRequest(provider="openai", modality="text",
                 model="gpt-4o-mini", prompt="summarize row 1",
                 custom_id="row-1"),
    BatchRequest(provider="openai", modality="text",
                 model="gpt-4o-mini", prompt="summarize row 2",
                 custom_id="row-2"),
])

print(handle.id, handle.status())

# Block until done (default 24h cap, 30s poll cadence).
results = handle.wait(poll_interval=60.0, timeout=24 * 3600)

# results is a list aligned to your original BatchRequest order.
# Each item is either a normal {"kind": "text", "text": "..."} response
# or {"kind": "error", "error": "...", "custom_id": "..."} for that
# single failed row.
```

One-shot:

```python
results = client.run_batch([req1, req2, req3])
```

`BatchHandle` API:

```python
handle.id            # vendor-side batch id
handle.provider      # "openai" etc.
handle.requests      # original BatchRequest list (in caller order)
handle.status()      # str — vendor's current status
handle.is_ready()    # True iff status is terminal
handle.wait(...)     # blocks; returns aligned results on success
handle.results()     # fetch (errors if status != "completed")
handle.cancel()      # best-effort cancel
```

Constraints:

- **One provider per batch.** Cross-vendor batching is N vendor-side
  jobs and Loom doesn't hide that — file N batches.
- **One modality per batch.** OpenAI's batch endpoint is per-URL
  (`/v1/chat/completions` xor `/v1/images/generations`); mixing text +
  image in one submission is rejected at `submit_batch` time.
- **custom_id collisions are rejected** at submit time. If you don't
  supply one, Loom generates `loom-<uuid>`.

**Registered batch adapters: OpenAI, Anthropic.** Gemini follows the
same protocol and registers in `loom/batch_providers/__init__.py`
when added.

Anthropic-specific notes:

- Text only (Anthropic doesn't expose image generation). Image
  modality is rejected at `submit_batch` time.
- Anthropic's per-request body shape (`model`, `max_tokens`,
  `messages`, `system`) is built by reusing the live adapter's
  `_build_kwargs`, so the same Loom-side knobs work in batch as
  real-time — including `cache_system` / `cache_user` for prompt
  caching across batched rows.
- Loom normalizes Anthropic's `processing_status` of `"ended"` to the
  uniform `"completed"` status. Per-row `errored` / `canceled` /
  `expired` outcomes surface as `{"kind": "error", "code": ...}`
  entries in `results()`, matching how OpenAI partial failures are
  reported.

### Smart model routing

Cheap-first / escalate-on-failure as a single primitive. Declare an
ordered list of candidates (cheapest first) and an optional
`validator`. Loom tries them in order; the first response that passes
the validator wins.

```python
from loom import Loom, Router, Candidate

router = Router(
    candidates=[
        ("openai", "text", "gpt-4o-mini"),                       # tuple shorthand
        Candidate("anthropic", "text", "claude-haiku-4-5"),
        ("openai", "text", "gpt-4o", {"temperature": 0.2}),      # tuple + params
    ],
    validator=lambda result: len(result["text"]) > 40,
)

client = Loom.from_env()
result = client.route(router, prompt="Explain quantum entanglement.")

result["text"]                  # whichever candidate won
result["_router"]["used"]       # "openai:text:gpt-4o-mini"
result["_router"]["tried"]      # list of every candidate attempted
result["_router"]["passed"]     # True iff the validator accepted
```

Per-candidate `params` are merged on top of the `params` passed to
`route()` — candidate params win on conflict. That's how you bake
quality knobs (temperature bumps, longer max_tokens) into the
escalation tier without rewriting them on each call.

Failure semantics:

- A candidate that raises `LoomError` (any subclass — `AuthError`,
  `RateLimitError`, `ProviderError`, `ModelNotFoundError`) is recorded
  and skipped. Loom tries the next candidate.
- Non-Loom exceptions propagate immediately — those are programmer
  errors, not vendor flakiness.
- If every candidate raises, the **last** exception is re-raised.
- If candidates succeed but the validator rejects all of them, the
  **last** successful response is returned with
  `result["_router"]["passed"] = False`. The caller still has an
  answer; they decide whether to use it.

Async surface is identical:

```python
result = await aclient.route(router, prompt="…")
```

Routing composes with the rest of the optimization layer — each
candidate call goes through the normal `generate()` path (cache,
dedup, retry). Cache hits on the cheap candidate short-circuit the
chain at zero cost.

### Cross-vendor failover

The same Router primitive doubles as failover: declare a starting model
and let Loom fall through cross-vendor equivalents if the primary
errors. Loom ships a small opinionated `EquivalenceMap` keyed by tier
(`text/nano`, `text/cheap`, `text/standard`, `text/frontier`); each
tier groups the models from different vendors that can stand in for
each other.

```python
from loom import Loom, Router

# gpt-4o-mini, falling back through Anthropic / Gemini / DeepSeek if
# OpenAI is down or rate-limiting.
router = Router.failover(
    provider="openai", modality="text", model="gpt-4o-mini",
)

client = Loom.from_env()
result = client.route(router, prompt=user_question)
print(result["_router"]["used"])    # which vendor actually answered
```

Custom equivalence map (your shop's own opinion about who's equivalent
to whom):

```python
from loom import EquivalenceMap, Router

my_map = EquivalenceMap({
    "text/cheap": [
        ("openai", "text", "gpt-4o-mini"),
        ("deepseek", "text", "deepseek-v3"),
    ],
})
router = Router.failover(
    provider="openai", modality="text", model="gpt-4o-mini",
    equivalence=my_map,
)
```

`Router.failover(...)` also accepts:

- `validator=fn` — same hook as `Router(...)`. Use it to layer a quality
  check on top of failover (vendor fell over *or* the answer was bad).
- `extra_candidates=[...]` — appended after the cross-vendor equivalents.
  Useful for "and if everything else fails, escalate to the expensive
  model" trailing fallbacks.

If the starting model isn't in any tier of the equivalence map,
`Router.failover(...)` returns a one-candidate Router — equivalent to a
plain `client.generate(...)` call but still composes with retry, cache,
and dedup through `client.route(...)`.

`Router.failover` is sugar over `Router`. Under the hood the failover
router is a regular Router with the candidates pre-populated from the
equivalence map; everything documented under "Smart model routing"
above (result trace, validator rules, async surface) applies verbatim.

### What's still pending in Phase 3

The roadmap items not yet implemented in this branch:

- **Batch API: Gemini** (Vertex AI batch prediction; uses GCS for I/O,
  so it's bigger work than the OpenAI/Anthropic pattern)
- **Observability dashboard** (per-project / per-model cost reporting UI)
- **Centralized key vault integration** (AWS / GCP / Vault backends for `api_keys`)
- **Public docs site** and **semver stability commitment** (release-time concerns)

These all land independently on top of the primitives above.

---

## Provider context (advanced)

`loom._context` exposes the per-call `LoomContext` via a `ContextVar`.
Provider modules read it through `loom.providers._common.require_env`
so they can be unaware of `api_keys` plumbing. End users normally don't
need to touch this.
