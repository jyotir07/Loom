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
