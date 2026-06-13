"""Async dispatch via AsyncLoom + module-level agenerate()."""

import asyncio

import pytest

import loom
from loom import AsyncLoom


def test_async_loom_uses_native_agenerate(monkeypatch):
    captured: dict = {}

    async def fake_agenerate(provider, modality, model, params, prompt):
        captured.update(provider=provider, model=model)
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.agenerate", fake_agenerate)
    client = AsyncLoom(api_keys={"OPENAI_API_KEY": "k"})
    result = asyncio.run(
        client.generate(
            provider="openai",
            modality="text",
            model="gpt-4o-mini",
            prompt="hi",
        )
    )
    assert result["text"] == "ok"
    assert result["provider"] == "openai"
    assert captured["provider"] == "openai"


def test_async_falls_back_to_thread_for_sync_only_provider(monkeypatch):
    """If a provider module has no agenerate, the dispatcher should
    transparently run its sync generate() in a thread."""
    import types

    # Build a synthetic provider module with only `generate`.
    fake_mod = types.ModuleType("fake_provider")

    def sync_generate(modality, model, params, prompt):
        return {"kind": "text", "text": "sync-result"}

    fake_mod.generate = sync_generate  # type: ignore[attr-defined]

    from loom.providers import _LAZY, _LOADED

    _LAZY["fake"] = "fake_provider_path"
    _LOADED["fake"] = fake_mod

    # Make catalog accept "fake"
    from loom.catalog import Catalog

    cat = Catalog.from_mapping(
        {
            "fake": {
                "label": "Fake",
                "modalities": {
                    "text": [{"id": "x", "name": "X"}],
                },
            }
        }
    )

    client = AsyncLoom(catalog=cat, api_keys={})
    result = asyncio.run(
        client.generate(
            provider="fake", modality="text", model="x", prompt="hi"
        )
    )
    assert result["text"] == "sync-result"

    # cleanup
    del _LOADED["fake"]
    del _LAZY["fake"]


def test_module_level_agenerate_exists():
    assert hasattr(loom, "agenerate")
    assert asyncio.iscoroutinefunction(loom.agenerate)
