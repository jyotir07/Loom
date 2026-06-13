"""Catalog — single source of truth for providers, modalities, and models.

The default in-memory catalog ships with the package
(`loom.catalog._data.CATALOG`). The Catalog class wraps it and accepts
pluggable backends (see `loom.catalog.backends`).
"""

from loom.catalog._catalog import CATALOG, Catalog, resolve
from loom.catalog.backends import (
    CatalogBackend,
    MemoryBackend,
    YamlBackend,
)

__all__ = [
    "Catalog",
    "CATALOG",
    "resolve",
    "CatalogBackend",
    "MemoryBackend",
    "YamlBackend",
]
