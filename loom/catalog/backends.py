"""Catalog backends — pluggable data sources for Catalog.

A backend is anything that yields the catalog dict in Loom's schema
when `.load()` is called. Backends are constructed eagerly but cheap;
`.load()` is allowed to be slow (read a file, hit a database) and is
called by Catalog on first access.

Phase 2 ships two:

    MemoryBackend(data)         — wraps an in-memory dict
    YamlBackend(path)           — reads a YAML file from disk

Postgres lands when an internal project asks for it; the interface is
intentionally narrow so the implementation is a few dozen lines.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol


class CatalogBackend(Protocol):
    """Anything with a load() returning the catalog dict."""

    def load(self) -> dict[str, Any]: ...


class MemoryBackend:
    """Trivial backend that just hands back a dict held in memory."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def load(self) -> dict[str, Any]:
        return self._data


class YamlBackend:
    """Backend that reads a YAML file and parses it into the catalog dict.

    Requires PyYAML (install Loom with the `yaml` extra: `pip install loom-weave[yaml]`).
    The file must match Loom's catalog schema — the same shape as the
    default `loom.catalog._data.CATALOG`.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "loom.catalog.YamlBackend requires PyYAML. "
                "Install with `pip install loom-weave[yaml]` or `pip install pyyaml`."
            ) from exc

        if not self._path.is_file():
            raise FileNotFoundError(f"catalog YAML not found at: {self._path}")
        with self._path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(
                f"catalog YAML at {self._path} must be a mapping at the top level"
            )
        return data


__all__ = ["CatalogBackend", "MemoryBackend", "YamlBackend"]
