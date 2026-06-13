"""Single-flight request deduplication.

If two callers ask for the same (provider, modality, model, prompt,
params) at the same time, we want one upstream call — not two. The
second caller waits for the first to finish and gets the same result.

Sync variant uses threading.Event; async variant uses asyncio.Event.
Both are keyed on the same call_key, so a sync caller and an async
caller racing the same prompt do NOT coalesce (different event loops
and thread models — coordinating across them isn't worth the complexity).

In-flight registry lives per InFlight() instance; the Loom client
holds one. Failures fan out the exception to all waiters.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _SyncSlot:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: BaseException | None = None


@dataclass
class _AsyncSlot:
    event: asyncio.Event
    result: dict[str, Any] | None = None
    error: BaseException | None = None


class InFlight:
    """Tracks in-flight calls and lets duplicate callers wait on them."""

    def __init__(self) -> None:
        self._sync: dict[str, _SyncSlot] = {}
        self._sync_lock = threading.Lock()
        self._async: dict[str, _AsyncSlot] = {}
        self._async_lock = threading.Lock()

    # ---------------- sync ----------------

    def claim_or_wait_sync(self, key: str) -> tuple[bool, _SyncSlot]:
        """Either claim the slot (is_owner=True) or wait on someone else's.

        Returns (is_owner, slot). If is_owner: the caller MUST eventually
        call `finish_sync(key, ...)`. If not: the slot's event is already
        set or will be — read .result / .error after blocking on .event.
        """
        with self._sync_lock:
            existing = self._sync.get(key)
            if existing is not None:
                return False, existing
            slot = _SyncSlot()
            self._sync[key] = slot
            return True, slot

    def finish_sync(
        self,
        key: str,
        *,
        result: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        with self._sync_lock:
            slot = self._sync.pop(key, None)
        if slot is None:
            return
        slot.result = result
        slot.error = error
        slot.event.set()

    # ---------------- async ----------------

    def claim_or_wait_async(self, key: str) -> tuple[bool, _AsyncSlot]:
        with self._async_lock:
            existing = self._async.get(key)
            if existing is not None:
                return False, existing
            slot = _AsyncSlot(event=asyncio.Event())
            self._async[key] = slot
            return True, slot

    def finish_async(
        self,
        key: str,
        *,
        result: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        with self._async_lock:
            slot = self._async.pop(key, None)
        if slot is None:
            return
        slot.result = result
        slot.error = error
        slot.event.set()
