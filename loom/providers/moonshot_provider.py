"""Moonshot / Kimi — OpenAI-compatible chat completions at api.moonshot.ai/v1.

Both catalog keys "kimi" and "moonshot" point at the same vendor and
the same adapter; this module is registered under both keys in
loom/providers/__init__.py.
"""

from __future__ import annotations

from typing import Any

from loom.providers._openai_compatible import atext_only, text_only

_API_KEY_ENV = "MOONSHOT_API_KEY"
_BASE_URL = "https://api.moonshot.ai/v1"


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return text_only(
        api_key_env=_API_KEY_ENV,
        base_url=_BASE_URL,
        modality=modality,
        model=model,
        params=params,
        prompt=prompt,
        provider_label="moonshot",
    )


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return await atext_only(
        api_key_env=_API_KEY_ENV,
        base_url=_BASE_URL,
        modality=modality,
        model=model,
        params=params,
        prompt=prompt,
        provider_label="moonshot",
    )
