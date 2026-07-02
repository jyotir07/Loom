"""Structured logging for every Loom call.

One log line per `generate()` call, emitted at INFO on the `loom`
logger. The message is a human-readable summary; the full structured
fields are attached as `record.extra` so log aggregators (JSON
formatters, ELK, Datadog, etc.) can index them directly.

Consumers wire it up like any other stdlib logger:

    import logging
    logging.basicConfig(level=logging.INFO)
    # or, for a JSON formatter, route the "loom" logger to your handler

By default Loom does NOT add handlers — the library follows the
"no surprises" rule. The Phase 1 Flask app already runs `logging.basicConfig`,
so calls become visible there automatically.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.observability.sink import EventSink

logger = logging.getLogger("loom")


def log_call(
    *,
    provider: str,
    modality: str,
    model: str,
    upstream_model: str,
    latency_ms: float,
    result: dict[str, Any] | None,
    error: BaseException | None = None,
    cached: bool = False,
    deduped: bool = False,
    retries: int = 0,
    tags: Any | None = None,
    sink: "EventSink | None" = None,
) -> None:
    usage = (result or {}).get("usage") or {}
    cost = (result or {}).get("cost") or {}
    extra = {
        "provider": provider,
        "modality": modality,
        "model": model,
        "upstream_model": upstream_model,
        "latency_ms": round(latency_ms, 2),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost_usd": cost.get("usd"),
        "cost_local": cost.get("local"),
        "cost_currency": cost.get("local_currency"),
        "ok": error is None,
        "cached": cached,
        "deduped": deduped,
        "retries": retries,
    }
    if tags:
        extra["tags"] = tags
    if error is not None:
        extra["error_type"] = type(error).__name__
        extra["error"] = str(error)
    # Write to the client's own sink first — this is what powers
    # client.analytics(). It's separate from the "loom" logger, so wiring a
    # sink here never mutates global logging state for other consumers.
    if sink is not None:
        try:
            sink.write({**extra, "ts": time.time()})
        except Exception:  # a broken sink must never crash the call
            pass
    if error is not None:
        logger.warning(
            "loom.generate failed: %s/%s %s -> %s (%.0fms)",
            provider,
            modality,
            model,
            type(error).__name__,
            latency_ms,
            extra={"loom": extra},
        )
        return

    cost_str = ""
    if cost:
        cost_str = f" cost={cost.get('usd'):.6f}USD"
    tokens_str = ""
    if usage:
        tokens_str = (
            f" tokens={usage.get('input_tokens', 0)}/{usage.get('output_tokens', 0)}"
        )
    logger.info(
        "loom.generate %s/%s %s -> %s (%.0fms)%s%s",
        provider,
        modality,
        model,
        upstream_model,
        latency_ms,
        tokens_str,
        cost_str,
        extra={"loom": extra},
    )
