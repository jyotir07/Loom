"""RoutingSignals — the unified source of truth for routing decisions.

A routing decision wants two kinds of information about a model:

* **static** metadata seeded in the catalog — `context_window`,
  `quality_tier`, `latency_class`, `capabilities` (see issue #40); and
* **live** runtime signals observed in production — e.g. `latency_ms`
  and `failure_rate` — supplied by a pluggable source that the
  health/observability layer will implement in a later phase.

`RoutingSignals` blends the two into a single dict so that strategies
("fastest", "balanced", "highest_quality", ...) read from *here* and
never from the catalog or the observability store directly. That keeps
the static-vs-live blend free to evolve without touching every strategy.

Merge rule: **live wins when present; otherwise fall back to catalog
metadata.** A live source that only reports `latency_ms` still leaves
the catalog's `quality_tier`/`capabilities` intact.

This module deliberately contains **no** routing logic, strategy
selection, or provider ranking — only signal resolution. Those build on
top of it next.

Example::

    from loom import Catalog
    from loom.routing import RoutingSignals

    signals = RoutingSignals(Catalog())          # NullLiveSignals by default
    signals.for_model("gemini", "text", "gemini-3.1-pro")
    # -> {"context_window": 1000000, "quality_tier": "frontier",
    #     "latency_class": "slow", "capabilities": [...]}

    # Once a live source is wired in, latency_ms / failure_rate appear and
    # override any catalog-derived field they share a key with.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from loom.catalog import Catalog


@runtime_checkable
class LiveSignalSource(Protocol):
    """Supplies live runtime signals for one model, or ``None`` if it has
    nothing recorded yet.

    Concrete implementations (a health registry, observability queries)
    arrive in a later phase. A returned mapping may carry live metrics
    such as ``latency_ms`` and ``failure_rate``, and may also override a
    static field when the runtime knows better. ``None`` (or an absent
    key) means "no opinion — keep the catalog value".
    """

    def get(
        self, provider: str, modality: str, model: str
    ) -> Mapping[str, Any] | None: ...


class NullLiveSignals:
    """Default live source that knows nothing — every lookup returns
    ``None``.

    Used until a real health/observability-backed source is wired in.
    With this source, resolved signals are exactly the catalog metadata.
    """

    def get(
        self, provider: str, modality: str, model: str
    ) -> Mapping[str, Any] | None:
        return None


class RoutingSignals:
    """Resolves the merged routing signals for a model.

    ``static metadata (catalog)``  <- overlaid by ->  ``live signals (source)``
    """

    def __init__(
        self, catalog: Catalog, live: LiveSignalSource | None = None
    ) -> None:
        self._catalog = catalog
        self._live: LiveSignalSource = live if live is not None else NullLiveSignals()

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    @property
    def live(self) -> LiveSignalSource:
        return self._live

    def for_model(
        self, provider: str, modality: str, model: str
    ) -> dict[str, Any]:
        """Return the merged signal dict for a single model.

        Starts from the catalog's static metadata, then overlays any live
        values the source provides. Live values that are ``None`` are
        ignored, so a partially-populated live source still falls back to
        catalog data field-by-field.

        Raises ``ModelNotFoundError`` if the model isn't in the catalog,
        mirroring ``Catalog.metadata()``. The returned dict is freshly
        built — mutating it never affects the catalog or the live source.
        """
        signals: dict[str, Any] = dict(
            self._catalog.metadata(provider, modality, model)
        )
        live = self._live.get(provider, modality, model)
        if live:
            for key, value in live.items():
                if value is not None:
                    signals[key] = value
        return signals


__all__ = ["RoutingSignals", "LiveSignalSource", "NullLiveSignals"]
