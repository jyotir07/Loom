"""Dispatch + error-taxonomy tests — offline (no upstream calls)."""

import pytest

import loom
from loom import Loom
from loom.errors import AuthError, ModelNotFoundError, ProviderError


def test_default_module_exports():
    assert hasattr(loom, "generate")
    assert hasattr(loom, "Loom")
    assert hasattr(loom, "Catalog")
    assert hasattr(loom, "LoomError")


def test_from_env_returns_loom():
    client = Loom.from_env()
    assert isinstance(client, Loom)
    assert client.catalog is not None


def test_unknown_provider_raises_model_not_found():
    # Catalog rejects before dispatch even runs.
    client = Loom.from_env()
    with pytest.raises(ModelNotFoundError):
        client.generate(
            provider="ghost", modality="text", model="x", prompt="hi"
        )


def test_unregistered_provider_raises_provider_error():
    # Anthropic is in the catalog but has no Loom adapter in Phase 1.
    client = Loom.from_env()
    with pytest.raises(ProviderError):
        client.generate(
            provider="anthropic",
            modality="text",
            model="claude-haiku-4-5",
            prompt="hi",
        )


def test_openai_without_key_raises_auth_error(monkeypatch):
    client = Loom.from_env()
    # Drop the key after from_env() loads .env, so require_env() trips at
    # generate time regardless of whether a local .env defines the key.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AuthError):
        client.generate(
            provider="openai",
            modality="text",
            model="gpt-4o-mini",
            prompt="hi",
        )


def test_caller_params_override_catalog_defaults(monkeypatch):
    """Caller-provided params should win over the catalog's default params."""
    captured: dict = {}

    def fake_generate(provider, modality, model, params, prompt):
        captured.update(
            provider=provider,
            modality=modality,
            model=model,
            params=params,
            prompt=prompt,
        )
        return {"kind": "image", "images": []}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client = Loom.from_env()
    # gpt-image-1-high's catalog default is quality=high; override to low.
    client.generate(
        provider="openai",
        modality="image",
        model="gpt-image-1-high",
        prompt="cat",
        params={"quality": "low"},
    )
    assert captured["model"] == "gpt-image-1"
    assert captured["params"] == {"quality": "low"}
