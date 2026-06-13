"""Shared adapter for vendors that speak the OpenAI chat-completions wire shape.

Mistral, DeepSeek, xAI, MiniMax, Z.AI, Perplexity, Together, Kimi/Moonshot
all expose this API at a different base URL. A vendor module just imports
`chat_text` and passes its base URL + env var name.
"""

from __future__ import annotations

from typing import Any

from loom.errors import ProviderError
from loom.providers._common import require_env, text_response


def _attach_usage(out: dict[str, Any], resp: Any) -> dict[str, Any]:
    usage = getattr(resp, "usage", None)
    if usage is not None:
        out["usage"] = {
            "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }
    return out


def chat_text(
    *,
    api_key_env: str,
    base_url: str | None,
    model: str,
    params: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Single-turn chat completion -> {kind: text, text: ..., usage: ...}."""
    from openai import OpenAI

    client = OpenAI(api_key=require_env(api_key_env), base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **params,
    )
    return _attach_usage(
        text_response(resp.choices[0].message.content or ""),
        resp,
    )


async def achat_text(
    *,
    api_key_env: str,
    base_url: str | None,
    model: str,
    params: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Async sibling of chat_text — uses AsyncOpenAI."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=require_env(api_key_env), base_url=base_url)
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **params,
    )
    return _attach_usage(
        text_response(resp.choices[0].message.content or ""),
        resp,
    )


def text_only(
    *,
    api_key_env: str,
    base_url: str | None,
    modality: str,
    model: str,
    params: dict[str, Any],
    prompt: str,
    provider_label: str,
) -> dict[str, Any]:
    """Convenience: dispatch a (modality, ...) call from a text-only provider."""
    if modality != "text":
        raise ProviderError(
            f"{provider_label} provider only supports text — got modality '{modality}'"
        )
    return chat_text(
        api_key_env=api_key_env,
        base_url=base_url,
        model=model,
        params=params,
        prompt=prompt,
    )


async def atext_only(
    *,
    api_key_env: str,
    base_url: str | None,
    modality: str,
    model: str,
    params: dict[str, Any],
    prompt: str,
    provider_label: str,
) -> dict[str, Any]:
    if modality != "text":
        raise ProviderError(
            f"{provider_label} provider only supports text — got modality '{modality}'"
        )
    return await achat_text(
        api_key_env=api_key_env,
        base_url=base_url,
        model=model,
        params=params,
        prompt=prompt,
    )
