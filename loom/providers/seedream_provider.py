"""ByteDance Seedream — Volcano Engine ARK images API.

ARK exposes an OpenAI-shape /images/generations endpoint at
ark.cn-beijing.volces.com/api/v3. The OpenAI SDK works against it
when pointed at the right base_url with the ARK API key.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loom.errors import ProviderError
from loom.providers._common import (
    fetch_image_b64,
    image_payload,
    image_response,
    require_env,
)

_API_KEY_ENV = "ARK_API_KEY"
_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def _client():
    from openai import OpenAI

    return OpenAI(api_key=require_env(_API_KEY_ENV), base_url=_BASE_URL)


def _image(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    resp = _client().images.generate(model=model, prompt=prompt, **(params or {}))
    images: list[dict[str, str]] = []
    for item in resp.data or []:
        b64 = getattr(item, "b64_json", None)
        url = getattr(item, "url", None)
        if b64:
            images.append(image_payload(mime_type="image/png", data_b64=b64))
        elif url:
            images.append(fetch_image_b64(url))
    return image_response(images)


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality != "image":
        raise ProviderError(
            f"seedream provider only supports image — got modality '{modality}'"
        )
    return _image(model, params, prompt)


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return await asyncio.to_thread(generate, modality, model, params, prompt)
