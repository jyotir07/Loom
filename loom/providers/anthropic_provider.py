"""Anthropic Claude — native SDK (Messages API).

Anthropic does not ship image generation, so this adapter handles
text only. The catalog "image" modality on `anthropic` exists for UI
consistency but has zero entries.
"""

from __future__ import annotations

from typing import Any

from loom.errors import ProviderError
from loom.providers._common import require_env, text_response

_API_KEY_ENV = "ANTHROPIC_API_KEY"
_DEFAULT_MAX_TOKENS = 1024


def _client():
    from anthropic import Anthropic

    return Anthropic(api_key=require_env(_API_KEY_ENV))


def _async_client():
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=require_env(_API_KEY_ENV))


def _build_kwargs(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    kwargs = dict(params)
    kwargs.setdefault("max_tokens", _DEFAULT_MAX_TOKENS)
    kwargs["model"] = model
    kwargs["messages"] = [{"role": "user", "content": prompt}]
    return kwargs


def _to_text(resp: Any) -> str:
    parts: list[str] = []
    for block in getattr(resp, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _attach_usage(out: dict[str, Any], resp: Any) -> dict[str, Any]:
    usage = getattr(resp, "usage", None)
    if usage is not None:
        inp = int(getattr(usage, "input_tokens", 0) or 0)
        outp = int(getattr(usage, "output_tokens", 0) or 0)
        out["usage"] = {
            "input_tokens": inp,
            "output_tokens": outp,
            "total_tokens": inp + outp,
        }
    return out


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality != "text":
        raise ProviderError(
            f"anthropic provider only supports text — got modality '{modality}'"
        )
    resp = _client().messages.create(**_build_kwargs(model, params, prompt))
    return _attach_usage(text_response(_to_text(resp)), resp)


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality != "text":
        raise ProviderError(
            f"anthropic provider only supports text — got modality '{modality}'"
        )
    resp = await _async_client().messages.create(
        **_build_kwargs(model, params, prompt)
    )
    return _attach_usage(text_response(_to_text(resp)), resp)
