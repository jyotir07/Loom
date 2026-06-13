"""Black Forest Labs (Flux) — async-polling HTTP API at api.bfl.ai.

BFL returns a polling URL on the create call; we poll until the
result is ready (or timeout), then fetch the image and return it
in the unified shape.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import requests

from loom.errors import ProviderError
from loom.providers._common import fetch_image_b64, image_response, require_env

_API_KEY_ENV = "BFL_API_KEY"
_BASE_URL = "https://api.bfl.ai/v1"
_POLL_INTERVAL = 1.0
_POLL_TIMEOUT = 180.0


def _headers() -> dict[str, str]:
    return {
        "x-key": require_env(_API_KEY_ENV),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _kickoff(model: str, params: dict[str, Any], prompt: str) -> dict[str, Any]:
    body = {"prompt": prompt, **(params or {})}
    resp = requests.post(
        f"{_BASE_URL}/{model}", json=body, headers=_headers(), timeout=60
    )
    resp.raise_for_status()
    return resp.json()


def _poll(polling_url: str) -> dict[str, Any]:
    deadline = time.time() + _POLL_TIMEOUT
    headers = _headers()
    while True:
        if time.time() > deadline:
            raise ProviderError(f"bfl polling timed out after {_POLL_TIMEOUT}s")
        r = requests.get(polling_url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = (data.get("status") or "").lower()
        if status == "ready":
            return data
        if status in {"error", "failed", "content_moderated", "request_moderated"}:
            raise ProviderError(f"bfl job failed: status={status}, payload={data}")
        time.sleep(_POLL_INTERVAL)


def _result_to_images(data: dict[str, Any]) -> list[dict[str, str]]:
    result = data.get("result") or {}
    sample = result.get("sample")
    if sample:
        return [fetch_image_b64(sample)]
    return []


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality != "image":
        raise ProviderError(
            f"bfl provider only supports image — got modality '{modality}'"
        )
    kicked = _kickoff(model, params, prompt)
    polling_url = kicked.get("polling_url")
    if not polling_url:
        raise ProviderError(f"bfl create returned no polling_url: {kicked}")
    final = _poll(polling_url)
    return image_response(_result_to_images(final))


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return await asyncio.to_thread(generate, modality, model, params, prompt)
