"""Public batch API — BatchRequest and BatchHandle.

Vendor batch endpoints (OpenAI, Anthropic, Gemini) trade latency for
cost: typical pricing is ~50% off list with a ~24h completion window.
Loom wraps each vendor behind one uniform interface so consumers can
swap between them without changing call shape.

Usage:

    from loom import Loom, BatchRequest

    client = Loom.from_env()
    handle = client.submit_batch([
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="..."),
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="..."),
    ])
    print(handle.id, handle.status())

    # Block until ready (24h default — pass your own poll cadence).
    results = handle.wait(poll_interval=60.0)

    # results is a list in the same order as the request list. Each item
    # is either a normal {"kind": "text"/"image", ...} response or a
    # {"kind": "error", "error": "..."} payload for that one request.

Or one-shot:

    results = client.run_batch([req1, req2, req3])

All requests in a single batch must share `provider`. Cross-vendor
batching means N separate vendor-side jobs and isn't something Loom
hides — file N batches if you need that.

`BatchHandle` is constructed by the dispatcher, not by callers.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from loom.errors import ProviderError


# ---------------- BatchRequest ----------------

@dataclass
class BatchRequest:
    """One entry in a batch submission.

    `custom_id` is what the vendor returns alongside each result so we
    can match outputs back to inputs. Left blank, we generate a UUID.
    Caller-supplied IDs let downstream code key results by domain
    identifier (e.g. row ID, ticket number).
    """

    provider: str
    modality: str
    model: str
    prompt: str
    params: dict[str, Any] | None = None
    custom_id: str = ""

    def __post_init__(self) -> None:
        if not self.custom_id:
            self.custom_id = "loom-" + uuid.uuid4().hex[:16]


# ---------------- BatchHandle ----------------

# Terminal statuses — once we see one of these, polling stops.
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "expired"}


@dataclass
class BatchHandle:
    """Live handle for a submitted batch job.

    Wraps the vendor-side batch ID and the original request list so we
    can fetch results in the caller's original order.
    """

    id: str                         # vendor-side batch id
    provider: str
    requests: list[BatchRequest]    # in caller order; used to align results
    submitted_at: float = field(default_factory=time.time)
    _module: Any = None             # the batch-provider adapter module
    _context_factory: Any = None    # callable returning a LoomContext for keys

    # ---- status / polling ----

    def status(self) -> str:
        """Return the current vendor-side status (single API call)."""
        return self._call_with_ctx(
            lambda: self._module.status(self.id)
        )

    def is_ready(self) -> bool:
        """True iff the batch has reached a terminal state."""
        return self.status() in TERMINAL_STATUSES

    def wait(
        self,
        *,
        poll_interval: float = 30.0,
        timeout: float = 24 * 3600.0,
    ) -> list[dict[str, Any]]:
        """Block until terminal, then return aligned results.

        Raises ProviderError on `failed` / `expired` / `cancelled`, or
        if polling exceeds `timeout`.
        """
        deadline = time.time() + timeout
        while True:
            s = self.status()
            if s == "completed":
                return self.results()
            if s in {"failed", "expired", "cancelled"}:
                raise ProviderError(
                    f"batch {self.id} ended in terminal status '{s}'"
                )
            if time.time() > deadline:
                raise ProviderError(
                    f"batch {self.id} did not finish within {timeout}s "
                    f"(last status: {s})"
                )
            time.sleep(poll_interval)

    def results(self) -> list[dict[str, Any]]:
        """Fetch the results. Raises if the batch is not in `completed`.

        Returned list mirrors `self.requests` element-for-element. Each
        item is either a normal generate() response or
        `{"kind": "error", "error": str, "custom_id": str}` for that
        single failed request.
        """
        return self._call_with_ctx(
            lambda: self._module.results(self.id, self.requests)
        )

    def cancel(self) -> None:
        """Request cancellation of the batch (best-effort, vendor-dependent)."""
        self._call_with_ctx(lambda: self._module.cancel(self.id))

    # ---- internals ----

    def _call_with_ctx(self, fn):
        """Run `fn()` with the parent Loom's api_keys context active."""
        if self._context_factory is None:
            return fn()
        from loom import _context

        with _context.use(self._context_factory()):
            return fn()


__all__ = ["BatchRequest", "BatchHandle", "TERMINAL_STATUSES"]
