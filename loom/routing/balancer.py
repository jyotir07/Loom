"""LoadBalancer — spread requests across a pool of providers.

Routing (``StrategySelector``) answers *"which model is best?"* and always
lands on the same top choice. A load balancer answers a different question
— *"of these equally-acceptable providers, which one should take this
request?"* — so traffic is distributed instead of hammering one provider.

Four strategies:

- ``round_robin``    — cycle through the pool in order, one provider per call.
- ``weighted``       — random pick proportional to configured weights.
- ``least_latency``  — the provider with the lowest observed latency
                       (from :class:`HealthRegistry`).
- ``least_failures`` — the provider with the fewest recorded failures
                       (from :class:`HealthRegistry`).

Health-awareness: a :class:`HealthRegistry` filters the pool to providers
whose circuit is not open before any strategy runs. If *every* provider is
unavailable the full pool is used rather than returning nothing — a
degraded provider beats no provider at all (mirroring the selector).

This module only *picks a provider*. Turning that into a concrete model
and dispatching is the client's job (see ``Loom._auto_select``). Routing
strategies and fallback are untouched by this class.
"""

from __future__ import annotations

import random
import threading
from enum import Enum
from typing import Iterable, Mapping, Union

from loom.routing.health import HealthRegistry

_INF = float("inf")


class BalancingStrategy(str, Enum):
    """How a :class:`LoadBalancer` distributes requests across providers."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_LATENCY = "least_latency"
    LEAST_FAILURES = "least_failures"

    @classmethod
    def coerce(cls, value: "BalancingLike") -> "BalancingStrategy":
        """Accept either an enum member or its string name."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(
                f"unknown balancing strategy {value!r}; expected one of: {valid}"
            ) from None


BalancingLike = Union[BalancingStrategy, str]


class LoadBalancer:
    """Distributes requests across a fixed pool of providers.

    Args:
        strategy: one of the :class:`BalancingStrategy` values (or its
            string name). Defaults to ``round_robin``.
        providers: the ordered provider pool. Required for every strategy
            except ``weighted``, which derives its pool from ``weights``.
        weights: ``{provider: weight}`` for the ``weighted`` strategy; all
            weights must be positive. Ignored by other strategies (but, if
            given, supplies their pool when ``providers`` is omitted).
        rng: random source for ``weighted`` (injectable for tests).
    """

    def __init__(
        self,
        strategy: BalancingLike = BalancingStrategy.ROUND_ROBIN,
        *,
        providers: Iterable[str] | None = None,
        weights: Mapping[str, float] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.strategy = BalancingStrategy.coerce(strategy)

        if weights is not None:
            if not weights:
                raise ValueError("weights must be a non-empty mapping")
            for provider, weight in weights.items():
                if weight <= 0:
                    raise ValueError(
                        f"weight for {provider!r} must be positive, got {weight!r}"
                    )
            self.weights: dict[str, float] | None = dict(weights)
        else:
            self.weights = None

        if self.strategy is BalancingStrategy.WEIGHTED:
            if self.weights is None:
                raise ValueError(
                    "weighted strategy requires weights={provider: weight}"
                )
            pool = list(self.weights)
        elif providers is not None:
            pool = list(providers)
        elif self.weights is not None:
            pool = list(self.weights)
        else:
            raise ValueError(
                f"{self.strategy.value} strategy requires providers=[...]"
            )
        if not pool:
            raise ValueError("provider pool must be non-empty")
        self.providers = pool

        self._rng = rng if rng is not None else random.Random()
        self._lock = threading.Lock()
        self._rr_index = 0

    def pick(
        self,
        health: HealthRegistry | None = None,
        *,
        providers: Iterable[str] | None = None,
    ) -> str | None:
        """Choose one provider for the next request.

        ``providers`` overrides the configured pool for this call (e.g. to
        restrict to providers a catalog actually offers). Open-circuit
        providers are filtered via ``health`` first; if that leaves nothing,
        the unfiltered pool is used. Returns ``None`` only for an empty pool.
        """
        pool = list(providers) if providers is not None else list(self.providers)
        if not pool:
            return None
        candidates = self._available(pool, health)

        if self.strategy is BalancingStrategy.ROUND_ROBIN:
            return self._round_robin(candidates)
        if self.strategy is BalancingStrategy.WEIGHTED:
            return self._weighted(candidates)
        if self.strategy is BalancingStrategy.LEAST_LATENCY:
            return self._least_latency(candidates, health)
        return self._least_failures(candidates, health)

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _available(pool: list[str], health: HealthRegistry | None) -> list[str]:
        if health is None:
            return pool
        healthy = health.healthy(pool)
        return healthy if healthy else pool  # no-strand fallback

    def _round_robin(self, candidates: list[str]) -> str:
        with self._lock:
            chosen = candidates[self._rr_index % len(candidates)]
            self._rr_index += 1
            return chosen

    def _weighted(self, candidates: list[str]) -> str:
        weights = [self.weights.get(p, 0.0) for p in candidates] if self.weights else []
        total = sum(weights)
        if total <= 0:
            # No positive weight among the healthy subset — pick uniformly.
            return self._rng.choice(candidates)
        threshold = self._rng.random() * total
        upto = 0.0
        for provider, weight in zip(candidates, weights):
            upto += weight
            if threshold < upto:
                return provider
        return candidates[-1]  # float rounding guard

    def _least_latency(
        self, candidates: list[str], health: HealthRegistry | None
    ) -> str:
        if health is None:
            return candidates[0]

        def key(provider: str) -> tuple[float, str]:
            latency = health.status(provider).latency_ms
            return (_INF if latency is None else latency, provider)

        return min(candidates, key=key)

    def _least_failures(
        self, candidates: list[str], health: HealthRegistry | None
    ) -> str:
        if health is None:
            return candidates[0]

        def key(provider: str) -> tuple[int, str]:
            return (health.status(provider).failures, provider)

        return min(candidates, key=key)


__all__ = ["LoadBalancer", "BalancingStrategy", "BalancingLike"]
