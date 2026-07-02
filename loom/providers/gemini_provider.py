"""Google Gemini — native google-genai SDK.

Handles text via gemini-* models, image via imagen-* and
gemini-*-image-preview models, and video via veo-* models.

For video, we kick off the long-running operation and poll until done.
Polling cadence is conservative (5s); callers who want different
cadence can implement their own loop using the same SDK directly.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loom.errors import ProviderError
from loom.providers._common import (
    fetch_image_b64,
    image_payload,
    image_response,
    require_env,
    text_response,
)

_API_KEY_ENV = "GEMINI_API_KEY"
_POLL_INTERVAL = 5.0
_POLL_TIMEOUT = 600.0


def _client():
    from google import genai

    return genai.Client(api_key=require_env(_API_KEY_ENV))


# ---------------- text ----------------

def _split_text_params(params: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split params into (kwargs forwarded directly, config dict).

    Gemini routes `cached_content` (and other generation-config knobs)
    through a `config={"cached_content": "cachedContents/..."}` kwarg
    rather than a top-level argument. We pop the known config-level
    knobs here so callers can keep the flat Loom-side dict shape.
    """
    from loom._structured import take_response_schema

    rest, schema_spec = take_response_schema(params)
    cfg: dict[str, Any] = {}
    cached_content = rest.pop("cached_content", None)
    if cached_content is not None:
        cfg["cached_content"] = cached_content
    if schema_spec is not None:
        # Native structured output: Gemini enforces the schema itself and
        # returns JSON directly.
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = schema_spec["schema"]
    # If a caller passes an explicit `config` dict, merge our additions
    # on top — caller wins on conflict so they can override.
    explicit_cfg = rest.pop("config", None)
    if isinstance(explicit_cfg, dict):
        merged = {**cfg, **explicit_cfg}
        cfg = merged
    elif explicit_cfg is not None:
        # Non-dict config (e.g. an SDK GenerateContentConfig object) — let
        # it pass through verbatim; we don't try to merge cached_content
        # into a typed object.
        rest["config"] = explicit_cfg
        return rest, {}
    return rest, cfg


def _text(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    rest, cfg = _split_text_params(params)
    kwargs: dict[str, Any] = {"model": model, "contents": prompt, **rest}
    if cfg:
        kwargs["config"] = cfg
    resp = _client().models.generate_content(**kwargs)
    out = text_response(getattr(resp, "text", "") or "")
    usage = getattr(resp, "usage_metadata", None)
    if usage is not None:
        inp = int(getattr(usage, "prompt_token_count", 0) or 0)
        outp = int(getattr(usage, "candidates_token_count", 0) or 0)
        payload: dict[str, int] = {
            "input_tokens": inp,
            "output_tokens": outp,
            "total_tokens": int(
                getattr(usage, "total_token_count", inp + outp) or 0
            ),
        }
        cached = int(getattr(usage, "cached_content_token_count", 0) or 0)
        if cached > 0:
            payload["cached_tokens"] = cached
        out["usage"] = payload
    return out


# ---------------- image ----------------

def _image(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    client = _client()
    if model.startswith("imagen-"):
        resp = client.models.generate_images(
            model=model, prompt=prompt, **(params or {})
        )
        images: list[dict[str, str]] = []
        for gi in getattr(resp, "generated_images", []) or []:
            inner = getattr(gi, "image", None)
            data = getattr(inner, "image_bytes", None) if inner else None
            if data:
                import base64

                images.append(
                    image_payload(
                        mime_type=getattr(inner, "mime_type", "image/png")
                        or "image/png",
                        data_b64=base64.b64encode(data).decode("ascii"),
                    )
                )
        return image_response(images)

    # gemini-*-image-preview: returned as inline parts on generate_content
    resp = client.models.generate_content(
        model=model, contents=prompt, **(params or {})
    )
    images = []
    for cand in getattr(resp, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                import base64

                data = inline.data
                if isinstance(data, bytes):
                    b64 = base64.b64encode(data).decode("ascii")
                else:
                    b64 = str(data)
                images.append(
                    image_payload(
                        mime_type=getattr(inline, "mime_type", "image/png")
                        or "image/png",
                        data_b64=b64,
                    )
                )
    return image_response(images)


# ---------------- video ----------------

def _video(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    client = _client()
    op = client.models.generate_videos(
        model=model, prompt=prompt, **(params or {})
    )
    deadline = time.time() + _POLL_TIMEOUT
    while not getattr(op, "done", False):
        if time.time() > deadline:
            raise ProviderError(f"gemini video op timed out after {_POLL_TIMEOUT}s")
        time.sleep(_POLL_INTERVAL)
        op = client.operations.get(op)

    out: dict[str, Any] = {"kind": "video", "videos": []}
    response = getattr(op, "response", None)
    for v in getattr(response, "generated_videos", []) or []:
        uri = getattr(getattr(v, "video", None), "uri", None)
        if uri:
            out["videos"].append({"uri": uri})
    return out


# ---------------- dispatch ----------------

def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality == "text":
        return _text(model, params, prompt)
    if modality == "image":
        return _image(model, params, prompt)
    if modality == "video":
        return _video(model, params, prompt)
    raise ProviderError(f"gemini provider does not support modality '{modality}'")


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    # google-genai doesn't ship a uniform async client across all surfaces yet —
    # run sync in a thread for now so the AsyncLoom contract is preserved.
    return await asyncio.to_thread(generate, modality, model, params, prompt)
