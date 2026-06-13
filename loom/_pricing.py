"""Cost computation.

The catalog stores pricing in INR (project origin is in India). Loom
treats USD as the canonical reporting unit per the roadmap and reports
the local (INR by default) amount as a parallel view.

Conversion is FX-rate based and configurable on the Loom client:

    Loom(local_currency="INR", local_to_usd=0.012)

`local_to_usd` is how many USD one unit of local currency is worth.
At 1 USD ≈ 83 INR, that's ~0.012.
"""

from __future__ import annotations

from typing import Any

from loom._prompt_cache_rates import (
    cache_write_premium_for,
    cached_discount_for,
)
from loom.catalog import Catalog
from loom.types import Cost, Usage


DEFAULT_LOCAL_CURRENCY = "INR"
DEFAULT_LOCAL_TO_USD = 1.0 / 83.0  # ~1 USD per 83 INR


def _find_entry(
    catalog: Catalog, provider: str, modality: str, model_id: str
) -> dict[str, Any] | None:
    try:
        for entry in catalog.models(provider, modality):
            if entry["id"] == model_id:
                return entry
    except Exception:
        return None
    return None


def compute_cost(
    *,
    catalog: Catalog,
    provider: str,
    modality: str,
    model_id: str,
    usage: Usage | None,
    image_count: int = 0,
    local_currency: str = DEFAULT_LOCAL_CURRENCY,
    local_to_usd: float = DEFAULT_LOCAL_TO_USD,
) -> Cost | None:
    """Return a Cost dict for a single call, or None if catalog has no price.

    For text: needs `usage.input_tokens` and `usage.output_tokens`.
    For image: needs `image_count` (defaults to 1 if entry has cost_inr).
    """
    entry = _find_entry(catalog, provider, modality, model_id)
    if entry is None:
        return None

    local_amount: float | None = None

    if modality == "text" and usage is not None:
        # Vendor usage shapes:
        #   - `input_tokens` is the total prompt token count INCLUDING
        #     any cached/cache-write tokens. We have to subtract those
        #     before charging at the full rate.
        #   - `cached_tokens` is the cached-read subset (always a discount).
        #   - `cache_creation_tokens` (Anthropic only) is tokens written
        #     to cache this call (small premium).
        total_input = float(usage.get("input_tokens") or 0)
        cached = float(usage.get("cached_tokens") or 0)
        cache_writes = float(usage.get("cache_creation_tokens") or 0)
        out = float(usage.get("output_tokens") or 0)
        non_cached_input = max(0.0, total_input - cached - cache_writes)

        in_rate = entry.get("input_inr_per_1m")
        out_rate = entry.get("output_inr_per_1m")
        if in_rate is None and out_rate is None:
            return None

        in_rate_f = float(in_rate or 0)
        discount = cached_discount_for(provider)
        premium = cache_write_premium_for(provider)
        input_cost = (
            non_cached_input * in_rate_f
            + cached * in_rate_f * discount
            + cache_writes * in_rate_f * premium
        )
        local_amount = (input_cost + out * float(out_rate or 0)) / 1_000_000.0
    elif modality == "image":
        per_image = entry.get("cost_inr")
        if per_image is None:
            return None
        count = max(image_count, 1)
        local_amount = float(per_image) * count

    if local_amount is None:
        return None

    cost: Cost = {
        "usd": round(local_amount * local_to_usd, 8),
        "local": round(local_amount, 8),
        "local_currency": local_currency,
    }
    return cost
