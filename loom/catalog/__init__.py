"""Catalog — single source of truth for providers, modalities, and models.

Phase 1 ships one backend: an in-memory dict baked into the package
(`loom.catalog._data.CATALOG`). The Catalog class wraps it with a
small API so Phase 2 can drop in YAML / Postgres backends without
touching call sites.
"""

from loom.catalog._catalog import CATALOG, Catalog, resolve

__all__ = ["Catalog", "CATALOG", "resolve"]
