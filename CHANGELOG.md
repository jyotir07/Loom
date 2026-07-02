# Changelog

All notable changes to Loom. Versions follow [semantic versioning](https://semver.org).

## [2.0.0] — 2026-07-02

**Loom becomes an intelligent routing layer.** Applications stop encoding
which provider/model to call — they state intent, and Loom decides. Every
change is **additive and backward-compatible**: the explicit
`generate(provider=, modality=, model=)` path behaves exactly as in 1.x,
and no public symbol was removed. The major bump reflects the size of the
new surface, not a break. See `docs/routing_cookbook.md` for the full tour
and the "Migrating to v2" section of `docs/migration_guide.md`.

### Added

#### Intelligent routing in `generate()`
- `generate(providers=[...])` — try providers in preference order, best
  model each, with automatic health-aware reordering.
- `generate(router="cheapest" | "fastest" | "highest_quality" | "balanced")`
  — named strategies (also `RoutingStrategy` enum).
- `generate(prompt=...)` alone — fully automatic provider + model
  selection (default `balanced` strategy, modality inferred, default text).
- `RoutingStrategy`, `StrategySelector`, and a `RoutingSignals` layer that
  blends static catalog metadata with live runtime signals.
- Optional catalog metadata: `context_window`, `quality_tier`,
  `latency_class`, `capabilities`, read via `Catalog.metadata(...)`.

#### Automatic fallback
- `FallbackPolicy(retries=, providers=)` + `generate(fallback=...)` — walk a
  provider chain on retryable failures, each attempt under the client's
  `RetryPolicy`, tagged with a `_router` trace.

#### Health monitoring
- `HealthRegistry` — per-provider EWMA latency, rolling failure counts,
  rate-limit cooldown, and a circuit breaker (`CircuitState`:
  closed / open / half-open). On by default; `Loom(health=None)` disables.
- Routing consumes it: open-circuit providers are skipped and recovering
  ones deprioritized — with a no-strand fallback (a degraded provider beats
  no provider). `client.health` exposes `.status()` / `.state()` / `.snapshot()`.

#### Load balancing
- `LoadBalancer(strategy=, providers=, weights=)` with `round_robin`,
  `weighted`, `least_latency`, `least_failures` (`BalancingStrategy`).
  Wired via `Loom(balancer=...)`; spreads the fully-automatic path across a
  pool instead of always picking the single best model.

#### Provider benchmarking
- `client.compare(providers=, prompt=)` (sync + async) — runs candidates
  concurrently, returns `CompareReport` of `CompareResult` rows
  (latency / tokens / cost / output) plus a `CompareSummary` naming the
  cheapest / fastest / highest-quality result. Per-provider failures are
  captured as `ok=False` rows, not raised.

#### Provider-agnostic structured outputs
- `generate(schema=PydanticModel)` returns a validated model instance
  instead of a dict. Pydantic is an optional dependency (`loom[structured]`);
  a clear `StructuredOutputError` is raised when it's missing or validation
  fails.
- Native provider modes: OpenAI `response_format`, Anthropic tool-based
  JSON, Gemini `response_schema`; other providers fall back to prompt-driven
  JSON + validation. `providers.supports_structured_output(...)` capability.

#### Analytics
- Every client records call metrics to a zero-config in-memory sink
  (`InMemorySink`), surfaced via `client.analytics()` —
  `summary()`, `by_provider()`, `by_model()`, `recent()`, with an optional
  time window. `Loom(analytics=False)` opts out, or pass a custom `EventSink`.
- Events gained `retries` counts and optional per-call `tags=` metadata.
  Recording writes straight to the client's sink — the global `loom` logger
  is untouched, so existing handlers are unaffected. Existing on-disk
  `SQLiteSink` databases migrate automatically.

### Changed
- `modality` now defaults to `"text"` on `generate()` (was effectively
  always passed).
- Package version → 2.0.0; `loom.__version__` and `pyproject.toml` aligned.

### Compatibility
- No public symbol removed; no deprecations. The v1 stability surface in
  `docs/stability.md` is unchanged. New parameters (`providers=`, `router=`,
  `fallback=`, `schema=`, `tags=`) are optional and mutually-exclusive with
  explicit `provider=`/`model=`; omitting them preserves 1.x behavior
  exactly. `Router` / `Candidate` / `route()` remain as-is.

---

## [1.0.0] — 2026-06-14

The v1 stability commitment. The public surface documented in
`docs/stability.md` is now bound by semver: no breaking changes to it
within the 1.x line, no exceptions.

### Added

#### Key vault integration
- `KeyVault` Protocol — `get(name) -> str | None`.
- `InMemoryVault` for tests and programmatic boot.
- `AWSSecretsManagerVault` with single-secret-per-key and JSON-bundle
  modes, prefix support, in-process TTL cache, fail-soft on outages.
- `GCPSecretManagerVault` with Application Default Credentials, prefix
  and version support.
- `HashiCorpVaultBackend` for KV v2 engine with configurable
  `secret_key` and inject-able authenticated client.
- `require_env` now resolves in the order `api_keys → env → vault`,
  preserving local-override semantics.

#### Observability dashboard
- `SQLiteSink` — bundled sink with indexed schema, mutex-guarded
  single connection, supports `":memory:"` for tests.
- `EventSink` Protocol for swapping in Postgres / ClickHouse / etc.
- `LoomLogHandler` — drains the `loom` logger into a sink without
  touching call-site code; fail-soft on sink errors.
- `make_dashboard(sink)` — read-only Flask Blueprint with HTML and
  JSON endpoints (`/api/summary`, `/api/by-provider`, `/api/by-model`,
  `/api/recent`), time-window picker (`1h / 24h / 7d / 30d / all`).

#### Smart model routing + cross-vendor failover
- `Router(candidates, validator)` — cheap-first model routing with a
  caller-supplied quality validator. Cache and dedup compose for free.
- `Candidate` dataclass + tuple shorthand.
- `Router.failover(...)` — sugar over `Router` that pre-populates
  candidates from a cross-vendor `EquivalenceMap`.
- `EquivalenceMap` with bundled tiers (`text/nano`, `text/cheap`,
  `text/standard`, `text/frontier`).
- `Loom.route(router, prompt, ...)` and `AsyncLoom.route(...)`.

#### Batch API
- `BatchRequest`, `BatchHandle`, `Loom.submit_batch`, `Loom.run_batch`.
- OpenAI Batch adapter (`/v1/chat/completions`, `/v1/images/generations`).
- Anthropic Batch adapter (`/v1/messages/batches`) reusing the live
  adapter's body builder so prompt caching works in batch.

#### Vendor-native prompt caching
- `cached_tokens` and `cache_creation_tokens` surfaced in `Usage`.
- Per-provider discount table (`_prompt_cache_rates.py`): OpenAI 50%,
  Anthropic / DeepSeek 10% (read) and Anthropic 125% (write), Gemini 25%.
- Cost computation discounts each token bucket at its true rate.
- Automatic for OpenAI / DeepSeek; opt-in for Anthropic via
  `cache_system` / `cache_user` knobs.

#### Gemini context caching
- `ContextCacheHandle` resource handle.
- `Loom.create_context_cache(...)` and `Loom.delete_context_cache(handle)`.
- `gemini_provider` consumes `cached_content` param and surfaces
  `cached_tokens` from usage metadata.

#### Optimization layer (foundation)
- `RetryPolicy` with exponential backoff + jitter, classified
  exceptions, `Loom(retry=None)` to disable.
- `InMemoryCache` (LRU + TTL) and `RedisCache` (fail-soft).
- Single-flight request deduplication (`InFlight`).
- Cache → dedup → retry-wrapped call ordering.

#### Async support
- `AsyncLoom` with native `agenerate` paths for openai / anthropic /
  gemini providers; sync-only adapters wrapped via `asyncio.to_thread`.
- `loom.agenerate(...)` module-level convenience.

#### Library packaging
- Setuptools wheel build (`python -m build --wheel`).
- Extras: `openai`, `anthropic`, `gemini`, `tencent`, `yaml`, `redis`,
  `all`, `dev`.
- ContextVar-based per-call api_keys plumbing (async-safe).
- Pluggable catalog backends (`Catalog.from_yaml(...)`,
  `Catalog.from_mapping(...)`).

### Documentation
- `docs/api_reference.md` — full surface reference.
- `docs/migration_guide.md` — incremental adoption playbook.
- `docs/stability.md` — public vs internal API, semver promise,
  deprecation policy.
- MkDocs site (`mkdocs.yml`) deployable via GitHub Pages.

---

## [0.1.0] — 2026-04 *(pre-history)*

Phase 0 + Phase 1 outcome — Flask demo app with native-SDK adapters
extracted into an installable `loom` package. Single `Loom.generate`
contract live, 14+ vendor catalog, ContextVar-based api_keys plumbing.

Pre-1.0 surface; no compatibility guarantees.
