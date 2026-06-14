# Changelog

All notable changes to Loom. Versions follow [semantic versioning](https://semver.org).

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
