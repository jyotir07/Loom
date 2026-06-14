"""Gemini context cache adapter — google-genai CachedContent resource.

Wraps `client.caches.create / delete / get`. Contents may be a plain
string (wrapped as a single user-role text part), a list of dicts
matching Gemini's Content shape, or any value the SDK already accepts.
"""

from __future__ import annotations

from typing import Any

from loom.providers._common import require_env

_API_KEY_ENV = "GEMINI_API_KEY"


def _client():
    from google import genai

    return genai.Client(api_key=require_env(_API_KEY_ENV))


def _normalize_contents(contents: Any) -> Any:
    """Wrap a bare string as a Gemini Content list; pass everything else through."""
    if isinstance(contents, str):
        return [{"role": "user", "parts": [{"text": contents}]}]
    return contents


def _config_dict(
    *,
    contents: Any,
    system_instruction: Any | None,
    ttl_seconds: float | None,
    display_name: str | None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {"contents": _normalize_contents(contents)}
    if system_instruction is not None:
        cfg["system_instruction"] = system_instruction
    if ttl_seconds is not None:
        # Gemini accepts a duration string ("300s") or a Duration message.
        cfg["ttl"] = f"{int(ttl_seconds)}s"
    if display_name is not None:
        cfg["display_name"] = display_name
    return cfg


def create(
    model: str,
    *,
    contents: Any,
    system_instruction: Any | None = None,
    ttl_seconds: float | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    cfg = _config_dict(
        contents=contents,
        system_instruction=system_instruction,
        ttl_seconds=ttl_seconds,
        display_name=display_name,
    )
    resp = _client().caches.create(model=model, config=cfg)
    # google-genai returns a CachedContent with `name` (resource name) and
    # optionally `display_name`, `expire_time`, etc. Treat anything past
    # `id` + `display_name` as best-effort metadata.
    return {
        "id": getattr(resp, "name", "") or "",
        "display_name": getattr(resp, "display_name", None),
        "expire_time": getattr(resp, "expire_time", None),
        "model": model,
    }


def delete(cache_id: str) -> None:
    _client().caches.delete(name=cache_id)


def get(cache_id: str) -> dict[str, Any]:
    resp = _client().caches.get(name=cache_id)
    return {
        "id": getattr(resp, "name", "") or cache_id,
        "display_name": getattr(resp, "display_name", None),
        "expire_time": getattr(resp, "expire_time", None),
    }
