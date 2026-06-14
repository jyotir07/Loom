"""Loom — one contract for every AI vendor.

Quick start:

    import loom

    result = loom.generate(
        provider="openai",
        modality="text",
        model="gpt-4o-mini",
        prompt="Say hi in five words.",
    )
    print(result["text"])

Same thing, explicit instance (useful when you want a non-default config):

    from loom import Loom

    client = Loom.from_env()
    result = client.generate(
        provider="openai",
        modality="text",
        model="gpt-4o-mini",
        prompt="Say hi in five words.",
    )
"""

from loom._cache import CacheBackend, InMemoryCache, RedisCache
from loom._loom import AsyncLoom, Loom, agenerate, generate
from loom._retry import RetryPolicy
from loom._router import Candidate, Router
from loom.batch import BatchHandle, BatchRequest
from loom.catalog import Catalog
from loom.errors import (
    AuthError,
    LoomError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
)
from loom.types import (
    Cost,
    ImagePayload,
    ImageResponse,
    TextResponse,
    Usage,
)

__all__ = [
    "Loom",
    "AsyncLoom",
    "Catalog",
    "generate",
    "agenerate",
    "RetryPolicy",
    "CacheBackend",
    "InMemoryCache",
    "RedisCache",
    "BatchRequest",
    "BatchHandle",
    "Router",
    "Candidate",
    "LoomError",
    "ProviderError",
    "AuthError",
    "RateLimitError",
    "ModelNotFoundError",
    "TextResponse",
    "ImageResponse",
    "ImagePayload",
    "Usage",
    "Cost",
]

__version__ = "0.1.0"
