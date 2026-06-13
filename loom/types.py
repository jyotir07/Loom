"""Typed shapes for Loom responses.

The dict-shaped responses from `Loom.generate(...)` aren't going away —
existing callers can still use `result["text"]` or `result["images"]`.
These TypedDicts just give IDE autocomplete, mypy/pyright coverage,
and a single place to read the spec.

Every response carries:

  - kind:    "text" | "image"
  - provider: catalog provider key (e.g. "openai")
  - model:    catalog model id the caller asked for
  - upstream_model: the vendor's model id we actually called
  - usage:    token counts (input/output/total), where the provider exposes them
  - cost:     per-call cost in USD plus a configured local-currency view

`usage` and `cost` are optional in Phase 2's early shape because some
providers/modalities (e.g. image gen) don't report tokens.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class Usage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class Cost(TypedDict, total=False):
    usd: float
    local: float
    local_currency: str


class ImagePayload(TypedDict):
    mime_type: str
    data_b64: str


class TextResponse(TypedDict, total=False):
    kind: Literal["text"]
    text: str
    provider: str
    model: str
    upstream_model: str
    usage: Usage
    cost: Cost


class ImageResponse(TypedDict, total=False):
    kind: Literal["image"]
    images: list[ImagePayload]
    provider: str
    model: str
    upstream_model: str
    usage: Usage
    cost: Cost


__all__ = [
    "Usage",
    "Cost",
    "ImagePayload",
    "TextResponse",
    "ImageResponse",
]
