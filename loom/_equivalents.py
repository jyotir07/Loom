"""Cross-vendor equivalence map.

Same workload, different vendors. The bundled tier table groups models
that can stand in for each other when one provider is down, rate-limited,
or having a bad latency day.

Tiering is opinionated — picking equivalents is an aesthetic call about
capability, not a benchmark. The defaults below are the obvious pairs
that most teams agree on; if your shop disagrees, build your own:

    from loom import EquivalenceMap, Router

    my_map = EquivalenceMap({
        "text/cheap": [
            ("openai", "text", "gpt-4o-mini"),
            ("deepseek", "text", "deepseek-v3"),
        ],
    })
    router = Router.failover(
        provider="openai", modality="text", model="gpt-4o-mini",
        equivalence=my_map,
    )

The map keys (`"text/cheap"`, `"text/standard"`, ...) are arbitrary tier
labels — they only have meaning to the equivalence map itself. Two
models are equivalent iff they share a tier.
"""

from __future__ import annotations

from typing import Iterable


ModelKey = tuple[str, str, str]  # (provider, modality, model)


# Default tiers. Pulled from the bundled catalog; opinionated but defensible.
# Order within a tier is the preferred fallback order (most-popular first).
DEFAULT_TIERS: dict[str, list[ModelKey]] = {
    # Smallest, cheapest text — single-prompt classify / extract workloads.
    "text/nano": [
        ("openai", "text", "gpt-5-nano"),
        ("openai", "text", "gpt-4.1-nano"),
        ("gemini", "text", "gemini-3.1-flash-lite"),
    ],
    # Workhorse cheap text — the default chat tier.
    "text/cheap": [
        ("openai", "text", "gpt-4o-mini"),
        ("anthropic", "text", "claude-haiku-4-5"),
        ("gemini", "text", "gemini-2.5-flash"),
        ("deepseek", "text", "deepseek-v3"),
    ],
    # Stronger text — reasoning, longer outputs, harder prompts.
    "text/standard": [
        ("openai", "text", "gpt-4o"),
        ("anthropic", "text", "claude-sonnet-4-6"),
        ("gemini", "text", "gemini-2.5-pro"),
    ],
    # Frontier text — only when the budget allows.
    "text/frontier": [
        ("openai", "text", "gpt-5"),
        ("anthropic", "text", "claude-opus-4-7"),
        ("gemini", "text", "gemini-3.1-pro"),
    ],
}


class EquivalenceMap:
    """Look up cross-vendor equivalents for a (provider, modality, model)."""

    def __init__(self, tiers: dict[str, Iterable[ModelKey]] | None = None) -> None:
        raw = tiers if tiers is not None else DEFAULT_TIERS
        self._tiers: dict[str, list[ModelKey]] = {
            name: [tuple(m) for m in members] for name, members in raw.items()  # type: ignore[misc]
        }
        # Reverse index — (provider, modality, model) -> tier name.
        self._index: dict[ModelKey, str] = {}
        for tier_name, members in self._tiers.items():
            for key in members:
                # First tier wins if a model is listed in two tiers (shouldn't
                # happen, but be deterministic about it).
                self._index.setdefault(key, tier_name)

    def tier_of(self, provider: str, modality: str, model: str) -> str | None:
        return self._index.get((provider, modality, model))

    def equivalents_of(
        self, provider: str, modality: str, model: str
    ) -> list[ModelKey]:
        """Return the tier-mates of (provider, modality, model), excluding itself.

        Empty list if the model is not in any tier — callers can treat that
        as "no failover available" and use the starting model on its own.
        """
        tier = self.tier_of(provider, modality, model)
        if tier is None:
            return []
        return [k for k in self._tiers[tier] if k != (provider, modality, model)]

    def tiers(self) -> list[str]:
        return list(self._tiers.keys())


# Lazy singleton — module-level default, used when no explicit map is passed.
_DEFAULT: EquivalenceMap | None = None


def default_map() -> EquivalenceMap:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = EquivalenceMap()
    return _DEFAULT
