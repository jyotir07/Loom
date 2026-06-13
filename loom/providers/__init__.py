"""Provider registry + dispatch.

Each provider module under loom/providers/ exposes:

    def generate(modality: str, model: str, params: dict, prompt: str) -> dict

REGISTRY maps the catalog provider key to the module. `generate()`
here is the dispatcher — Loom.generate() and loom.generate() both
funnel through it.

Phase 1 implements `openai` end-to-end (text + image) for the smoke
tests. The shared `_openai_compatible` helper is wired up so OpenAI-
shaped vendors (mistral, deepseek, xai, minimax, zhipu, perplexity,
together, seedream) only need a thin wrapper that points at the right
base URL — those wrappers land as the catalog needs them.
"""

from __future__ import annotations

import asyncio
import importlib
from types import ModuleType
from typing import Any

from loom.errors import ProviderError

# Lazy-loaded so importing `loom` doesn't drag every vendor SDK into
# memory. Keys here are the catalog provider keys.
_LAZY: dict[str, str] = {
    "openai": "loom.providers.openai_provider",
}

_LOADED: dict[str, ModuleType] = {}


def _module_for(provider: str) -> ModuleType:
    if provider in _LOADED:
        return _LOADED[provider]
    if provider not in _LAZY:
        raise ProviderError(
            f"provider '{provider}' is in the catalog but has no Loom adapter yet"
        )
    module = importlib.import_module(_LAZY[provider])
    _LOADED[provider] = module
    return module


def available() -> list[str]:
    """Provider keys with a registered adapter (whether loaded yet or not)."""
    return list(_LAZY.keys())


def generate(
    provider: str,
    modality: str,
    model: str,
    params: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Route a generate() call to the right provider module."""
    module = _module_for(provider)
    return module.generate(modality, model, params, prompt)


async def agenerate(
    provider: str,
    modality: str,
    model: str,
    params: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Route an async generate() call to the right provider module.

    Prefers the provider's native `agenerate(...)` coroutine. If the
    provider only exposes a sync `generate(...)`, runs it in a thread
    via asyncio.to_thread so callers still get a non-blocking await.
    """
    module = _module_for(provider)
    native = getattr(module, "agenerate", None)
    if native is not None:
        return await native(modality, model, params, prompt)
    return await asyncio.to_thread(
        module.generate, modality, model, params, prompt
    )


__all__ = ["available", "generate", "agenerate"]
