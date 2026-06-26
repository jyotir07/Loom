"""Loom routing layer.

Two pieces today:

* `RoutingSignals` — the shared *signals* layer that blends static
  catalog metadata with live runtime metrics (the single source of
  truth routing reads from).
* `RoutingStrategy` + `StrategySelector` — the routing *engine* that
  turns a strategy into an ordered list of provider candidates.

Both are standalone — wiring them into `generate()` happens in a later
phase.
"""

from loom.routing.health import CircuitState, HealthRegistry, ProviderHealth
from loom.routing.selector import StrategySelector
from loom.routing.signals import (
    LiveSignalSource,
    NullLiveSignals,
    RoutingSignals,
)
from loom.routing.strategy import RoutingStrategy, StrategyLike

__all__ = [
    "RoutingSignals",
    "LiveSignalSource",
    "NullLiveSignals",
    "RoutingStrategy",
    "StrategyLike",
    "StrategySelector",
    "HealthRegistry",
    "ProviderHealth",
    "CircuitState",
]
