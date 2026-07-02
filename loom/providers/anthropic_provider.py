"""Anthropic Claude — native SDK (Messages API).

Anthropic does not ship image generation, so this adapter handles
text only. The catalog "image" modality on `anthropic` exists for UI
consistency but has zero entries.
"""

from __future__ import annotations

import json
from typing import Any

from loom.errors import ProviderError
from loom.providers._common import require_env, text_response

_API_KEY_ENV = "ANTHROPIC_API_KEY"
_DEFAULT_MAX_TOKENS = 1024
# Name of the synthetic tool used to coax structured JSON out of Claude.
_STRUCTURED_TOOL = "loom_structured_output"


def _client():
    from anthropic import Anthropic

    return Anthropic(api_key=require_env(_API_KEY_ENV))


def _async_client():
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=require_env(_API_KEY_ENV))


def _build_kwargs(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Translate Loom-side knobs into the Anthropic Messages API shape.

    Loom-side convenience params (consumed here, not forwarded):

        system          : str | list[dict]  — system prompt. A list is
                          passed through verbatim (callers using
                          cache_control directly own the shape). A
                          string + cache_system=True is wrapped as a
                          single cached text block.
        cache_system    : bool — wrap a string `system` in an
                          {"cache_control": {"type": "ephemeral"}} block.
        cache_user      : bool — same, applied to the user prompt.

    All other params (max_tokens, temperature, etc.) pass through
    unchanged to messages.create.
    """
    from loom._structured import take_response_schema

    kwargs, schema_spec = take_response_schema(params)
    cache_system = bool(kwargs.pop("cache_system", False))
    cache_user = bool(kwargs.pop("cache_user", False))
    system = kwargs.pop("system", None)

    if system is not None:
        if cache_system and isinstance(system, str):
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            kwargs["system"] = system

    if cache_user:
        user_content: Any = [
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        user_content = prompt

    if schema_spec is not None:
        # Native structured output: expose the schema as a single tool and
        # force Claude to call it, so its `input` is guaranteed-shape JSON.
        kwargs["tools"] = [
            {
                "name": _STRUCTURED_TOOL,
                "description": (
                    "Return the result as structured data matching the schema."
                ),
                "input_schema": schema_spec["schema"],
            }
        ]
        kwargs["tool_choice"] = {"type": "tool", "name": _STRUCTURED_TOOL}

    kwargs.setdefault("max_tokens", _DEFAULT_MAX_TOKENS)
    kwargs["model"] = model
    kwargs["messages"] = [{"role": "user", "content": user_content}]
    return kwargs


def _to_text(resp: Any) -> str:
    # Structured output arrives as a tool_use block whose `input` is the
    # schema-shaped object — serialize it to JSON so the shared parser
    # validates it exactly like any other provider's text.
    parts: list[str] = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "tool_use":
            tool_input = getattr(block, "input", None)
            if tool_input is not None:
                return json.dumps(tool_input)
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _attach_usage(out: dict[str, Any], resp: Any) -> dict[str, Any]:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return out
    # Anthropic's `input_tokens` is the NON-cached input portion; cached
    # reads and cache writes are reported separately. To keep one cost
    # formula across all vendors, Loom normalizes input_tokens to TOTAL
    # prompt tokens (non-cached + cache_read + cache_creation).
    non_cached = int(getattr(usage, "input_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    outp = int(getattr(usage, "output_tokens", 0) or 0)
    total_input = non_cached + cache_read + cache_write

    payload: dict[str, int] = {
        "input_tokens": total_input,
        "output_tokens": outp,
        "total_tokens": total_input + outp,
    }
    if cache_read > 0:
        payload["cached_tokens"] = cache_read
    if cache_write > 0:
        payload["cache_creation_tokens"] = cache_write
    out["usage"] = payload
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
