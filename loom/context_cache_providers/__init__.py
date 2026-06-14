"""Context-cache provider registry — same pattern as loom.batch_providers.

Each adapter exposes:

    create(model, *, contents, system_instruction=None, ttl_seconds=None,
           display_name=None) -> dict        # {"id": ..., "display_name": ..., ...}
    delete(cache_id) -> None
    get(cache_id) -> dict                    # raw vendor metadata; best-effort

Gemini ships in this chunk. Other vendors register here as they add the
capability.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from loom.errors import ProviderError

_LAZY: dict[str, str] = {
    "gemini": "loom.context_cache_providers.gemini_context_cache",
}

_LOADED: dict[str, ModuleType] = {}


def _module_for(provider: str) -> ModuleType:
    if provider in _LOADED:
        return _LOADED[provider]
    if provider not in _LAZY:
        raise ProviderError(
            f"provider '{provider}' has no Loom context-cache adapter yet"
        )
    module = importlib.import_module(_LAZY[provider])
    _LOADED[provider] = module
    return module


def available() -> list[str]:
    return list(_LAZY.keys())


__all__ = ["_LAZY", "_LOADED", "_module_for", "available"]
