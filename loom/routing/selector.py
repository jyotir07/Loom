"""StrategySelector — turn a RoutingStrategy into ordered candidates.

This is the routing *engine*. Given a strategy and a modality, it
enumerates the catalog's models, scores each using catalog pricing plus
`RoutingSignals` (quality tier, latency, capabilities), and returns an
ordered ``list[Candidate]`` — best first.

Scoring inputs by strategy:

- ``cheapest``         — estimated price (free models rank first).
- ``fastest``          — live ``latency_ms`` if known, else ``latency_class``.
- ``highest_quality``  — ``quality_tier`` (frontier > standard > cheap > nano).
- ``balanced``         — a normalized blend of quality, cost, and latency.

Models that lack the signal a strategy needs sort to the back
deterministically (unknown price = most expensive, unknown latency =
slowest, unknown quality = lowest), so a sparsely-seeded catalog still
produces a stable, sensible order. Ties break on the candidate label so
ordering is fully deterministic.

Per the issue scope, this selector is standalone — it does **not** touch
``generate()``. Wiring it into the call path comes in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from loom._router import Candidate
from loom.catalog import Catalog
from loom.errors import ModelNotFoundError
from loom.routing.signals import RoutingSignals
from loom.routing.strategy import RoutingStrategy, StrategyLike

# Quality tiers, weakest to strongest.
_QUALITY_RANK: dict[str, int] = {
    "nano": 0,
    "cheap": 1,
    "standard": 2,
    "frontier": 3,
}
_MAX_QUALITY_RANK = 3
_WORST_QUALITY = -1

# Notional latency (ms) for each static latency_class — only the relative
# ordering matters, used when no live latency_ms is available.
_LATENCY_CLASS_MS: dict[str, float] = {
    "fast": 300.0,
    "medium": 900.0,
    "slow": 2500.0,
}

# Blended price proxy assumes a 3:1 input:output token ratio. Absolute
# value is meaningless; only the ordering across candidates is used.
_PRICE_INPUT_WEIGHT = 3.0
_PRICE_OUTPUT_WEIGHT = 1.0

# balanced blend weights (sum to 1.0): quality favored, cost & latency equal.
_BALANCED_WEIGHTS = {"quality": 0.4, "cost": 0.3, "latency": 0.3}

_INF = float("inf")


@dataclass
class _Scored:
    """A candidate plus the metrics used to rank it."""

    candidate: Candidate
    price: float
    latency: float
    quality: int


def _price_of(entry: dict[str, Any]) -> float:
    """Comparable price proxy for a catalog entry (lower is cheaper)."""
    if entry.get("free"):
        return 0.0
    in_rate = entry.get("input_inr_per_1m")
    out_rate = entry.get("output_inr_per_1m")
    if in_rate is not None and out_rate is not None:
        return (_PRICE_INPUT_WEIGHT * in_rate + _PRICE_OUTPUT_WEIGHT * out_rate) / (
            _PRICE_INPUT_WEIGHT + _PRICE_OUTPUT_WEIGHT
        )
    cost_inr = entry.get("cost_inr")
    if cost_inr is not None:
        return float(cost_inr)
    return _INF


def _latency_of(signals: dict[str, Any]) -> float:
    """Comparable latency (ms) for a model (lower is faster)."""
    ms = signals.get("latency_ms")
    if ms is not None:
        return float(ms)
    cls = signals.get("latency_class")
    if cls in _LATENCY_CLASS_MS:
        return _LATENCY_CLASS_MS[cls]
    return _INF


def _quality_of(signals: dict[str, Any]) -> int:
    """Quality rank for a model (higher is better; -1 if unknown)."""
    return _QUALITY_RANK.get(signals.get("quality_tier"), _WORST_QUALITY)


class StrategySelector:
    """Ranks catalog candidates for a given RoutingStrategy."""

    def __init__(
        self, catalog: Catalog, signals: RoutingSignals | None = None
    ) -> None:
        self._catalog = catalog
        self._signals = signals if signals is not None else RoutingSignals(catalog)

    def select(
        self,
        strategy: StrategyLike,
        *,
        modality: str = "text",
        providers: Iterable[str] | None = None,
        capabilities: Iterable[str] | None = None,
    ) -> list[Candidate]:
        """Return candidates ordered best-first for ``strategy``.

        ``providers`` restricts the pool (default: every catalog provider
        offering ``modality``). ``capabilities`` keeps only models whose
        signals advertise all of the named capabilities. Providers that
        don't offer the modality are skipped silently. Returns ``[]`` when
        nothing qualifies.
        """
        strategy = RoutingStrategy.coerce(strategy)
        pool = self._candidate_pool(modality, providers, capabilities)
        if not pool:
            return []

        if strategy is RoutingStrategy.CHEAPEST:
            ranked = sorted(pool, key=lambda s: (s.price, s.candidate.label()))
        elif strategy is RoutingStrategy.FASTEST:
            ranked = sorted(pool, key=lambda s: (s.latency, s.candidate.label()))
        elif strategy is RoutingStrategy.HIGHEST_QUALITY:
            ranked = sorted(
                pool, key=lambda s: (-s.quality, s.price, s.candidate.label())
            )
        else:  # BALANCED
            ranked = self._rank_balanced(pool)

        return [s.candidate for s in ranked]

    # -- internals ----------------------------------------------------------

    def _candidate_pool(
        self,
        modality: str,
        providers: Iterable[str] | None,
        capabilities: Iterable[str] | None,
    ) -> list[_Scored]:
        provider_list: Sequence[str] = (
            list(providers) if providers is not None else self._catalog.providers()
        )
        required_caps = set(capabilities or ())

        pool: list[_Scored] = []
        for provider in provider_list:
            if modality not in self._safe_modalities(provider):
                continue
            for entry in self._catalog.models(provider, modality):
                model_id = entry["id"]
                signals = self._signals.for_model(provider, modality, model_id)
                if required_caps:
                    caps = set(signals.get("capabilities") or ())
                    if not required_caps.issubset(caps):
                        continue
                pool.append(
                    _Scored(
                        candidate=Candidate(provider, modality, model_id),
                        price=_price_of(entry),
                        latency=_latency_of(signals),
                        quality=_quality_of(signals),
                    )
                )
        return pool

    def _safe_modalities(self, provider: str) -> list[str]:
        try:
            return self._catalog.modalities(provider)
        except ModelNotFoundError:
            return []

    def _rank_balanced(self, pool: list[_Scored]) -> list[_Scored]:
        prices = [s.price for s in pool if s.price != _INF]
        latencies = [s.latency for s in pool if s.latency != _INF]
        p_lo, p_hi = (min(prices), max(prices)) if prices else (0.0, 0.0)
        l_lo, l_hi = (min(latencies), max(latencies)) if latencies else (0.0, 0.0)

        def _norm(value: float, lo: float, hi: float) -> float:
            # 0.0 = best (cheapest/fastest), 1.0 = worst. Unknown -> worst.
            if value == _INF:
                return 1.0
            if hi <= lo:
                return 0.0
            return (value - lo) / (hi - lo)

        scored: list[tuple[float, _Scored]] = []
        for s in pool:
            cost_n = _norm(s.price, p_lo, p_hi)
            lat_n = _norm(s.latency, l_lo, l_hi)
            qual_n = s.quality / _MAX_QUALITY_RANK if s.quality >= 0 else 0.0
            # Higher composite is better: reward quality, penalize cost/latency.
            score = (
                _BALANCED_WEIGHTS["quality"] * qual_n
                + _BALANCED_WEIGHTS["cost"] * (1.0 - cost_n)
                + _BALANCED_WEIGHTS["latency"] * (1.0 - lat_n)
            )
            scored.append((score, s))

        scored.sort(key=lambda t: (-t[0], t[1].candidate.label()))
        return [s for _, s in scored]


__all__ = ["StrategySelector"]
