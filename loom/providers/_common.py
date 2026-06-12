"""Shared helpers used across provider modules."""

from __future__ import annotations

import base64
import os
from typing import Any

import requests

from loom.errors import AuthError


def require_env(name: str) -> str:
    """Return env var `name` or raise AuthError if missing/blank."""
    value = (os.getenv(name) or "").strip()
    if not value:
        raise AuthError(f"environment variable {name} is required but not set")
    return value


def fetch_image_b64(url: str, timeout: float = 60.0) -> dict[str, str]:
    """Download an image and return it as the unified image payload."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    mime = resp.headers.get("Content-Type", "image/png").split(";")[0].strip()
    return {
        "mime_type": mime,
        "data_b64": base64.b64encode(resp.content).decode("ascii"),
    }


def image_payload(*, mime_type: str, data_b64: str) -> dict[str, str]:
    return {"mime_type": mime_type, "data_b64": data_b64}


def text_response(text: str) -> dict[str, Any]:
    return {"kind": "text", "text": text}


def image_response(images: list[dict[str, str]]) -> dict[str, Any]:
    return {"kind": "image", "images": images}
