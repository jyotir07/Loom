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
)
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
    "EquivalenceMap",
    "HealthRegistry",
    "ProviderHealth",
    "CircuitState",
    "LoadBalancer",
    "BalancingStrategy",
    "CompareReport",
    "CompareResult",
    "CompareSummary",
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
    "KeyVault",
    "InMemoryVault",
    "AWSSecretsManagerVault",
    "GCPSecretManagerVault",
    "HashiCorpVaultBackend",
]

__version__ = "1.0.0"
