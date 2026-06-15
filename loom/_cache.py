"""Response cache — pluggable backends.

Cache key is the SHA-256 of the canonical (provider, modality, model,
prompt, params) tuple — see loom._call_key. Hits return a deep copy of
the cached value so callers can't mutate the cached payload.

Backends:

    InMemoryCache(maxsize, ttl)    — LRU + TTL, single-process. Default.
    RedisCache(url=..., ttl=...)   — Redis. Requires `pip install redis`.

Wire on the client:

    Loom(cache=InMemoryCache(maxsize=10_000, ttl=3600))

Per-call opt-out:

    Loom(...).generate(..., use_cache=False)

Image responses are cached too — they're just bytes-as-base64 in the
unified shape, no streaming, so they round-trip cleanly.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Protocol

_logger = logging.getLogger("loom.cache")


class CacheBackend(Protocol):
    """Minimal cache interface. Backends MUST be thread-safe."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def set(
        self, key: str, value: dict[str, Any], ttl: float | None = None
    ) -> None: ...


class InMemoryCache:
    """LRU + TTL cache in a single process. Default backend.

    `maxsize=0` makes it unbounded. `ttl=None` keeps entries indefinitely;
    a positive `ttl` (seconds) expires entries on read.
    """

    def __init__(self, *, maxsize: int = 1024, ttl: float | None = 3600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at > 0 and time.time() > expires_at:
                self._data.pop(key, None)
                return None
            # Mark as recently used.
            self._data.move_to_end(key)
            return copy.deepcopy(value)

    def set(
        self, key: str, value: dict[str, Any], ttl: float | None = None
    ) -> None:
        effective_ttl = ttl if ttl is not None else self.ttl
        expires_at = time.time() + effective_ttl if effective_ttl else 0.0
        with self._lock:
            self._data[key] = (expires_at, copy.deepcopy(value))
            self._data.move_to_end(key)
            if self.maxsize > 0:
                while len(self._data) > self.maxsize:
                    self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


class RedisCache:
    """Redis-backed cache.

    Lazy-imports `redis` so the dependency stays optional. The connection
    is built on first use; failures during get/set are logged and swallowed
    (treat as a miss / no-op) so a Redis outage degrades to no-cache rather
    than failing every request.
    """

    def __init__(
        self,
        *,
        url: str = "redis://localhost:6379/0",
        ttl: float | None = 3600.0,
        prefix: str = "loom:",
    ) -> None:
        self.url = url
        self.ttl = ttl
        self.prefix = prefix
        self._client: Any | None = None

    def _conn(self) -> Any:
        if self._client is None:
            try:
                import redis  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ImportError(
                    "loom.RedisCache requires the `redis` package. "
                    "Install with `pip install loom-weave[redis]` or `pip install redis`."
                ) from exc
            self._client = redis.Redis.from_url(self.url, decode_responses=False)
        return self._client

    def _k(self, key: str) -> str:
        return self.prefix + key

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            blob = self._conn().get(self._k(key))
        except Exception as exc:  # noqa: BLE001 — log and degrade
            _logger.warning("redis cache get failed: %s", exc)
            return None
        if blob is None:
            return None
        try:
            return json.loads(blob)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("redis cache payload not JSON: %s", exc)
            return None

    def set(
        self, key: str, value: dict[str, Any], ttl: float | None = None
    ) -> None:
        effective_ttl = ttl if ttl is not None else self.ttl
        try:
            blob = json.dumps(value)
        except Exception as exc:  # noqa: BLE001 — unserializable payload
            _logger.warning("redis cache set skipped (not JSON-serialisable): %s", exc)
            return
        try:
            if effective_ttl and effective_ttl > 0:
                self._conn().set(self._k(key), blob, ex=int(effective_ttl))
            else:
                self._conn().set(self._k(key), blob)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("redis cache set failed: %s", exc)


__all__ = ["CacheBackend", "InMemoryCache", "RedisCache"]
