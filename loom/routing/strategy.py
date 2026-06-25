"""RoutingStrategy — the named ways Loom can order provider candidates.

A strategy is just an intent label. Turning it into an ordered list of
candidates is the `StrategySelector`'s job (see `selector.py`); this
module only defines the vocabulary.

The enum is `str`-based so a strategy compares equal to its wire name
(`RoutingStrategy.CHEAPEST == "cheapest"`), which lets callers pass a
plain string (`router="cheapest"`) or the enum interchangeably.
"""

from __future__ import annotations

from enum import Enum
from typing import Union


class RoutingStrategy(str, Enum):
    """Built-in routing strategies.

    - ``CHEAPEST``         — lowest estimated price first.
    - ``FASTEST``          — lowest latency first (live latency, else class).
    - ``HIGHEST_QUALITY``  — strongest quality tier first.
    - ``BALANCED``         — a normalized blend of quality, cost, latency.
    """

    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    HIGHEST_QUALITY = "highest_quality"
    BALANCED = "balanced"

    @classmethod
    def coerce(cls, value: "StrategyLike") -> "RoutingStrategy":
        """Accept a RoutingStrategy or its string name; raise on anything else."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                pass
        valid = ", ".join(s.value for s in cls)
        raise ValueError(
            f"unknown routing strategy {value!r}; valid options: {valid}"
        )


# Accepted anywhere a strategy is expected.
StrategyLike = Union[RoutingStrategy, str]


__all__ = ["RoutingStrategy", "StrategyLike"]
