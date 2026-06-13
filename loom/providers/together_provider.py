"""Together AI — OpenAI-compatible chat completions at api.together.xyz/v1."""

from __future__ import annotations

from typing import Any

from loom.providers._openai_compatible import atext_only, text_only

_API_KEY_ENV = "TOGETHER_API_KEY"
_BASE_URL = "https://api.together.xyz/v1"


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
        provider_label="together",
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
        provider_label="together",
    )
