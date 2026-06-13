"""Stable cache/dedup key for a generate() call.

The same inputs must always produce the same key, across runs and
across processes — so we hash a canonical JSON form of the inputs.
Param ordering is not stable across callers, so we sort recursively.

Used by:
  - loom._cache    : key into the response cache
  - loom._dedup    : key for single-flight coalescing of concurrent calls
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canonicalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(x) for x in obj]
    return obj


def call_key(
    *,
    provider: str,
    modality: str,
    model: str,
    prompt: str,
    params: dict[str, Any] | None,
) -> str:
    """Return a stable 64-char hex key for a generate() call."""
    payload = {
        "v": 1,  # bump if the key shape ever changes
        "provider": provider,
        "modality": modality,
        "model": model,
        "prompt": prompt,
        "params": _canonicalize(params or {}),
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
