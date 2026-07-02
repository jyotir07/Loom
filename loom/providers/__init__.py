"""Provider registry + dispatch.

Each provider module under loom/providers/ exposes:

    def generate(modality, model, params, prompt) -> dict
    async def agenerate(modality, model, params, prompt) -> dict   # optional

`_LAZY` maps the catalog provider key to the import path. Modules are
imported on first use so `import loom` doesn't drag every vendor SDK
into memory.

Async dispatch prefers a provider's native `agenerate(...)` when
present; otherwise the sync function is run in a thread via
asyncio.to_thread so the AsyncLoom contract is preserved.

OpenAI-shaped vendors (mistral, deepseek, xai, minimax, zhipu,
perplexity, together, moonshot/kimi, seedream-image) share the
adapter in `_openai_compatible.py`.
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
    "openai":     "loom.providers.openai_provider",
    "anthropic":  "loom.providers.anthropic_provider",
    "gemini":     "loom.providers.gemini_provider",
    "xai":        "loom.providers.xai_provider",
    "mistral":    "loom.providers.mistral_provider",
    "deepseek":   "loom.providers.deepseek_provider",
    "minimax":    "loom.providers.minimax_provider",
    "zhipu":      "loom.providers.zhipu_provider",
    "perplexity": "loom.providers.perplexity_provider",
    "together":   "loom.providers.together_provider",
    "kimi":       "loom.providers.moonshot_provider",
    "moonshot":   "loom.providers.moonshot_provider",
    "bfl":        "loom.providers.bfl_provider",
    "seedream":   "loom.providers.seedream_provider",
    "hunyuan":    "loom.providers.hunyuan_provider",
    "ideogram":   "loom.providers.ideogram_provider",
}

_LOADED: dict[str, ModuleType] = {}

# Providers with a *native* structured-output mode (guaranteed-schema JSON).
# The shared layer (loom._structured) already produces validated objects on
# every provider via JSON parsing; this set marks where a native, provider-
# specific path can be wired later without changing the public contract.
_STRUCTURED_OUTPUT: frozenset[str] = frozenset(
    {"openai", "anthropic", "gemini"}
)


def supports_structured_output(provider: str) -> bool:
    """Whether `provider` has a native structured-output capability.

    Informational today: `generate(schema=...)` works on any provider via
    the provider-agnostic JSON strategy. This flag gates the native
    per-provider implementations added in later work.
    """
    return provider in _STRUCTURED_OUTPUT


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


def _prepare_params(
    provider: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Strip the reserved structured-output schema key for providers without
    a native path — they fall back to the augmented-prompt JSON strategy, and
    the key must never reach their SDK. Native providers keep it and consume
    it in their own adapter."""
    if supports_structured_output(provider):
        return params
    from loom._structured import strip_response_schema

    return strip_response_schema(params)


def generate(
    provider: str,
    modality: str,
    model: str,
    params: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Route a generate() call to the right provider module."""
    module = _module_for(provider)
    return module.generate(modality, model, _prepare_params(provider, params), prompt)


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
    prepared = _prepare_params(provider, params)
    native = getattr(module, "agenerate", None)
    if native is not None:
        return await native(modality, model, prepared, prompt)
    return await asyncio.to_thread(
        module.generate, modality, model, prepared, prompt
    )


__all__ = [
    "available",
    "generate",
    "agenerate",
    "supports_structured_output",
]
