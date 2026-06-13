"""Smoke tests: every catalog provider has a registered adapter, every
adapter module imports cleanly, and dispatch resolves to a callable.

These do NOT make upstream calls — they verify wiring only. End-to-end
tests for individual vendors go in their own files (gated on API keys).
"""

from __future__ import annotations

import importlib

import pytest

from loom.catalog import CATALOG
from loom.providers import _LAZY, _module_for, available


def test_every_catalog_provider_has_an_adapter():
    """Every provider key in the catalog must be registered in _LAZY."""
    missing = [p for p in CATALOG.keys() if p not in _LAZY]
    assert not missing, f"providers without an adapter: {missing}"


@pytest.mark.parametrize("provider_key", sorted(set(_LAZY.keys())))
def test_each_adapter_module_imports(provider_key):
    """Each registered adapter module imports without crashing."""
    module = importlib.import_module(_LAZY[provider_key])
    assert hasattr(module, "generate"), f"{provider_key} missing generate()"


@pytest.mark.parametrize("provider_key", sorted(set(_LAZY.keys())))
def test_module_for_returns_callable(provider_key):
    module = _module_for(provider_key)
    assert callable(module.generate)


def test_available_lists_registered_providers():
    keys = available()
    # Every catalog provider should be available.
    for p in CATALOG.keys():
        assert p in keys, f"{p} not in available()"
