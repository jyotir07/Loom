"""Loom — the public client class + module-level convenience wrapper.

Sync:

    client = Loom.from_env()
    result = client.generate(provider=..., modality=..., model=..., prompt=...)

    # or
    import loom
    result = loom.generate(provider=..., modality=..., model=..., prompt=...)

Async:

    aclient = AsyncLoom.from_env()
    result = await aclient.generate(provider=..., modality=..., model=..., prompt=...)

    # or
    import loom
    result = await loom.agenerate(provider=..., modality=..., model=..., prompt=...)

Both surfaces share the catalog, api_keys, cost computation, and
structured logging paths.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from loom import _context
from loom import batch_providers as _batch_providers
from loom import context_cache_providers as _ctx_cache_providers
from loom import providers as _providers
from loom._cache import CacheBackend
from loom._call_key import call_key
from loom import _structured
from loom._compare import (
    CompareReport,
    run_compare_async,
    run_compare_sync,
)
from loom._context_cache import ContextCacheHandle
from loom._dedup import InFlight
from loom._logging import log_call
from loom._pricing import (
    DEFAULT_LOCAL_CURRENCY,
    DEFAULT_LOCAL_TO_USD,
    compute_cost,
)
from loom._retry import RetryPolicy, arun_with_retry, is_retryable, run_with_retry
from loom._router import (
    Candidate,
    FallbackPolicy,
    Router,
    run_route_async,
    run_route_sync,
)
from loom.batch import BatchHandle, BatchRequest
from loom.catalog import Catalog
from loom.errors import ProviderError, RateLimitError
from loom.routing import (
    CircuitState,
    HealthRegistry,
    LoadBalancer,
    RoutingStrategy,
    StrategyLike,
    StrategySelector,
)

_UNSET: Any = object()

# Strategy used when the caller names providers but no explicit strategy
# (providers=[...] without router=), and — later — for fully automatic
# selection. Balanced trades quality, cost, and latency.
_DEFAULT_STRATEGY = RoutingStrategy.BALANCED


class Loom:
    """The Loom client.

    Holds a Catalog and dispatches generate() calls to provider adapters.
    Vendor API keys are read from `api_keys` first, then from the process
    environment (see loom.providers._common.require_env).

    Example:

        client = Loom(
            api_keys={"OPENAI_API_KEY": "sk-..."},
            catalog=my_catalog,
        )

    `Loom.from_env()` is the convenience constructor that reads keys
    from a .env file and the process environment instead.
    """

    def __init__(
        self,
        *,
        catalog: Catalog | None = None,
        api_keys: dict[str, str] | None = None,
        local_currency: str = DEFAULT_LOCAL_CURRENCY,
        local_to_usd: float = DEFAULT_LOCAL_TO_USD,
        retry: RetryPolicy | None = _UNSET,
        cache: CacheBackend | None = None,
        dedup: bool = True,
        vault: Any | None = None,
        health: HealthRegistry | None = _UNSET,
        balancer: LoadBalancer | None = None,
    ) -> None:
        self.catalog = catalog or Catalog()
        self.api_keys: dict[str, str] = dict(api_keys or {})
        self.local_currency = local_currency
        self.local_to_usd = local_to_usd
        # retry=_UNSET (default) -> use default policy; retry=None -> disabled.
        self.retry = RetryPolicy() if retry is _UNSET else retry
        self.cache = cache
        self._inflight: InFlight | None = InFlight() if dedup else None
        # KeyVault — third source for require_env after api_keys + env.
        self.vault = vault
        # health=_UNSET (default) -> track in a fresh registry;
        # health=None -> tracking disabled. When present, routing consumes
        # it: open-circuit providers are skipped and recovering ones are
        # deprioritized (see _health_reorder / StrategySelector).
        self.health: HealthRegistry | None = (
            HealthRegistry() if health is _UNSET else health
        )
        # Optional load balancer. When set, the fully-automatic path
        # (generate(prompt=...)) spreads traffic across its provider pool
        # instead of always landing on the single best model.
        self.balancer = balancer

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | os.PathLike[str] | None = None,
        catalog: Catalog | None = None,
        api_keys: dict[str, str] | None = None,
        local_currency: str = DEFAULT_LOCAL_CURRENCY,
        local_to_usd: float = DEFAULT_LOCAL_TO_USD,
        retry: RetryPolicy | None = _UNSET,
        cache: CacheBackend | None = None,
        dedup: bool = True,
        vault: Any | None = None,
        health: HealthRegistry | None = _UNSET,
        balancer: LoadBalancer | None = None,
    ) -> "Loom":
        """Build a Loom that reads vendor keys from environment variables.

        If `dotenv_path` is given, that .env file is loaded first. If
        it's omitted but a `.env` exists in the current working directory,
        that is loaded. Already-set env vars are not overridden.
        """
        try:
            from dotenv import load_dotenv
        except ImportError:
            load_dotenv = None

        if load_dotenv is not None:
            if dotenv_path is not None:
                load_dotenv(dotenv_path=Path(dotenv_path), override=False)
            else:
                default = Path.cwd() / ".env"
                if default.is_file():
                    load_dotenv(dotenv_path=default, override=False)

        return cls(
            catalog=catalog,
            api_keys=api_keys,
            local_currency=local_currency,
            local_to_usd=local_to_usd,
            retry=retry,
            cache=cache,
            dedup=dedup,
            vault=vault,
            health=health,
            balancer=balancer,
        )

    def generate(
        self,
        *,
        provider: str | None = None,
        modality: str = "text",
        model: str | None = None,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        providers: list[str] | None = None,
        router: StrategyLike | None = None,
        fallback: FallbackPolicy | None = None,
        schema: Any | None = None,
    ) -> Any:
        """Generate a response, optionally as a validated `schema` object.

        Without `schema=`, returns the usual response dict (see
        `_run_generate` for the full routing/cache/dedup flow). With
        `schema=` (a Pydantic model), Loom asks the model for JSON matching
        that schema, then parses and validates the reply and returns a
        schema instance instead of the dict — a provider-agnostic
        structured output. Pydantic is an optional dependency required only
        when `schema=` is used. `schema=` applies to `modality="text"`.
        """
        if schema is None:
            return self._run_generate(
                provider=provider, modality=modality, model=model,
                prompt=prompt, params=params, use_cache=use_cache,
                providers=providers, router=router, fallback=fallback,
            )
        if modality != "text":
            raise _structured.StructuredOutputError(
                "schema= is only supported for modality 'text'"
            )
        _structured.ensure_available(schema)
        result = self._run_generate(
            provider=provider, modality=modality, model=model,
            prompt=_structured.augment_prompt(prompt, schema),
            params=params, use_cache=use_cache,
            providers=providers, router=router, fallback=fallback,
        )
        return _structured.parse(schema, result.get("text"))

    def _run_generate(
        self,
        *,
        provider: str | None = None,
        modality: str = "text",
        model: str | None = None,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        providers: list[str] | None = None,
        router: StrategyLike | None = None,
        fallback: FallbackPolicy | None = None,
    ) -> dict[str, Any]:
        """Resolve `model` against the catalog and dispatch to the provider.

        Four ways to choose where the call goes:

            generate(prompt=...)                     # fully automatic
            generate(provider=..., model=..., ...)   # explicit (unchanged)
            generate(providers=[...], ...)           # ordered preference
            generate(router="balanced", ...)         # strategy-based

        With nothing but a prompt, Loom picks the optimal model itself
        using the default `balanced` strategy for `modality` (default
        "text"). `providers=` / `router=` route through the intelligent
        router and cannot be combined with `provider=` / `model=`.

        `params` are merged on top of the catalog defaults for that
        model — caller params win on conflict.

        Flow when both cache and dedup are enabled:
            1. Cache hit?  -> return immediately, log cached=True.
            2. In-flight?  -> wait on the existing caller, log deduped=True.
            3. Otherwise   -> claim the slot, run with retry, fill cache,
                              notify waiters.
        """
        if fallback is not None:
            chain = self._resolve_fallback_chain(
                provider=provider, model=model, providers=providers,
                router=router, fallback=fallback, modality=modality,
            )
            return run_route_sync(
                self, Router(candidates=chain),
                prompt=prompt, params=params, use_cache=use_cache,
                fallback_when=self._fallback_predicate(),
            )
        if (
            provider is None and model is None
            and providers is None and router is None
        ):
            provider, model = self._auto_select(modality)
        if providers is not None or router is not None:
            built = self._resolve_routing(
                provider=provider, model=model,
                providers=providers, router=router, modality=modality,
            )
            return self.route(
                built, prompt=prompt, params=params, use_cache=use_cache
            )
        if provider is None or model is None:
            raise ValueError(
                "generate() requires provider= and model=, or use providers=/"
                "router= for intelligent routing"
            )

        upstream_model, catalog_params = self.catalog.resolve(
            provider, modality, model
        )
        merged: dict[str, Any] = dict(catalog_params)
        if params:
            merged.update(params)

        key = call_key(
            provider=provider,
            modality=modality,
            model=upstream_model,
            prompt=prompt,
            params=merged,
        )
        started = time.perf_counter()

        # 1. Cache lookup.
        if self.cache is not None and use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                log_call(
                    provider=provider, modality=modality, model=model,
                    upstream_model=upstream_model,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    result=cached, cached=True,
                )
                return cached

        # 2. Single-flight: claim slot or wait on existing one.
        is_owner = True
        slot = None
        if self._inflight is not None:
            is_owner, slot = self._inflight.claim_or_wait_sync(key)

        if not is_owner:
            # Wait for the owner to finish, then propagate their result/error.
            assert slot is not None
            slot.event.wait()
            if slot.error is not None:
                log_call(
                    provider=provider, modality=modality, model=model,
                    upstream_model=upstream_model,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    result=None, error=slot.error, deduped=True,
                )
                raise slot.error
            assert slot.result is not None
            log_call(
                provider=provider, modality=modality, model=model,
                upstream_model=upstream_model,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                result=slot.result, deduped=True,
            )
            return slot.result

        # 3. We own the slot — run the upstream call (with retry) and fan out.
        ctx = _context.LoomContext(api_keys=self.api_keys, vault=self.vault)
        try:
            def _do_call() -> dict[str, Any]:
                with _context.use(ctx):
                    return _providers.generate(
                        provider, modality, upstream_model, merged, prompt
                    )

            result = run_with_retry(self.retry, _do_call)
        except BaseException as exc:
            log_call(
                provider=provider, modality=modality, model=model,
                upstream_model=upstream_model,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                result=None, error=exc,
            )
            self._record_health_failure(provider, exc)
            if self._inflight is not None:
                self._inflight.finish_sync(key, error=exc)
            raise

        enriched = self._enrich(
            result,
            provider=provider, modality=modality, model=model,
            upstream_model=upstream_model,
        )
        self._record_health_success(provider, started)
        if self.cache is not None and use_cache:
            self.cache.set(key, enriched)
        log_call(
            provider=provider, modality=modality, model=model,
            upstream_model=upstream_model,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            result=enriched,
        )
        if self._inflight is not None:
            self._inflight.finish_sync(key, result=enriched)
        return enriched

    def _enrich(
        self,
        result: dict[str, Any],
        *,
        provider: str,
        modality: str,
        model: str,
        upstream_model: str,
    ) -> dict[str, Any]:
        result.setdefault("provider", provider)
        result.setdefault("model", model)
        result.setdefault("upstream_model", upstream_model)

        image_count = 0
        if modality == "image":
            image_count = len(result.get("images") or [])

        cost = compute_cost(
            catalog=self.catalog,
            provider=provider,
            modality=modality,
            model_id=model,
            usage=result.get("usage"),
            image_count=image_count,
            local_currency=self.local_currency,
            local_to_usd=self.local_to_usd,
        )
        if cost is not None:
            result["cost"] = cost
        return result

    # ---------------- health ----------------

    def _record_health_success(self, provider: str, started: float) -> None:
        if self.health is not None:
            self.health.record_success(
                provider, latency_ms=(time.perf_counter() - started) * 1000.0
            )

    def _record_health_failure(self, provider: str, exc: BaseException) -> None:
        if self.health is not None:
            self.health.record_failure(
                provider,
                rate_limited=isinstance(exc, RateLimitError),
                error=str(exc),
            )

    def _health_reorder(self, candidates: list[Candidate]) -> list[Candidate]:
        """Re-order a candidate chain by current provider health.

        Healthy (closed-circuit) providers come first, then recovering
        (half-open) ones; both groups keep their incoming order so an
        explicit `providers=` chain still honours the caller's preference
        within a health tier. Open-circuit providers are dropped — unless
        *every* candidate is open, in which case the chain is returned
        untouched rather than leaving the caller with nothing to try.

        A no-op when health tracking is disabled. Selector-built chains are
        already health-filtered; this also covers the per-provider paths
        (`providers=`, explicit fallback chains) the selector can't filter
        on its own.
        """
        if self.health is None or not candidates:
            return candidates
        healthy: list[Candidate] = []
        recovering: list[Candidate] = []
        for cand in candidates:
            state = self.health.state(cand.provider)
            if state is CircuitState.OPEN:
                continue
            if state is CircuitState.HALF_OPEN:
                recovering.append(cand)
            else:
                healthy.append(cand)
        ordered = healthy + recovering
        return ordered if ordered else candidates

    # ---------------- routing ----------------

    def route(
        self,
        router: Router,
        *,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Try `router.candidates` in order, return the first response
        that passes `router.validator` (or the first that succeeds, if
        no validator). See `loom._router` for full semantics.
        """
        return run_route_sync(
            self, router, prompt=prompt, params=params, use_cache=use_cache
        )

    def _auto_select(self, modality: str) -> tuple[str, str]:
        """Pick (provider, model) automatically for a bare `generate()`.

        With a `balancer` configured, the balancer chooses the provider
        (spreading traffic across its pool) and the default strategy picks
        that provider's best model. Otherwise the default strategy ranks
        every task-compatible model in the catalog and the single best one
        is returned. Either way this dispatches directly (no failover
        chain) — automatic *selection*, not routing.
        """
        selector = StrategySelector(self.catalog, health=self.health)
        if self.balancer is not None:
            provider = self.balancer.pick(self.health)
            if provider is not None:
                chosen = selector.best(
                    _DEFAULT_STRATEGY, modality=modality, providers=[provider]
                )
                if chosen is not None:
                    return chosen.provider, chosen.model
            # Balancer pick unusable (no provider, or it can't serve this
            # modality) — fall back to the global best below.

        chosen = selector.best(_DEFAULT_STRATEGY, modality=modality)
        if chosen is None:
            raise ValueError(
                f"automatic selection found no model for modality {modality!r}"
            )
        return chosen.provider, chosen.model

    def _fallback_predicate(self) -> "Any":
        """A predicate classifying an exception as fallback-worthy, using
        the client's RetryPolicy taxonomy (or the default when retry is
        disabled)."""
        policy = self.retry if isinstance(self.retry, RetryPolicy) else None
        return lambda exc: is_retryable(exc, policy)

    def _resolve_fallback_chain(
        self,
        *,
        provider: str | None,
        model: str | None,
        providers: list[str] | None,
        router: StrategyLike | None,
        fallback: FallbackPolicy,
        modality: str,
    ) -> list[Candidate]:
        """Build the ordered candidate chain for a `fallback=` call.

        Provider order comes from `fallback.providers` (preferred), else
        `providers=`, else the whole catalog ranked by strategy. The model
        for each provider is its best under the `router=` strategy (or the
        default). The chain is de-duplicated and truncated to
        `fallback.retries`.
        """
        if provider is not None or model is not None:
            raise ValueError(
                "fallback= cannot be combined with explicit provider=/model= — "
                "put the provider chain in FallbackPolicy(providers=[...]) or "
                "use providers=/router="
            )

        strategy = (
            RoutingStrategy.coerce(router)
            if router is not None
            else _DEFAULT_STRATEGY
        )
        selector = StrategySelector(self.catalog, health=self.health)

        chain_providers: list[str] | None = None
        if fallback.providers:
            chain_providers = list(fallback.providers)
        elif providers is not None:
            if not isinstance(providers, (list, tuple)) or len(providers) == 0:
                raise ValueError(
                    "providers= must be a non-empty list of provider names"
                )
            chain_providers = list(providers)

        candidates: list[Candidate] = []
        seen: set[str] = set()

        def _add(cand: Candidate | None) -> None:
            if cand is not None and cand.label() not in seen:
                seen.add(cand.label())
                candidates.append(cand)

        if chain_providers is None:
            # No explicit chain: rank the whole catalog by strategy.
            for cand in selector.select(strategy, modality=modality):
                _add(cand)
        else:
            for prov in chain_providers:
                _add(
                    selector.best(
                        strategy, modality=modality, providers=[prov]
                    )
                )

        if not candidates:
            raise ValueError(
                f"fallback produced no candidates for modality {modality!r}"
            )
        return self._health_reorder(candidates)[: fallback.retries]

    def _resolve_routing(
        self,
        *,
        provider: str | None,
        model: str | None,
        providers: list[str] | None,
        router: StrategyLike | None,
        modality: str,
    ) -> Router:
        """Turn `providers=` / `router=` into a `Router` of candidates.

        - `router=` ranks candidates with that strategy (optionally
          restricted to `providers=` when both are given).
        - `providers=` alone keeps the caller's provider order, picking
          each provider's best model under the default strategy.

        Raises ValueError/TypeError on invalid combinations or when no
        candidate can be produced. The returned Router is then driven by
        `route()`, so failover/validator/retry all apply unchanged.
        """
        if provider is not None or model is not None:
            raise ValueError(
                "provider=/model= cannot be combined with providers=/router= — "
                "pass either an explicit provider+model or a routing selector"
            )
        if providers is not None:
            if not isinstance(providers, (list, tuple)):
                raise TypeError("providers= must be a list of provider names")
            if len(providers) == 0:
                raise ValueError("providers= must contain at least one provider")

        selector = StrategySelector(self.catalog, health=self.health)
        provider_subset = list(providers) if providers is not None else None

        if router is not None:
            strategy = RoutingStrategy.coerce(router)
            candidates = selector.select(
                strategy, modality=modality, providers=provider_subset
            )
            if not candidates:
                where = (
                    f" among providers {provider_subset}" if provider_subset else ""
                )
                raise ValueError(
                    f"router={router!r} produced no candidates for modality "
                    f"{modality!r}{where}"
                )
            return Router(candidates=self._health_reorder(candidates))

        # providers= only: caller's order, best model per provider.
        candidates = []
        for prov in provider_subset:  # provider_subset is non-empty here
            best = selector.select(
                _DEFAULT_STRATEGY, modality=modality, providers=[prov]
            )
            if best:
                candidates.append(best[0])
        if not candidates:
            raise ValueError(
                f"none of the providers {provider_subset} offer modality "
                f"{modality!r}"
            )
        return Router(candidates=self._health_reorder(candidates))

    # ---------------- benchmarking ----------------

    def compare(
        self,
        *,
        prompt: str,
        providers: list[Any],
        modality: str = "text",
        params: dict[str, Any] | None = None,
        strategy: StrategyLike | None = None,
        use_cache: bool = False,
    ) -> CompareReport:
        """Run `prompt` across `providers` concurrently and tabulate results.

        Each entry in `providers` may be a provider name (``"openai"`` —
        its best model for `modality` under `strategy` is chosen), a
        ``(provider, model)`` pair, or a :class:`Candidate` for full
        control. Returns a :class:`CompareReport`: one
        :class:`CompareResult` row per entry (latency, tokens, cost,
        output) plus a summary naming the cheapest / fastest / highest-
        quality result.

        Benchmarking reuses `generate()`, so retry / health / logging all
        apply. Two defaults suit measurement: the cache is bypassed
        (`use_cache=False`) so latency is real, and a per-provider failure
        becomes a row with ``ok=False`` instead of aborting the run.
        """
        candidates = self._resolve_compare_candidates(
            providers, modality, strategy
        )
        return run_compare_sync(
            self, candidates, prompt=prompt, params=params, use_cache=use_cache
        )

    def _resolve_compare_candidates(
        self,
        providers: list[Any],
        modality: str,
        strategy: StrategyLike | None,
    ) -> list[Candidate]:
        """Turn each `compare()` entry into a concrete `Candidate`.

        Health is intentionally ignored here — a benchmark should exercise
        every named provider, including one whose circuit is currently
        open, so the caller sees how it actually performs right now.
        """
        if not isinstance(providers, (list, tuple)) or len(providers) == 0:
            raise ValueError(
                "compare() requires a non-empty providers list"
            )
        strat = (
            RoutingStrategy.coerce(strategy)
            if strategy is not None
            else _DEFAULT_STRATEGY
        )
        selector = StrategySelector(self.catalog, health=None)

        candidates: list[Candidate] = []
        for item in providers:
            candidates.append(
                self._coerce_compare_item(item, modality, selector, strat)
            )
        return candidates

    @staticmethod
    def _coerce_compare_item(
        item: Any,
        modality: str,
        selector: StrategySelector,
        strategy: RoutingStrategy,
    ) -> Candidate:
        if isinstance(item, Candidate):
            return item
        if isinstance(item, str):
            chosen = selector.best(
                strategy, modality=modality, providers=[item]
            )
            if chosen is None:
                raise ValueError(
                    f"provider {item!r} offers no {modality!r} model to compare"
                )
            return chosen
        if isinstance(item, (list, tuple)) and len(item) == 2:
            return Candidate(provider=item[0], modality=modality, model=item[1])
        raise TypeError(
            "compare() providers entries must be a provider name, a "
            f"(provider, model) pair, or a Candidate — got {item!r}"
        )

    # ---------------- batch ----------------

    def submit_batch(
        self,
        requests: list[BatchRequest],
        **adapter_kwargs: Any,
    ) -> BatchHandle:
        """Submit a batch to the appropriate vendor batch endpoint.

        All requests must share `provider`. Returns a `BatchHandle` —
        call `.wait()` to block until done, or `.status()` / `.results()`
        to poll explicitly.

        Extra kwargs are forwarded to the vendor adapter's `submit()`
        (e.g. `completion_window="24h"` on OpenAI).
        """
        if not requests:
            raise ProviderError("submit_batch requires at least one request")
        providers = {r.provider for r in requests}
        if len(providers) > 1:
            raise ProviderError(
                "submit_batch requires a single provider per batch — got "
                f"{sorted(providers)}. File N batches if you need that."
            )
        provider = providers.pop()
        module = _batch_providers._module_for(provider)

        def _resolve(p: str, m: str, mid: str):
            return self.catalog.resolve(p, m, mid)

        # api_keys context: providers read keys via require_env, so we
        # need the LoomContext active during submit AND during later
        # status/results/cancel calls — captured via the factory below.
        def _ctx_factory():
            return _context.LoomContext(api_keys=self.api_keys, vault=self.vault)

        with _context.use(_ctx_factory()):
            batch_id = module.submit(requests, _resolve, **adapter_kwargs)

        return BatchHandle(
            id=batch_id,
            provider=provider,
            requests=list(requests),
            _module=module,
            _context_factory=_ctx_factory,
        )

    # ---------------- context cache ----------------

    def create_context_cache(
        self,
        *,
        provider: str,
        model: str,
        contents: Any,
        system_instruction: Any | None = None,
        ttl_seconds: float | None = None,
        display_name: str | None = None,
    ) -> ContextCacheHandle:
        """Create a vendor-side context cache and return a handle.

        Pass `handle.id` through `params={"cached_content": handle.id}`
        on subsequent generate() calls to reference it. Only Gemini has
        a registered adapter in this chunk; other providers raise
        ProviderError("no Loom context-cache adapter yet").
        """
        module = _ctx_cache_providers._module_for(provider)

        def _ctx_factory():
            return _context.LoomContext(api_keys=self.api_keys, vault=self.vault)

        with _context.use(_ctx_factory()):
            info = module.create(
                model,
                contents=contents,
                system_instruction=system_instruction,
                ttl_seconds=ttl_seconds,
                display_name=display_name,
            )
        return ContextCacheHandle(
            id=info["id"],
            provider=provider,
            model=model,
            display_name=info.get("display_name") or display_name,
            ttl_seconds=ttl_seconds,
            _module=module,
            _context_factory=_ctx_factory,
        )

    def delete_context_cache(self, handle: ContextCacheHandle) -> None:
        """Delete the vendor-side resource pointed to by `handle`."""
        handle.delete()

    def run_batch(
        self,
        requests: list[BatchRequest],
        *,
        poll_interval: float = 30.0,
        timeout: float = 24 * 3600.0,
        **adapter_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Submit + poll + return aligned results. Blocks for up to `timeout`."""
        handle = self.submit_batch(requests, **adapter_kwargs)
        return handle.wait(poll_interval=poll_interval, timeout=timeout)


class AsyncLoom(Loom):
    """Async sibling of Loom.

    Inherits configuration (catalog, api_keys, currency) from Loom and
    exposes `generate(...)` as a coroutine. Native-async providers are
    awaited directly; sync-only providers are run via asyncio.to_thread.
    """

    async def generate(  # type: ignore[override]
        self,
        *,
        provider: str | None = None,
        modality: str = "text",
        model: str | None = None,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        providers: list[str] | None = None,
        router: StrategyLike | None = None,
        fallback: FallbackPolicy | None = None,
        schema: Any | None = None,
    ) -> Any:
        """Async sibling of :meth:`Loom.generate`. With `schema=`, returns a
        validated Pydantic instance instead of the response dict; otherwise
        returns the response dict. See :meth:`Loom.generate`."""
        if schema is None:
            return await self._run_generate(
                provider=provider, modality=modality, model=model,
                prompt=prompt, params=params, use_cache=use_cache,
                providers=providers, router=router, fallback=fallback,
            )
        if modality != "text":
            raise _structured.StructuredOutputError(
                "schema= is only supported for modality 'text'"
            )
        _structured.ensure_available(schema)
        result = await self._run_generate(
            provider=provider, modality=modality, model=model,
            prompt=_structured.augment_prompt(prompt, schema),
            params=params, use_cache=use_cache,
            providers=providers, router=router, fallback=fallback,
        )
        return _structured.parse(schema, result.get("text"))

    async def _run_generate(  # type: ignore[override]
        self,
        *,
        provider: str | None = None,
        modality: str = "text",
        model: str | None = None,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        providers: list[str] | None = None,
        router: StrategyLike | None = None,
        fallback: FallbackPolicy | None = None,
    ) -> dict[str, Any]:
        if fallback is not None:
            chain = self._resolve_fallback_chain(
                provider=provider, model=model, providers=providers,
                router=router, fallback=fallback, modality=modality,
            )
            return await run_route_async(
                self, Router(candidates=chain),
                prompt=prompt, params=params, use_cache=use_cache,
                fallback_when=self._fallback_predicate(),
            )
        if (
            provider is None and model is None
            and providers is None and router is None
        ):
            provider, model = self._auto_select(modality)
        if providers is not None or router is not None:
            built = self._resolve_routing(
                provider=provider, model=model,
                providers=providers, router=router, modality=modality,
            )
            return await self.route(
                built, prompt=prompt, params=params, use_cache=use_cache
            )
        if provider is None or model is None:
            raise ValueError(
                "generate() requires provider= and model=, or use providers=/"
                "router= for intelligent routing"
            )

        upstream_model, catalog_params = self.catalog.resolve(
            provider, modality, model
        )
        merged: dict[str, Any] = dict(catalog_params)
        if params:
            merged.update(params)

        key = call_key(
            provider=provider,
            modality=modality,
            model=upstream_model,
            prompt=prompt,
            params=merged,
        )
        started = time.perf_counter()

        if self.cache is not None and use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                log_call(
                    provider=provider, modality=modality, model=model,
                    upstream_model=upstream_model,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    result=cached, cached=True,
                )
                return cached

        is_owner = True
        slot = None
        if self._inflight is not None:
            is_owner, slot = self._inflight.claim_or_wait_async(key)

        if not is_owner:
            assert slot is not None
            await slot.event.wait()
            if slot.error is not None:
                log_call(
                    provider=provider, modality=modality, model=model,
                    upstream_model=upstream_model,
                    latency_ms=(time.perf_counter() - started) * 1000.0,
                    result=None, error=slot.error, deduped=True,
                )
                raise slot.error
            assert slot.result is not None
            log_call(
                provider=provider, modality=modality, model=model,
                upstream_model=upstream_model,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                result=slot.result, deduped=True,
            )
            return slot.result

        ctx = _context.LoomContext(api_keys=self.api_keys, vault=self.vault)
        try:
            async def _do_call() -> dict[str, Any]:
                with _context.use(ctx):
                    return await _providers.agenerate(
                        provider, modality, upstream_model, merged, prompt
                    )

            result = await arun_with_retry(self.retry, _do_call)
        except BaseException as exc:
            log_call(
                provider=provider, modality=modality, model=model,
                upstream_model=upstream_model,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                result=None, error=exc,
            )
            self._record_health_failure(provider, exc)
            if self._inflight is not None:
                self._inflight.finish_async(key, error=exc)
            raise

        enriched = self._enrich(
            result,
            provider=provider, modality=modality, model=model,
            upstream_model=upstream_model,
        )
        self._record_health_success(provider, started)
        if self.cache is not None and use_cache:
            self.cache.set(key, enriched)
        log_call(
            provider=provider, modality=modality, model=model,
            upstream_model=upstream_model,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            result=enriched,
        )
        if self._inflight is not None:
            self._inflight.finish_async(key, result=enriched)
        return enriched

    async def route(  # type: ignore[override]
        self,
        router: Router,
        *,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        return await run_route_async(
            self, router, prompt=prompt, params=params, use_cache=use_cache
        )

    async def compare(  # type: ignore[override]
        self,
        *,
        prompt: str,
        providers: list[Any],
        modality: str = "text",
        params: dict[str, Any] | None = None,
        strategy: StrategyLike | None = None,
        use_cache: bool = False,
    ) -> CompareReport:
        """Async sibling of :meth:`Loom.compare` — fans out with
        asyncio.gather instead of a thread pool. Same rows, same summary,
        same per-row failure capture."""
        candidates = self._resolve_compare_candidates(
            providers, modality, strategy
        )
        return await run_compare_async(
            self, candidates, prompt=prompt, params=params, use_cache=use_cache
        )


_default: Loom | None = None
_adefault: AsyncLoom | None = None


def _get_default() -> Loom:
    global _default
    if _default is None:
        _default = Loom.from_env()
    return _default


def _get_async_default() -> AsyncLoom:
    global _adefault
    if _adefault is None:
        _adefault = AsyncLoom.from_env()
    return _adefault


def generate(
    *,
    provider: str | None = None,
    modality: str = "text",
    model: str | None = None,
    prompt: str,
    params: dict[str, Any] | None = None,
    providers: list[str] | None = None,
    router: StrategyLike | None = None,
    fallback: FallbackPolicy | None = None,
    schema: Any | None = None,
) -> Any:
    """Module-level convenience — runs on the default Loom.from_env() instance.

    Accepts the same explicit (`provider`+`model`) or routing
    (`providers=` / `router=` / `fallback=`) entry points as `Loom.generate`,
    plus `schema=` for a validated structured-output object.
    """
    return _get_default().generate(
        provider=provider,
        modality=modality,
        model=model,
        prompt=prompt,
        params=params,
        providers=providers,
        router=router,
        fallback=fallback,
        schema=schema,
    )


async def agenerate(
    *,
    provider: str | None = None,
    modality: str = "text",
    model: str | None = None,
    prompt: str,
    params: dict[str, Any] | None = None,
    providers: list[str] | None = None,
    router: StrategyLike | None = None,
    fallback: FallbackPolicy | None = None,
    schema: Any | None = None,
) -> Any:
    """Async module-level convenience — runs on the default AsyncLoom.from_env().

    Accepts the same explicit or routing entry points as
    `AsyncLoom.generate`, plus `schema=` for a validated structured object.
    """
    return await _get_async_default().generate(
        provider=provider,
        modality=modality,
        model=model,
        prompt=prompt,
        params=params,
        providers=providers,
        router=router,
        fallback=fallback,
        schema=schema,
    )
