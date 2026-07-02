"""Analytics — a friendly read API over an EventSink.

`client.analytics()` returns one of these, wrapping the client's event
sink and the aggregation functions in `loom.observability.queries`. It
turns "write raw SQL against the sink" into a few named methods:

    analytics = client.analytics()
    analytics.summary()                 # top-line rollup, all time
    analytics.summary(window="24h")     # last 24 hours
    analytics.by_provider()             # per-provider cost / latency
    analytics.by_model()                # per-model breakdown
    analytics.recent(limit=20)          # the latest calls

`window` accepts a named window (`"1h"`, `"24h"`, `"7d"`, `"30d"`,
`"all"`), a raw number of seconds, or ``None`` for all time.
"""

from __future__ import annotations

from typing import Any

from loom.observability import queries
from loom.observability.queries import WINDOWS
from loom.observability.sink import EventSink


def _window_seconds(window: str | int | None) -> int | None:
    """Normalize a window argument to seconds (or None for all time)."""
    if window is None:
        return None
    if isinstance(window, str):
        if window not in WINDOWS:
            valid = ", ".join(WINDOWS)
            raise ValueError(
                f"unknown window {window!r}; expected one of: {valid}, "
                "an integer number of seconds, or None"
            )
        return WINDOWS[window]
    return int(window)


class Analytics:
    """Read-only analytics accessor bound to a single client's event sink."""

    def __init__(self, sink: EventSink) -> None:
        self._sink = sink

    def summary(self, *, window: str | int | None = None) -> dict[str, Any]:
        """Top-line rollup: calls, cost, latency, tokens, retries, and
        cache/dedup/error rates over `window`."""
        return queries.summary(self._sink, window_seconds=_window_seconds(window))

    def by_provider(
        self, *, window: str | int | None = None
    ) -> list[dict[str, Any]]:
        """Per-provider cost, call count, latency, and cache/error rates."""
        return queries.by_provider(
            self._sink, window_seconds=_window_seconds(window)
        )

    def by_model(
        self, *, window: str | int | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Per-(provider, modality, model) breakdown, costliest first."""
        return queries.by_model(
            self._sink, window_seconds=_window_seconds(window), limit=limit
        )

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """The most recent calls, newest first."""
        return queries.recent(self._sink, limit=limit)


__all__ = ["Analytics"]
