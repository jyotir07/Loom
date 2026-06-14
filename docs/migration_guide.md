# Migrating from direct vendor SDKs to Loom

Loom is designed for incremental adoption. You don't rewrite anything
to start using it — pick one call site, swap it, ship it, repeat.

This guide covers the common cases.

---

## Install

```bash
pip install loom[openai]      # or loom[all] for every supported vendor
```

Extras are optional dependency groups: `openai`, `anthropic`, `gemini`,
`tencent`, `yaml`, `all`. Loom itself has only `requests` and
`python-dotenv` as hard dependencies, so installing without an extra
gives you the catalog + dispatcher but no vendor SDK.

---

## OpenAI — sync text

**Before:**

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hi."}],
)
text = resp.choices[0].message.content
```

**After:**

```python
import loom

result = loom.generate(
    provider="openai",
    modality="text",
    model="gpt-4o-mini",
    prompt="Say hi.",
)
text = result["text"]
```

What you also get for free:

- `result["usage"]` — input/output tokens
- `result["cost"]` — USD + local currency
- An `INFO`-level log line with provider, model, latency, tokens, cost

---

## OpenAI — sync image

**Before:**

```python
from openai import OpenAI

client = OpenAI()
resp = client.images.generate(
    model="gpt-image-1",
    prompt="a red apple",
    quality="low",
)
b64 = resp.data[0].b64_json
```

**After:**

```python
import loom

result = loom.generate(
    provider="openai",
    modality="image",
    model="gpt-image-1-low",   # catalog sugar — sets quality=low for you
    prompt="a red apple",
)
b64 = result["images"][0]["data_b64"]
```

Catalog model IDs like `gpt-image-1-low` bake the `quality` param in,
so you don't have to. You can still pass `params={"size": "1024x1024"}`
to override or extend.

---

## Async

**Before (FastAPI):**

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

@app.get("/answer")
async def answer():
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "..."}],
    )
    return resp.choices[0].message.content
```

**After:**

```python
import loom

@app.get("/answer")
async def answer():
    result = await loom.agenerate(
        provider="openai",
        modality="text",
        model="gpt-4o-mini",
        prompt="...",
    )
    return result["text"]
```

For a long-lived client (skip recreating per-request):

```python
from loom import AsyncLoom

aclient = AsyncLoom.from_env()

@app.get("/answer")
async def answer():
    result = await aclient.generate(
        provider="openai",
        modality="text",
        model="gpt-4o-mini",
        prompt="...",
    )
    return result["text"]
```

---

## Configuration — environment vs programmatic

**Env-var style.** Vendor keys live in `.env` or the process
environment under the standard names (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, …). This is the default; `loom.generate(...)` and
`Loom.from_env()` both pick them up.

**Programmatic.** Pass them in directly when you build the client:

```python
from loom import Loom

client = Loom(
    api_keys={
        "OPENAI_API_KEY": secrets_manager.get("openai/prod"),
        "ANTHROPIC_API_KEY": secrets_manager.get("anthropic/prod"),
    },
)
```

`api_keys` wins over the process environment, so this is the right
hook for services that pull keys from Vault / Secrets Manager at boot.

---

## Custom catalogs

If your team maintains its own model list (different pricing, different
internal IDs, restricted to an approved subset), point Loom at a YAML
file:

```yaml
# models.yaml
openai:
  label: OpenAI
  modalities:
    text:
      - id: small
        name: Cheap default
        model: gpt-4o-mini
        input_inr_per_1m: 14.4578
        output_inr_per_1m: 57.8312
```

```python
from loom import Loom, Catalog

client = Loom(catalog=Catalog.from_yaml("models.yaml"))
client.generate(provider="openai", modality="text", model="small", prompt="hi")
```

Schema is the same one the bundled catalog uses — see
`loom/catalog/_data.py` for a working example.

---

## Error handling

Vendor SDKs each raise their own exception hierarchy. Loom unifies them:

```python
from loom import AuthError, RateLimitError, ProviderError, ModelNotFoundError

try:
    result = loom.generate(provider=..., modality=..., model=..., prompt=...)
except AuthError:
    # missing/invalid API key — config problem
    ...
except RateLimitError:
    # back off + retry, or fall back to another model
    ...
except ModelNotFoundError:
    # catalog doesn't know that (provider, modality, model) triple
    ...
except ProviderError:
    # anything else from the upstream call
    ...
```

---

## Turning on the optimization layer

Phase 3 primitives are off (cache) or on with safe defaults (retry, dedup).
The minimal "turn it on" pattern:

```python
from loom import Loom, InMemoryCache

client = Loom(
    cache=InMemoryCache(maxsize=10_000, ttl=3600),
    # retry and dedup already on by default
)
```

In a multi-process deployment (FastAPI behind a worker pool, Celery, etc.):

