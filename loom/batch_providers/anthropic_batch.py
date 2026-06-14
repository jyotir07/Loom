"""Anthropic Message Batches API adapter.

Flow per the Anthropic Message Batches spec:

  1. Build a list of `{custom_id, params}` where `params` is the same
     body shape `messages.create` takes (model, max_tokens, messages, …).
  2. POST to `/v1/messages/batches` via `client.messages.batches.create`.
  3. Poll the batch — `processing_status` transitions
     "in_progress" → "ended". Loom normalizes "ended" → "completed"
     so `BatchHandle.wait()` works uniformly across vendors.
  4. Iterate `client.messages.batches.results(id)` — JSONL stream of
     `{custom_id, result: {type, message|error}}` rows. Per-row failures
     are surfaced as `{"kind": "error", ...}` in-place; the batch as a
     whole still "completes".

Constraints:

- Text only. Anthropic doesn't expose image generation; image requests
  are rejected at submit time.
- A single Loom batch may mix Claude models (each row picks its own).
- Loom forwards the same Loom-side knobs (`cache_system`, `cache_user`,
  `system`) into the batch body that the live adapter consumes, so
  prompt caching works the same in batch as in real-time.
"""

from __future__ import annotations

from typing import Any, Callable

from loom.batch import BatchRequest
from loom.errors import ProviderError
from loom.providers._common import require_env

_API_KEY_ENV = "ANTHROPIC_API_KEY"


def _client():
    from anthropic import Anthropic

    return Anthropic(api_key=require_env(_API_KEY_ENV))


def _body_for(req: BatchRequest, upstream_model: str, merged_params: dict[str, Any]) -> dict[str, Any]:
    """Translate one BatchRequest into an Anthropic message-create body.

    Mirrors the live adapter (`loom.providers.anthropic_provider._build_kwargs`)
    so prompt caching, system blocks, and other Loom-side knobs behave
    identically between real-time and batch.
    """
    if req.modality != "text":
        raise ProviderError(
            f"anthropic batch only supports text — got modality '{req.modality}'"
        )
    # Defer to the live adapter's translator to keep one source of truth.
    from loom.providers.anthropic_provider import _build_kwargs

    return _build_kwargs(upstream_model, dict(merged_params), req.prompt)


# ---------------- public adapter API ----------------

def submit(
    requests: list[BatchRequest],
    resolve: Callable[[str, str, str], tuple[str, dict[str, Any]]],
) -> str:
    if not requests:
        raise ProviderError("anthropic batch requires at least one request")

    modalities = {r.modality for r in requests}
    if modalities != {"text"}:
        raise ProviderError(
            "anthropic batch supports text only — got "
            f"{sorted(modalities)}. File a separate batch per modality."
        )

    seen_ids: set[str] = set()
    payload: list[dict[str, Any]] = []
    for req in requests:
        if req.custom_id in seen_ids:
            raise ProviderError(
                f"duplicate custom_id '{req.custom_id}' in batch"
            )
        seen_ids.add(req.custom_id)

        upstream, catalog_params = resolve(req.provider, req.modality, req.model)
        merged = dict(catalog_params)
        if req.params:
            merged.update(req.params)
        body = _body_for(req, upstream, merged)
        payload.append({"custom_id": req.custom_id, "params": body})

    batch = _client().messages.batches.create(requests=payload)
    return getattr(batch, "id", "") or ""


def status(batch_id: str) -> str:
    """Return a Loom-normalized status string.

    Anthropic uses `processing_status` of "in_progress" or "ended".
    "ended" maps to "completed" — per-row "errored" / "canceled" /
    "expired" outcomes show up in `results()` as per-row error dicts,
    matching how the OpenAI adapter treats partial failures.
    """
    batch = _client().messages.batches.retrieve(batch_id)
    proc = getattr(batch, "processing_status", None) or "unknown"
    if proc == "ended":
        return "completed"
    if proc == "in_progress":
        return "in_progress"
    if proc == "canceling":
        return "in_progress"
    return proc


def cancel(batch_id: str) -> None:
    _client().messages.batches.cancel(batch_id)


# ---------------- result parsing ----------------

def _extract_text(message: Any) -> str:
    """Pull joined text from an Anthropic Message's content blocks."""
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    if not content:
        return ""
    parts: list[str] = []
    for block in content:
        text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _extract_usage(message: Any) -> dict[str, int] | None:
    """Normalize Anthropic usage in the same shape the live adapter uses.

    `input_tokens` is reported as the non-cached portion; we sum it with
    cache reads + cache writes so Loom's single pricing formula works.
    """
    usage = message.get("usage") if isinstance(message, dict) else getattr(message, "usage", None)
    if usage is None:
        return None

    def _g(key: str) -> int:
        if isinstance(usage, dict):
            return int(usage.get(key, 0) or 0)
        return int(getattr(usage, key, 0) or 0)

    non_cached = _g("input_tokens")
    cache_read = _g("cache_read_input_tokens")
    cache_write = _g("cache_creation_input_tokens")
    outp = _g("output_tokens")
    total_input = non_cached + cache_read + cache_write

    payload: dict[str, int] = {
        "input_tokens": total_input,
        "output_tokens": outp,
        "total_tokens": total_input + outp,
    }
    if cache_read > 0:
        payload["cached_tokens"] = cache_read
    if cache_write > 0:
        payload["cache_creation_tokens"] = cache_write
    return payload


def _parse_row(row: Any) -> dict[str, Any]:
    """Map one Anthropic batch result row to a Loom response dict.

    Each row shape:

        {
            "custom_id": str,
            "result": {
                "type": "succeeded" | "errored" | "canceled" | "expired",
                "message": {...}      # if succeeded
                "error":   {...}      # if errored
            }
        }
    """
    # Anthropic's SDK returns typed objects; accept either dict or attr style.
    def _g(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    custom_id = _g(row, "custom_id")
    result = _g(row, "result")
    rtype = _g(result, "type") if result is not None else None

    if rtype == "succeeded":
        message = _g(result, "message")
        out: dict[str, Any] = {
            "kind": "text",
            "text": _extract_text(message),
            "custom_id": custom_id,
        }
        usage = _extract_usage(message)
        if usage is not None:
            out["usage"] = usage
        return out

    if rtype == "errored":
        err = _g(result, "error") or {}
        msg = _g(err, "message") or str(err)
        code = _g(err, "type")
        return {
            "kind": "error",
            "error": msg,
            "code": code,
            "custom_id": custom_id,
        }

    # canceled / expired — surface as per-row errors with a code.
    return {
        "kind": "error",
        "error": f"row ended in status '{rtype}'",
        "code": rtype,
        "custom_id": custom_id,
    }


def results(
    batch_id: str, requests: list[BatchRequest]
) -> list[dict[str, Any]]:
    """Iterate the vendor results stream, align to caller's request order."""
    client = _client()
    by_custom_id: dict[str, dict[str, Any]] = {}

    for row in client.messages.batches.results(batch_id):
        parsed = _parse_row(row)
        cid = parsed.get("custom_id")
        if cid is None:
            continue
        by_custom_id[cid] = parsed

    aligned: list[dict[str, Any]] = []
    for req in requests:
        item = by_custom_id.get(req.custom_id)
        if item is None:
            aligned.append({
                "kind": "error",
                "error": "no result row for this request in the batch output",
                "custom_id": req.custom_id,
            })
        else:
            aligned.append(item)
    return aligned
