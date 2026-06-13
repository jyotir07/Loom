"""OpenAI Batch API adapter.

Flow per the OpenAI Batch spec:

  1. Build a JSONL where each line is a request body wrapped in
     `{custom_id, method, url, body}`.
  2. Upload the JSONL to the Files API with purpose="batch".
  3. Create a batch from that file ID with the desired endpoint
     (`/v1/chat/completions` for text, `/v1/images/generations` for image)
     and a 24h completion_window.
  4. Poll batch.status — "validating" -> "in_progress" -> "completed".
  5. Download output_file_id, parse JSONL, map each row's custom_id back
     to the caller's original request.

A single Loom batch is allowed to mix models within a vendor (OpenAI's
batch endpoint takes one URL per file, but every line picks its own
model). Mixing modalities (text + image) within one batch is NOT
supported — different endpoints — and is rejected at submit time.
"""

from __future__ import annotations

import io
import json
from typing import Any, Callable

from loom.batch import BatchRequest
from loom.errors import ProviderError
from loom.providers._common import require_env

_TEXT_URL = "/v1/chat/completions"
_IMAGE_URL = "/v1/images/generations"


def _client():
    from openai import OpenAI

    return OpenAI(api_key=require_env("OPENAI_API_KEY"))


def _endpoint_for(modality: str) -> str:
    if modality == "text":
        return _TEXT_URL
    if modality == "image":
        return _IMAGE_URL
    raise ProviderError(
        f"openai batch does not support modality '{modality}'"
    )


def _line_for(
    req: BatchRequest,
    upstream_model: str,
    merged_params: dict[str, Any],
) -> dict[str, Any]:
    """Format one JSONL line for the batch input file."""
    if req.modality == "text":
        body = {
            "model": upstream_model,
            "messages": [{"role": "user", "content": req.prompt}],
            **merged_params,
        }
    elif req.modality == "image":
        body = {
            "model": upstream_model,
            "prompt": req.prompt,
            **merged_params,
        }
    else:
        raise ProviderError(
            f"openai batch does not support modality '{req.modality}'"
        )
    return {
        "custom_id": req.custom_id,
        "method": "POST",
        "url": _endpoint_for(req.modality),
        "body": body,
    }


# ---------------- public adapter API ----------------

def submit(
    requests: list[BatchRequest],
    resolve: Callable[[str, str, str], tuple[str, dict[str, Any]]],
    *,
    completion_window: str = "24h",
) -> str:
    """Upload requests as JSONL, create a batch, return the batch id."""
    if not requests:
        raise ProviderError("openai batch requires at least one request")

    modalities = {r.modality for r in requests}
    if len(modalities) > 1:
        raise ProviderError(
            "openai batch can't mix modalities in one submission — "
            f"got {sorted(modalities)}. Split into separate batches."
        )
    modality = modalities.pop()
    endpoint = _endpoint_for(modality)

    seen_ids: set[str] = set()
    buf = io.BytesIO()
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

        line = _line_for(req, upstream, merged)
        buf.write((json.dumps(line) + "\n").encode("utf-8"))
    buf.seek(0)

    client = _client()
    upload = client.files.create(file=("loom-batch.jsonl", buf), purpose="batch")
    batch = client.batches.create(
        input_file_id=upload.id,
        endpoint=endpoint,
        completion_window=completion_window,
    )
    return batch.id


def status(batch_id: str) -> str:
    """Return the vendor-side status string."""
    batch = _client().batches.retrieve(batch_id)
    return getattr(batch, "status", "unknown") or "unknown"


def cancel(batch_id: str) -> None:
    _client().batches.cancel(batch_id)


# ---------------- result parsing ----------------

def _parse_text_response(body: dict[str, Any]) -> dict[str, Any]:
    choices = body.get("choices") or []
    text = ""
    if choices:
        msg = (choices[0] or {}).get("message") or {}
        text = msg.get("content") or ""
    out: dict[str, Any] = {"kind": "text", "text": text}
    usage = body.get("usage") or {}
    if usage:
        out["usage"] = {
            "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "output_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        }
    return out


def _parse_image_response(body: dict[str, Any]) -> dict[str, Any]:
    from loom.providers._common import fetch_image_b64, image_payload

    images: list[dict[str, str]] = []
    for item in body.get("data") or []:
        b64 = item.get("b64_json")
        url = item.get("url")
        if b64:
            images.append(image_payload(mime_type="image/png", data_b64=b64))
        elif url:
            images.append(fetch_image_b64(url))
    return {"kind": "image", "images": images}


def _parse_row(row: dict[str, Any], modality: str) -> dict[str, Any]:
    """Map one JSONL output row to a Loom response dict.

    Each row has:
      - custom_id: str
      - response: { status_code, body } | null on per-row failure
      - error:    { code, message } | null on per-row success
    """
    err = row.get("error")
    if err is not None:
        return {
            "kind": "error",
            "error": err.get("message") or str(err),
            "code": err.get("code"),
            "custom_id": row.get("custom_id"),
        }
    response = row.get("response") or {}
    if (response.get("status_code") or 0) >= 400:
        return {
            "kind": "error",
            "error": json.dumps(response.get("body") or {}),
            "code": response.get("status_code"),
            "custom_id": row.get("custom_id"),
        }
    body = response.get("body") or {}
    if modality == "text":
        out = _parse_text_response(body)
    elif modality == "image":
        out = _parse_image_response(body)
    else:
        out = {"kind": "error", "error": f"unknown modality '{modality}'"}
    out["custom_id"] = row.get("custom_id")
    return out


def results(
    batch_id: str, requests: list[BatchRequest]
) -> list[dict[str, Any]]:
    """Fetch + parse the output file, aligned to the original `requests` order."""
    client = _client()
    batch = client.batches.retrieve(batch_id)
    out_file_id = getattr(batch, "output_file_id", None)
    err_file_id = getattr(batch, "error_file_id", None)

    by_custom_id: dict[str, dict[str, Any]] = {}

    # Modality is uniform across the batch — we validated that at submit().
    modality = requests[0].modality if requests else "text"

    if out_file_id:
        data = client.files.content(out_file_id).read()
        for raw in data.decode("utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            row = json.loads(raw)
            parsed = _parse_row(row, modality)
            by_custom_id[parsed.get("custom_id") or row.get("custom_id")] = parsed

    if err_file_id:
        data = client.files.content(err_file_id).read()
        for raw in data.decode("utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            row = json.loads(raw)
            parsed = _parse_row(row, modality)
            cid = parsed.get("custom_id") or row.get("custom_id")
            # Errors only fill in if we didn't get a successful row for that id.
            by_custom_id.setdefault(cid, parsed)

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
