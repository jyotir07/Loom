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
from loom import providers as _providers
from loom._cache import CacheBackend
from loom._call_key import call_key
from loom._dedup import InFlight
from loom._logging import log_call
from loom._pricing import (
    DEFAULT_LOCAL_CURRENCY,
    DEFAULT_LOCAL_TO_USD,
    compute_cost,
)
from loom._retry import RetryPolicy, arun_with_retry, run_with_retry
from loom.catalog import Catalog

_UNSET: Any = object()


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
    ) -> None:
        self.catalog = catalog or Catalog()
        self.api_keys: dict[str, str] = dict(api_keys or {})
        self.local_currency = local_currency
        self.local_to_usd = local_to_usd
        # retry=_UNSET (default) -> use default policy; retry=None -> disabled.
        self.retry = RetryPolicy() if retry is _UNSET else retry
        self.cache = cache
        self._inflight: InFlight | None = InFlight() if dedup else None

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
        )

    def generate(
        self,
        *,
        provider: str,
        modality: str,
        model: str,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Resolve `model` against the catalog and dispatch to the provider.

        `params` are merged on top of the catalog defaults for that
        model — caller params win on conflict.

        Flow when both cache and dedup are enabled:
            1. Cache hit?  -> return immediately, log cached=True.
            2. In-flight?  -> wait on the existing caller, log deduped=True.
            3. Otherwise   -> claim the slot, run with retry, fill cache,
                              notify waiters.
        """
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
        ctx = _context.LoomContext(api_keys=self.api_keys)
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
            if self._inflight is not None:
                self._inflight.finish_sync(key, error=exc)
            raise

        enriched = self._enrich(
            result,
            provider=provider, modality=modality, model=model,
            upstream_model=upstream_model,
        )
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


class AsyncLoom(Loom):
    """Async sibling of Loom.

    Inherits configuration (catalog, api_keys, currency) from Loom and
    exposes `generate(...)` as a coroutine. Native-async providers are
    awaited directly; sync-only providers are run via asyncio.to_thread.
    """

    async def generate(  # type: ignore[override]
        self,
        *,
        provider: str,
        modality: str,
        model: str,
        prompt: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
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

        ctx = _context.LoomContext(api_keys=self.api_keys)
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
            if self._inflight is not None:
                self._inflight.finish_async(key, error=exc)
            raise

        enriched = self._enrich(
            result,
            provider=provider, modality=modality, model=model,
            upstream_model=upstream_model,
        )
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
    provider: str,
    modality: str,
    model: str,
    prompt: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience — runs on the default Loom.from_env() instance."""
    return _get_default().generate(
        provider=provider,
        modality=modality,
        model=model,
        prompt=prompt,
        params=params,
    )


async def agenerate(
    *,
    provider: str,
    modality: str,
    model: str,
    prompt: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Async module-level convenience — runs on the default AsyncLoom.from_env()."""
    return await _get_async_default().generate(
        provider=provider,
        modality=modality,
        model=model,
        prompt=prompt,
        params=params,
    )
