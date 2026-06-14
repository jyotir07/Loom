# Stability commitment

Starting at **v1.0.0**, Loom follows [semantic versioning](https://semver.org).
This page is the precise definition of what that promise covers and what
it doesn't.

---

## The promise

Within the 1.x line:

- The **public API** (defined below) will not break.
- Adding new functions, classes, methods, or parameters with safe
  defaults is a minor-version bump.
- Bug fixes that don't change documented behavior are a patch bump.

Breaking changes get a major-version bump (v2.0.0). That bump is
preceded by at least one minor-version release marking the affected
surface with `DeprecationWarning`.

---

## Public API

These are the symbols you can pin against. Importing them from `loom`
(top-level) is the stable path; importing from internal `loom._*`
modules is not covered by this commitment.

### Core surface

| Symbol                    | What it is                                   |
|---------------------------|-----------------------------------------------|
| `loom.generate(...)`      | Module-level sync convenience                 |
| `loom.agenerate(...)`     | Module-level async convenience                |
| `loom.Loom`               | Sync client class                             |
| `loom.AsyncLoom`          | Async client class                            |
| `loom.Catalog`            | Model catalog                                 |
| `loom.RetryPolicy`        | Retry config                                  |
| `loom.CacheBackend`       | Cache Protocol                                |
| `loom.InMemoryCache`      | Bundled in-process cache                      |
| `loom.RedisCache`         | Bundled Redis-backed cache                    |
| `loom.Router`             | Smart routing primitive                       |
| `loom.Candidate`          | Router candidate                              |
| `loom.EquivalenceMap`     | Cross-vendor equivalence map                  |
| `loom.BatchRequest`       | Batch input                                   |
| `loom.BatchHandle`        | Batch handle (status / wait / results / cancel) |
| `loom.ContextCacheHandle` | Gemini-style context cache handle             |

### Vault backends

| Symbol                          |
|----------------------------------|
| `loom.KeyVault` (Protocol)       |
| `loom.InMemoryVault`             |
| `loom.AWSSecretsManagerVault`    |
| `loom.GCPSecretManagerVault`     |
| `loom.HashiCorpVaultBackend`     |

### Response types

| Symbol                  |
|-------------------------|
| `loom.TextResponse`     |
| `loom.ImageResponse`    |
| `loom.ImagePayload`     |
| `loom.Usage`            |
| `loom.Cost`             |

### Errors

| Symbol                       |
|-------------------------------|
| `loom.LoomError`              |
| `loom.ProviderError`          |
| `loom.AuthError`              |
| `loom.RateLimitError`         |
| `loom.ModelNotFoundError`     |

### Observability

| Symbol                                  |
|------------------------------------------|
| `loom.observability.EventSink` (Protocol) |
| `loom.observability.SQLiteSink`           |
| `loom.observability.LoomLogHandler`       |
| `loom.observability.make_dashboard`       |

### Response shapes

The dict returned by `loom.generate(...)` is part of the contract:

```python
{
    "kind": "text" | "image" | "video",
    "text": str,                  # if kind == "text"
    "images": [ImagePayload],     # if kind == "image"
    "provider": str,
    "model": str,
    "upstream_model": str,
    "usage": Usage | absent,
    "cost": Cost | absent,
    "custom_id": str | absent,    # batch results only
    "_router": dict | absent,     # set by client.route(...)
}
```

Adding new optional keys to this dict is **not** a breaking change.
Removing or renaming an existing key is.

### Logger fields

The `loom` logger emits records with a `loom` attribute carrying the
fields documented in `docs/api_reference.md` → "Logging". The set of
documented field names is part of the contract; new fields may be
added, existing ones won't be renamed within a major.

---

## What's NOT covered

- **Modules and functions prefixed with `_`** (`loom._loom`,
  `loom._cache`, `loom._router`, etc.) are internal. Their layout and
  behavior may change at any time. Import from `loom` instead.
- **Catalog contents.** Model IDs, prices, and per-model default
  params evolve as vendors release / deprecate / re-price. The
  catalog *shape* is stable; the *contents* track reality.
- **Provider modules under `loom.providers.*`.** The dispatch contract
  (`generate(modality, model, params, prompt) -> dict`) is stable;
  the individual module names are not. Add new ones via the
  `_LAZY` registry, don't import them directly.
- **Per-vendor pass-through params.** The `params={...}` dict is
  forwarded to the upstream SDK after a small set of Loom-side knobs
  (`cache_system`, `cache_user`, `cached_content`, `system`, etc.)
  is consumed. Vendor SDK breakages flow through; that's the
  trade-off for native-SDK fidelity.
- **Bundled `EquivalenceMap` tier contents.** The map *exists* in
  every 1.x; which models populate which tiers reflects the catalog
  and may shift between minor releases as vendors ship and deprecate.
- **Pre-release version of any backend.** A backend documented as
  "experimental" in `api_reference.md` is not covered until it loses
  that label.

---

## Deprecation policy

When a public symbol or behavior needs to change:

1. The new shape lands in a minor release. The old shape continues
   to work and emits `DeprecationWarning` with a pointer to the
   replacement.
2. The next major release (≥ 6 months later) removes the old shape.
3. `CHANGELOG.md` records both events.

Security fixes can compress this timeline. They'll be flagged as such
in the changelog.

---

## How to pin

Recommended pin in `pyproject.toml`:

```toml
dependencies = [
    "loom>=1.0,<2.0",
]
```

If you depend on a feature added after 1.0.0, pin the minor:

```toml
dependencies = [
    "loom>=1.4,<2.0",
]
```

Don't pin to an exact patch unless you're chasing a specific bug
fix — that prevents you from taking future patches in the same line.
