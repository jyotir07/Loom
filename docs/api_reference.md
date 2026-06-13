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
)
```

- `catalog` — `Catalog` instance. Defaults to the bundled in-memory catalog.
- `api_keys` — maps env-var name → key value, e.g.
  `{"OPENAI_API_KEY": "sk-..."}`. Wins over the process environment.
- `local_currency` — label used on `cost.local_currency`.
- `local_to_usd` — multiplier converting one unit of local currency
  to USD. At 1 USD ≈ 83 INR, the default is `1/83 ≈ 0.012`.

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

## Provider context (advanced)

`loom._context` exposes the per-call `LoomContext` via a `ContextVar`.
Provider modules read it through `loom.providers._common.require_env`
so they can be unaware of `api_keys` plumbing. End users normally don't
need to touch this.
