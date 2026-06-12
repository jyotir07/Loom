"""Catalog class + module-level default instance.

The default in-memory dataset lives in `_data.py`. Phase 2 will add
backends keyed on this same interface (Catalog.providers, .modalities,
.models, .resolve).
"""

from __future__ import annotations

from typing import Any

from loom.catalog._data import CATALOG as _DEFAULT_CATALOG
from loom.errors import ModelNotFoundError


class Catalog:
    """In-memory catalog of providers, modalities, and models.

    Construct with no arguments to use Loom's bundled catalog, or
    pass `data=` to use a custom dict in the same schema.
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data if data is not None else _DEFAULT_CATALOG

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
