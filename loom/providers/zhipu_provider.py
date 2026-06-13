"""Z.AI (GLM) — OpenAI-compatible chat completions at api.z.ai/api/paas/v4."""

from __future__ import annotations

from typing import Any

from loom.providers._openai_compatible import atext_only, text_only

_API_KEY_ENV = "ZAI_API_KEY"
_BASE_URL = "https://api.z.ai/api/paas/v4"


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
        provider_label="zhipu",
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
        provider_label="zhipu",
    )
