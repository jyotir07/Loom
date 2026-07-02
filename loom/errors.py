"""Error taxonomy.

Phase 1 ships the hierarchy so downstream consumers can write
`except loom.ProviderError` from day one. Phase 2 wires the
provider adapters to actually raise these on upstream failures.
"""


class LoomError(Exception):
    """Base class for every error raised by Loom."""


class ProviderError(LoomError):
    """An upstream provider returned an error we couldn't classify."""


class AuthError(ProviderError):
    """Missing or rejected vendor API key."""


class RateLimitError(ProviderError):
    """Vendor returned a 429 / rate-limit signal."""


class ModelNotFoundError(LoomError):
    """The requested (provider, modality, model) is not in the catalog."""


class StructuredOutputError(LoomError):
    """A `schema=` request could not be satisfied.

    Raised when Pydantic is missing, `schema=` is not a supported schema
    type, or the model's reply can't be parsed/validated against it.
    """
