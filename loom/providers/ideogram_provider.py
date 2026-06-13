"""Ideogram — REST API at api.ideogram.ai."""

from __future__ import annotations

import asyncio
from typing import Any

import requests

from loom.errors import ProviderError
from loom.providers._common import fetch_image_b64, image_response, require_env

_API_KEY_ENV = "IDEOGRAM_API_KEY"
_URL = "https://api.ideogram.ai/generate"


def _headers() -> dict[str, str]:
    return {
        "Api-Key": require_env(_API_KEY_ENV),
        "Content-Type": "application/json",
    }


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality != "image":
        raise ProviderError(
            f"ideogram provider only supports image — got modality '{modality}'"
        )
    request = {"prompt": prompt, "model": model}
    request.update(params or {})
    body = {"image_request": request}
    resp = requests.post(_URL, json=body, headers=_headers(), timeout=120)
    resp.raise_for_status()
    data = resp.json()
    urls = [item.get("url") for item in (data.get("data") or []) if item.get("url")]
    images = [fetch_image_b64(u) for u in urls]
    return image_response(images)


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return await asyncio.to_thread(generate, modality, model, params, prompt)
