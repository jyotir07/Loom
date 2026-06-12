"""Loom — the public client class + module-level convenience wrapper.

Phase 1 shape:

    client = Loom.from_env()
    result = client.generate(provider, modality, model, prompt)

Or, for a one-liner, use the module-level convenience:

    import loom
    result = loom.generate(provider, modality, model, prompt)

The convenience form is backed by a lazily-built default `Loom.from_env()`
instance, so the two paths share configuration and behaviour.

Phase 2 will widen the constructor:
    Loom(catalog=..., api_keys=..., cache_backend=...)
and add async via AsyncLoom / agenerate(). The Phase 1 surface is
designed so those additions don't break callers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loom import providers as _providers
from loom.catalog import Catalog


class Loom:
    """The Loom client.

    Holds a Catalog and dispatches generate() calls to provider adapters.
    Vendor API keys are read from environment variables by each provider
    on demand (see loom.providers._common.require_env).
    """

    def __init__(self, *, catalog: Catalog | None = None) -> None:
        self.catalog = catalog or Catalog()

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | os.PathLike[str] | None = None,
        catalog: Catalog | None = None,
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

        return cls(catalog=catalog)

    def generate(
        self,
        *,
        provider: str,
        modality: str,
        model: str,
        prompt: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve `model` against the catalog and dispatch to the provider.

        `params` are merged on top of the catalog defaults for that
        model — caller params win on conflict.
        """
        upstream_model, catalog_params = self.catalog.resolve(
            provider, modality, model
        )
        merged: dict[str, Any] = dict(catalog_params)
        if params:
            merged.update(params)
        return _providers.generate(provider, modality, upstream_model, merged, prompt)


_default: Loom | None = None


def _get_default() -> Loom:
    global _default
    if _default is None:
        _default = Loom.from_env()
    return _default


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
