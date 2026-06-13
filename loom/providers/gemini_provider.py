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

def _text(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    resp = _client().models.generate_content(
        model=model, contents=prompt, **(params or {})
    )
    out = text_response(getattr(resp, "text", "") or "")
    usage = getattr(resp, "usage_metadata", None)
    if usage is not None:
        inp = int(getattr(usage, "prompt_token_count", 0) or 0)
        outp = int(getattr(usage, "candidates_token_count", 0) or 0)
        out["usage"] = {
            "input_tokens": inp,
            "output_tokens": outp,
            "total_tokens": int(
                getattr(usage, "total_token_count", inp + outp) or 0
            ),
        }
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
