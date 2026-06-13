"""Per-call context — flows from Loom.generate() into provider adapters.

Providers don't take an explicit context argument because that would
ripple through every adapter signature and break compatibility with
the Phase 1 contract `generate(modality, model, params, prompt) -> dict`.
Instead, Loom sets a ContextVar before dispatch, providers read it via
`require_env()` (and friends) in `loom.providers._common`, and the
contextvar is reset on return.

ContextVar is async-safe — asyncio.Task copies the context on creation —
so this works the same for AsyncLoom in Phase 2.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class LoomContext:
    """State the providers can see during a single generate() call."""

    api_keys: dict[str, str] = field(default_factory=dict)


_current: ContextVar[LoomContext | None] = ContextVar(
    "loom_current_context", default=None
)


def current() -> LoomContext | None:
    return _current.get()


@contextmanager
def use(context: LoomContext) -> Iterator[LoomContext]:
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)
