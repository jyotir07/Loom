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

v2 — intelligent routing folded into the same call. All additive; the
explicit form above keeps working unchanged:

    client.generate(prompt="Summarize this.")               # fully automatic
    client.generate(providers=["gemini", "openai"], prompt=...)  # preference order
    client.generate(router="cheapest", prompt=...)          # named strategy

    from loom import FallbackPolicy, RoutingStrategy
    client.generate(router=RoutingStrategy.BALANCED,
                    fallback=FallbackPolicy(retries=3), prompt=...)

    from pydantic import BaseModel
    class User(BaseModel):
        name: str
    client.generate(prompt="...", schema=User)              # validated object

    client.compare(providers=["openai", "anthropic"], prompt=...)  # benchmark
    client.analytics().summary()                            # usage metrics

See docs/routing_cookbook.md for the full v2 tour.
"""

from loom._cache import CacheBackend, InMemoryCache, RedisCache
from loom._compare import CompareReport, CompareResult, CompareSummary
from loom._context_cache import ContextCacheHandle
from loom._equivalents import EquivalenceMap
from loom._loom import AsyncLoom, Loom, agenerate, generate
from loom._retry import RetryPolicy
from loom._router import Candidate, FallbackPolicy, Router
from loom.routing import (
    BalancingStrategy,
    CircuitState,
    HealthRegistry,
    LoadBalancer,
    ProviderHealth,
    RoutingStrategy,
)
from loom.batch import BatchHandle, BatchRequest
from loom.catalog import Catalog
from loom.errors import (
    AuthError,
    LoomError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    StructuredOutputError,
)
from loom.observability import Analytics, InMemorySink
from loom.types import (
    Cost,
    ImagePayload,
    ImageResponse,
    TextResponse,
    Usage,
)
from loom.vault import (
    AWSSecretsManagerVault,
    GCPSecretManagerVault,
    HashiCorpVaultBackend,
    InMemoryVault,
    KeyVault,
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
    "ContextCacheHandle",
    "Router",
    "Candidate",
    "FallbackPolicy",
    "RoutingStrategy",
    "EquivalenceMap",
    "HealthRegistry",
    "ProviderHealth",
    "CircuitState",
    "LoadBalancer",
    "BalancingStrategy",
    "CompareReport",
    "CompareResult",
    "CompareSummary",
    "Analytics",
    "InMemorySink",
    "LoomError",
    "ProviderError",
    "AuthError",
    "RateLimitError",
    "ModelNotFoundError",
    "StructuredOutputError",
    "TextResponse",
    "ImageResponse",
    "ImagePayload",
    "Usage",
    "Cost",
    "KeyVault",
    "InMemoryVault",
    "AWSSecretsManagerVault",
    "GCPSecretManagerVault",
    "HashiCorpVaultBackend",
]

__version__ = "2.0.0"
