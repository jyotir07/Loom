"""OpenAI provider — chat completions (text) and Images API (image).

Public contract:

    generate(modality, model, params, prompt) -> dict

with the same {"kind": "text" | "image", ...} response shape used
across every Loom provider.
"""

from __future__ import annotations

from typing import Any

from loom.errors import ProviderError
from loom.providers._common import (
    image_payload,
    image_response,
    require_env,
    text_response,
)


def _client():
    from openai import OpenAI

    return OpenAI(api_key=require_env("OPENAI_API_KEY"))


def _text(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    resp = _client().chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **params,
    )
    return text_response(resp.choices[0].message.content or "")


def _image(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    resp = _client().images.generate(model=model, prompt=prompt, **params)

    images: list[dict[str, str]] = []
    for item in resp.data or []:
        b64 = getattr(item, "b64_json", None)
        url = getattr(item, "url", None)
        if b64:
            images.append(image_payload(mime_type="image/png", data_b64=b64))
        elif url:
            from loom.providers._common import fetch_image_b64

            images.append(fetch_image_b64(url))
    return image_response(images)


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality == "text":
        return _text(model, params, prompt)
    if modality == "image":
        return _image(model, params, prompt)
    raise ProviderError(f"openai provider does not support modality '{modality}'")
