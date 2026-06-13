"""Programmatic api_keys configuration — overrides env vars per-call."""

import pytest

import loom
from loom import Loom
from loom.errors import AuthError


def test_api_keys_override_env(monkeypatch):
    """A key passed to Loom(api_keys=...) wins over the process env."""
    captured: dict = {}

    def fake_generate(provider, modality, model, params, prompt):
        # Pull the key the way a real provider would — through require_env.
        from loom.providers._common import require_env

        captured["key"] = require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key-value")

    client = Loom(api_keys={"OPENAI_API_KEY": "programmatic-key"})
    client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
    )
    assert captured["key"] == "programmatic-key"


def test_api_keys_fall_back_to_env(monkeypatch):
    """If api_keys doesn't have it, require_env reads the process env."""
    captured: dict = {}

    def fake_generate(provider, modality, model, params, prompt):
        from loom.providers._common import require_env

        captured["key"] = require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    monkeypatch.setenv("OPENAI_API_KEY", "env-fallback")

    client = Loom()  # no api_keys
    client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
    )
    assert captured["key"] == "env-fallback"


def test_missing_key_raises_auth_error(monkeypatch):
    """If neither api_keys nor env has the key, AuthError fires."""

    def fake_generate(provider, modality, model, params, prompt):
        from loom.providers._common import require_env

        require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client = Loom()  # no programmatic keys
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AuthError):
        client.generate(
            provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
        )
