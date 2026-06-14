"""Public context-cache surface — ContextCacheHandle.

Some vendors (Gemini today, more later) let you create a *standalone*
cache of prompt content that lives outside any single call: a long
document, a system instruction, retrieval context. Subsequent
generate() calls reference the cache by ID and pay a steep discount
on the cached portion of input tokens.

This differs from the in-call prompt caching surface
(`docs/api_reference.md` → "Vendor-native prompt caching") in two ways:

1. The cache is a named resource with its own lifecycle (`create`,
   `delete`, TTL). You can reuse it across hundreds of unrelated calls.
2. The prompt content is uploaded once at create time, not on every
   call — so even the request-side bandwidth savings show up.

Typical use:

    client = Loom.from_env()

    cache = client.create_context_cache(
        provider="gemini",
        model="gemini-2.5-flash",
        contents="…fifty pages of policy text…",
        system_instruction="You are a compliance assistant.",
        ttl_seconds=600,
    )

    # Pass cache.id through `params={"cached_content": cache.id}` on each call.
    result = client.generate(
        provider="gemini", modality="text", model="gemini-2.5-flash",
        prompt="Does clause 4.2 apply to subcontractors?",
        params={"cached_content": cache.id},
    )

    # When done:
    client.delete_context_cache(cache)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextCacheHandle:
    """Vendor-agnostic handle for a created context cache.

    `id` is the vendor-side identifier (Gemini returns names like
    `cachedContents/abc123`). Pass it through `params={"cached_content": id}`
    on subsequent `generate()` calls to reference the cache.
    """

    id: str
    provider: str
    model: str
    display_name: str | None = None
    ttl_seconds: float | None = None
    _module: Any = None
    _context_factory: Any = None

    def delete(self) -> None:
        """Best-effort delete of the underlying vendor resource."""
        self._call_with_ctx(lambda: self._module.delete(self.id))

    def refresh(self) -> dict[str, Any]:
        """Re-fetch metadata from the vendor — returns the raw vendor dict.

        Useful for inspecting `expire_time` and TTL extension. Not all
        adapters implement this; raises AttributeError if missing.
        """
        return self._call_with_ctx(lambda: self._module.get(self.id))

    def _call_with_ctx(self, fn):
        if self._context_factory is None:
            return fn()
        from loom import _context

        with _context.use(self._context_factory()):
            return fn()


__all__ = ["ContextCacheHandle"]
