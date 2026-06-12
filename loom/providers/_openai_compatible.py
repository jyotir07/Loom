"""Shared adapter for vendors that speak the OpenAI chat-completions wire shape.

Mistral, DeepSeek, xAI, MiniMax, Z.AI, Perplexity, Together, and Seedream
all expose this API at a different base URL. A vendor module just imports
`chat_text` and passes its base URL + env var name.
"""

from __future__ import annotations

from typing import Any

from loom.providers._common import require_env, text_response


def chat_text(
    *,
    api_key_env: str,
    base_url: str | None,
    model: str,
    params: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    """Single-turn chat completion -> {kind: text, text: ...}."""
    from openai import OpenAI

    client = OpenAI(api_key=require_env(api_key_env), base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **params,
    )
    return text_response(resp.choices[0].message.content or "")
