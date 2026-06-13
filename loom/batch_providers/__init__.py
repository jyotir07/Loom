"""Batch provider registry — same pattern as loom.providers.

Each batch adapter exposes:

    submit(requests, resolve) -> batch_id      # vendor-side id
    status(batch_id)          -> str           # vendor-side status
    results(batch_id, requests) -> list[dict]  # aligned to `requests`
    cancel(batch_id)          -> None

`resolve(provider, modality, model) -> (upstream_model, params)` is the
Catalog.resolve callable, passed in so adapters can translate
catalog-level model IDs (e.g. "gpt-image-1-high") into upstream model
IDs and default params without needing to know about Catalog.

OpenAI ships in this chunk. Anthropic/Gemini follow the same shape and
register here when added.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Callable

from loom.errors import ProviderError

_LAZY: dict[str, str] = {
    "openai": "loom.batch_providers.openai_batch",
}

_LOADED: dict[str, ModuleType] = {}


def _module_for(provider: str) -> ModuleType:
    if provider in _LOADED:
        return _LOADED[provider]
    if provider not in _LAZY:
        raise ProviderError(
            f"provider '{provider}' has no Loom batch adapter yet"
        )
    module = importlib.import_module(_LAZY[provider])
    _LOADED[provider] = module
    return module


def available() -> list[str]:
    return list(_LAZY.keys())


__all__ = ["_LAZY", "_LOADED", "_module_for", "available"]
