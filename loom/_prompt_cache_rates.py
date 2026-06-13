"""Per-provider prompt-cache pricing multipliers.

These are public vendor pricing facts, not Loom config. Values are
multipliers against the regular input-token rate:

    cached_discount     — cached read tokens cost (rate * discount)
    cache_write_premium — newly written cache tokens cost (rate * premium)

A provider missing from a map gets the default (1.0), meaning Loom won't
discount or surcharge — which is the safe behaviour if a vendor changes
its scheme and we haven't updated the table.

Sources (as of 2026-06):
    OpenAI    — cached input at 50% of base.
    Anthropic — cache reads at 10%, writes at 125%.
    DeepSeek  — cache hits at 10%.
    Gemini    — cache reads at 25% (context caching — not wired yet).
"""

from __future__ import annotations

CACHED_DISCOUNT: dict[str, float] = {
    "openai": 0.5,
    "anthropic": 0.1,
    "deepseek": 0.1,
    "gemini": 0.25,
}

CACHE_WRITE_PREMIUM: dict[str, float] = {
    "anthropic": 1.25,
}


def cached_discount_for(provider: str) -> float:
    return CACHED_DISCOUNT.get(provider, 1.0)


def cache_write_premium_for(provider: str) -> float:
    return CACHE_WRITE_PREMIUM.get(provider, 1.0)
