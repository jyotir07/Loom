"""HealthRegistry — in-memory provider health tracking.

Loom otherwise treats every request in isolation: a provider that just
rate-limited or errored twenty times in a row gets the same treatment as
a healthy one. This registry gives Loom a memory — per-provider latency
(EWMA), success/failure counts, and a circuit-breaker state — so a later
phase can route around providers that are currently struggling.

Circuit breaker states:

    closed     — healthy; requests flow normally.
    open       — too many recent failures (or a rate limit); the provider
                 is "tripped" and should be avoided until its cooldown
                 expires.
    half_open  — the cooldown has elapsed; one trial request is allowed.
                 A success closes the breaker, a failure re-opens it.

Transitions:

    closed   --failures >= threshold-->  open (cooldown = recovery_timeout)
    closed   --rate limit-------------->  open (cooldown = rate_limit_cooldown)
    open     --cooldown elapsed-------->  half_open  (lazily, on read)
    half_open--success---------------->  closed
    half_open--failure---------------->  open (cooldown reset)

This module only *collects and maintains* health data. Wiring it into
routing/selection decisions is deliberately out of scope here.
"""

from __future__ import annotations

import dataclasses
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable


class CircuitState(str, Enum):
    """Circuit-breaker state for a provider."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderHealth:
    """A snapshot of one provider's health."""

    provider: str
    latency_ms: float | None = None  # EWMA of observed success latencies
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    state: CircuitState = CircuitState.CLOSED
    cooldown_until: float | None = None  # clock value; None = no cooldown
    last_error: str | None = None
    last_updated: float | None = None

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def failure_rate(self) -> float:
        return self.failures / self.total if self.total else 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.total if self.total else 0.0


class HealthRegistry:
    """Thread-safe, in-memory store of per-provider health.

    Tunables:
        ewma_alpha          — weight of the newest latency sample (0..1).
        failure_threshold   — consecutive failures that trip the breaker.
        recovery_timeout     — seconds a tripped breaker stays open before
                              allowing a half-open trial.
        rate_limit_cooldown — seconds a rate-limited provider stays open.
        time_fn             — clock source (injectable for tests).
    """

    def __init__(
        self,
        *,
        ewma_alpha: float = 0.3,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        rate_limit_cooldown: float = 60.0,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 0.0 < ewma_alpha <= 1.0:
            raise ValueError("ewma_alpha must be in (0, 1]")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.ewma_alpha = ewma_alpha
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.rate_limit_cooldown = rate_limit_cooldown
        self._now = time_fn
        self._providers: dict[str, ProviderHealth] = {}
        self._lock = threading.Lock()

    # -- recording ----------------------------------------------------------

    def record_success(self, provider: str, *, latency_ms: float | None = None) -> None:
        """Record a successful upstream call, updating EWMA latency and
        closing the breaker (a success means the provider has recovered)."""
        with self._lock:
            h = self._get(provider)
            if latency_ms is not None:
                if h.latency_ms is None:
                    h.latency_ms = float(latency_ms)
                else:
                    a = self.ewma_alpha
                    h.latency_ms = a * float(latency_ms) + (1.0 - a) * h.latency_ms
            h.successes += 1
            h.consecutive_failures = 0
            h.state = CircuitState.CLOSED
            h.cooldown_until = None
            h.last_updated = self._now()

    def record_failure(
        self,
        provider: str,
        *,
        rate_limited: bool = False,
        error: str | None = None,
    ) -> None:
        """Record a failed upstream call.

        A rate limit trips the breaker immediately with `rate_limit_cooldown`.
        Otherwise the breaker trips once `failure_threshold` consecutive
        failures accumulate (or immediately when already half-open).
        """
        with self._lock:
            h = self._get(provider)
            h.failures += 1
            h.consecutive_failures += 1
            h.last_error = error
            h.last_updated = self._now()

            if rate_limited:
                self._trip(h, self.rate_limit_cooldown)
            elif h.state is CircuitState.HALF_OPEN:
                # A trial failed — re-open.
                self._trip(h, self.recovery_timeout)
            elif h.consecutive_failures >= self.failure_threshold:
                self._trip(h, self.recovery_timeout)

    def _trip(self, h: ProviderHealth, cooldown: float) -> None:
        h.state = CircuitState.OPEN
        h.cooldown_until = self._now() + cooldown

    # -- reading ------------------------------------------------------------

    def status(self, provider: str) -> ProviderHealth:
        """Return a snapshot copy of a provider's health (creating an empty
        healthy record if unseen). Mutating the copy never affects the
        registry."""
        with self._lock:
            h = self._get(provider)
            self._resolve(h)
            return dataclasses.replace(h)

    def state(self, provider: str) -> CircuitState:
        """Current circuit state, lazily promoting open -> half_open once
        the cooldown has elapsed."""
        with self._lock:
            h = self._get(provider)
            self._resolve(h)
            return h.state

    def is_available(self, provider: str) -> bool:
        """True unless the breaker is open with an unexpired cooldown.

        Unknown providers are considered available (no evidence of trouble).
        Half-open counts as available — it permits a single trial request.
        """
        with self._lock:
            h = self._get(provider)
            self._resolve(h)
            return h.state is not CircuitState.OPEN

    def snapshot(self) -> dict[str, ProviderHealth]:
        """A copy of every tracked provider's health."""
        with self._lock:
            for h in self._providers.values():
                self._resolve(h)
            return {p: dataclasses.replace(h) for p, h in self._providers.items()}

    def healthy(self, providers: Iterable[str]) -> list[str]:
        """Return the subset of `providers` whose circuit is not open,
        preserving the input order. Unknown providers count as healthy."""
        return [p for p in providers if self.is_available(p)]

    def reset(self, provider: str | None = None) -> None:
        """Clear health for one provider, or all when `provider` is None."""
        with self._lock:
            if provider is None:
                self._providers.clear()
            else:
                self._providers.pop(provider, None)

    # -- internals ----------------------------------------------------------

    def _get(self, provider: str) -> ProviderHealth:
        h = self._providers.get(provider)
        if h is None:
            h = ProviderHealth(provider=provider)
            self._providers[provider] = h
        return h

    def _resolve(self, h: ProviderHealth) -> None:
        """Promote an expired open breaker to half_open (allow a trial)."""
        if (
            h.state is CircuitState.OPEN
            and h.cooldown_until is not None
            and self._now() >= h.cooldown_until
        ):
            h.state = CircuitState.HALF_OPEN


__all__ = ["HealthRegistry", "ProviderHealth", "CircuitState"]