```python
from loom import Loom, RedisCache

client = Loom(
    cache=RedisCache(url="redis://internal-redis:6379/0", ttl=3600),
)
```

Per-call opt-outs:

```python
client.generate(..., use_cache=False)            # force a fresh upstream call
Loom(dedup=False)                                # don't coalesce concurrent calls
Loom(retry=None)                                 # don't retry on rate-limits
```

See `docs/api_reference.md` → "Optimization layer" for the full
flow + the list of items still pending in Phase 3 (Gemini context
caching, more batch adapters, observability dashboard, vault
integration).

### Prompt caching

OpenAI and DeepSeek cache long prompt prefixes automatically — Loom
surfaces the saving in `result["usage"]["cached_tokens"]` and discounts
the `result["cost"]` already. No code change.

Anthropic is opt-in. If you have a long, repeated system prompt
(few-shot examples, retrieval context, persona), turn on `cache_system`:

```python
loom.generate(
    provider="anthropic", modality="text", model="claude-haiku-4-5",
    prompt=user_question,
    params={
        "system": LONG_STATIC_SYSTEM_PROMPT,
        "cache_system": True,
    },
)
```

The first call writes the cache (small premium); calls within the cache
TTL pay ~10% of normal on the cached portion. Break-even is ~2 reads.

### Cheap-first routing

If most of your prompts are easy enough for a small model and only some
need the expensive one, declare a `Router` and let Loom escalate only
when needed:

```python
from loom import Loom, Router

router = Router(
    candidates=[
        ("openai", "text", "gpt-4o-mini"),     # try cheap first
        ("openai", "text", "gpt-4o"),          # escalate
    ],
    validator=lambda result: "I don't know" not in result["text"],
)

client = Loom.from_env()
result = client.route(router, prompt=user_question)
print(result["_router"]["used"])   # which model actually answered
```

The validator is your "is this answer good enough" hook. It runs
against the cheap model's response; if it returns False, Loom calls
the next candidate. Routing composes with the cache, so repeat hits
on the cheap candidate cost zero.

### Cross-vendor failover

If your service can't go down when OpenAI does (or when Anthropic does,
or when any one vendor flakes for ten minutes), use `Router.failover`:

```python
from loom import Loom, Router

router = Router.failover(
    provider="openai", modality="text", model="gpt-4o-mini",
)

client = Loom.from_env()
result = client.route(router, prompt=question)
```

Loom tries OpenAI first; if it raises (`AuthError`, `RateLimitError`,
any `ProviderError`), it falls through the bundled equivalence map —
by default through `claude-haiku-4-5`, `gemini-2.5-flash`,
`deepseek-v3`. The set is overridable with a custom `EquivalenceMap`.

You need API keys for every vendor in the chain (otherwise the
fallbacks raise `AuthError` and Loom moves on, which is fine — but
they'll never actually answer).

### Bulk / overnight jobs — use the Batch API

For workloads that can tolerate ~24h latency, OpenAI's batch endpoint
is ~50% cheaper than real-time. Bulk migrations, embedding backfills,
overnight analytics — all good candidates.

```python
from loom import Loom, BatchRequest

client = Loom.from_env()

# Submit and walk away.
handle = client.submit_batch([
    BatchRequest(provider="openai", modality="text",
                 model="gpt-4o-mini", prompt=text, custom_id=row_id)
    for row_id, text in rows
])
# Persist handle.id somewhere. Pick up later:
#   results = handle.wait()  # aligned to your input order

# Or block this process until done:
results = client.run_batch(requests, poll_interval=60.0)
```

Results align element-for-element to your submitted requests. Failed
rows appear as `{"kind": "error", "error": "...", "custom_id": "..."}`
in-place; the batch as a whole still completes.

---

## Cost logging

Every successful call returns a `cost` field:

```python
result["cost"]
# {"usd": 0.000028, "local": 0.0023, "local_currency": "INR"}
```

The local currency and conversion rate are configurable:

```python
Loom(local_currency="USD", local_to_usd=1.0)   # report only USD
Loom(local_currency="EUR", local_to_usd=1.08)  # 1 EUR ≈ 1.08 USD
```

Aggregating cost is a downstream concern — Loom logs each call, you
plug those logs into whatever you already use (Datadog, ELK, Postgres).

---

## When NOT to migrate (yet)

Phase 2 ships an OpenAI adapter for end-to-end use. Other providers
have catalog entries but no adapter registered yet; calling them
raises `ProviderError("provider 'X' is in the catalog but has no Loom
adapter yet")`. Migrate OpenAI call sites first; other vendors will
come online as their adapters land.

If you need a specific vendor before its adapter ships, the OpenAI-
compatible adapter pattern (`loom/providers/_openai_compatible.py`)
takes ~10 lines to wire up a new OpenAI-shaped vendor — open a PR.
