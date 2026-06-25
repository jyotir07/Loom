"""Catalog class + module-level default instance.

The default in-memory dataset lives in `_data.py`. Backends (memory,
YAML, etc.) live in `backends.py` — Catalog accepts either a raw dict
(via `data=`) or any object with a `.load() -> dict` method (via
`backend=`).
"""

from __future__ import annotations

import os
from typing import Any

from loom.catalog._data import CATALOG as _DEFAULT_CATALOG
from loom.catalog._data import METADATA_FIELDS
from loom.catalog.backends import CatalogBackend, MemoryBackend, YamlBackend
from loom.errors import ModelNotFoundError


class Catalog:
    """Catalog of providers, modalities, and models.

    Three construction styles:

        Catalog()                       # bundled default catalog
        Catalog(data=my_dict)            # in-memory dict in Loom's schema
        Catalog(backend=YamlBackend(p))  # any pluggable backend
        Catalog.from_yaml("models.yaml") # convenience for the YAML case

    `data=` wins if both `data` and `backend` are passed.
    """

    #: Recognized optional routing-metadata field names on a model entry.
    #: Exposed so the routing/signals layer (and tests) can name the static
    #: fields without importing the private `_data` module.
    METADATA_FIELDS = METADATA_FIELDS

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        *,
        backend: CatalogBackend | None = None,
    ) -> None:
        if data is not None:
            self._data: dict[str, Any] = data
        elif backend is not None:
            self._data = backend.load()
        else:
            self._data = _DEFAULT_CATALOG

    @classmethod
    def from_yaml(cls, path: str | os.PathLike[str]) -> "Catalog":
        """Build a Catalog from a YAML file."""
        return cls(backend=YamlBackend(path))

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Catalog":
        """Build a Catalog from a dict in Loom's schema."""
        return cls(backend=MemoryBackend(data))

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def providers(self) -> list[str]:
        return list(self._data.keys())

    def modalities(self, provider: str) -> list[str]:
        self._require_provider(provider)
        return list(self._data[provider]["modalities"].keys())

    def models(self, provider: str, modality: str) -> list[dict[str, Any]]:
        self._require_provider(provider)
        modalities = self._data[provider]["modalities"]
        if modality not in modalities:
            raise ModelNotFoundError(
                f"unknown modality '{modality}' for provider '{provider}'"
            )
        return list(modalities[modality])

    def resolve(
        self, provider: str, modality: str, model_id: str
    ) -> tuple[str, dict[str, Any]]:
        """Return (upstream_model_id, extra_params) for a catalog entry.

        Raises ModelNotFoundError if the (provider, modality, model_id)
        triple isn't present.
        """
        for entry in self.models(provider, modality):
            if entry["id"] == model_id:
                upstream = entry.get("model", entry["id"])
                params = dict(entry.get("params") or {})
                return upstream, params
        raise ModelNotFoundError(
            f"unknown model '{model_id}' for {provider}/{modality}"
        )

    def metadata(
        self, provider: str, modality: str, model_id: str
    ) -> dict[str, Any]:
        """Return optional routing metadata for a catalog entry.

        Looks up the (provider, modality, model_id) entry and returns a
        fresh dict containing only the recognized routing-metadata fields
        that are present on it (context_window, quality_tier,
        latency_class, capabilities). A known model that carries no
        metadata returns an empty dict.

        Raises ModelNotFoundError when the triple isn't in the catalog,
        mirroring resolve(). The returned dict is a copy — mutating it
        (including the capabilities list) never touches the catalog.

        This is read-only metadata that *seeds* routing decisions; it
        intentionally does not affect resolve() or the dispatch path.
        """
        for entry in self.models(provider, modality):
            if entry["id"] == model_id:
                meta: dict[str, Any] = {}
                for field in METADATA_FIELDS:
                    if field in entry:
                        value = entry[field]
                        # Copy mutable containers so callers can't mutate
                        # the underlying catalog through the returned dict.
                        if isinstance(value, list):
                            value = list(value)
                        meta[field] = value
                return meta
        raise ModelNotFoundError(
            f"unknown model '{model_id}' for {provider}/{modality}"
        )

    def _require_provider(self, provider: str) -> None:
        if provider not in self._data:
            raise ModelNotFoundError(f"unknown provider '{provider}'")


# Module-level default instance + data + free function, so existing
# call sites that did `from models_catalog import CATALOG, resolve`
# can switch to `from loom.catalog import CATALOG, resolve` and keep
# working unchanged.
CATALOG: dict[str, Any] = _DEFAULT_CATALOG
_default_catalog = Catalog()


def resolve(
    provider: str, modality: str, model_id: str
) -> tuple[str, dict[str, Any]]:
    """Resolve against the default in-memory catalog."""
    return _default_catalog.resolve(provider, modality, model_id)
