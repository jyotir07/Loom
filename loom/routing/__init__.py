"""Loom routing layer.

Today this package holds only the shared *signals* layer
(`RoutingSignals`) — the single source of truth that routing strategies
will read from. Strategy selection, provider ranking, and health-backed
live signals land in later phases and will live alongside it here.
"""

from loom.routing.signals import (
    LiveSignalSource,
    NullLiveSignals,
    RoutingSignals,
)

__all__ = ["RoutingSignals", "LiveSignalSource", "NullLiveSignals"]
