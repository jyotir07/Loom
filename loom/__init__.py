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

from loom._loom import Loom, generate
from loom.catalog import Catalog
from loom.errors import (
    AuthError,
    LoomError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
)

__all__ = [
    "Loom",
    "Catalog",
    "generate",
    "LoomError",
    "ProviderError",
    "AuthError",
    "RateLimitError",
    "ModelNotFoundError",
]

__version__ = "0.1.0"
