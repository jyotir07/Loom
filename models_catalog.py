"""Backward-compat shim.

The catalog lives in `loom.catalog` now. This module re-exports CATALOG
and resolve() so existing call sites (seed_db.py, scripts, notebooks)
keep working without edits.

New code should import from `loom.catalog` directly.
"""

from loom.catalog import CATALOG, resolve

__all__ = ["CATALOG", "resolve"]
