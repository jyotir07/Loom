"""Runtime catalog / registry patching for the Flask demo app.

These helpers exist because the demo UI lets users add a new model (or
a whole new provider) without restarting. They modify the package source
files (`loom/catalog/_data.py`, `loom/providers/__init__.py`) so the
edits survive a restart, then return enough info for the Flask handler
to reload the affected modules in-process.

The helpers are NOT part of the public `loom` library — they only make
sense for the demo app that ships next to them.
"""

from app_patch.catalog_writer import (
    add_catalog_entry,
    rollback_catalog_entry,
)
from app_patch.code_gen import generate_provider_source
from app_patch.registry_writer import add_provider_to_registry

__all__ = [
    "add_catalog_entry",
    "rollback_catalog_entry",
    "generate_provider_source",
    "add_provider_to_registry",
]
