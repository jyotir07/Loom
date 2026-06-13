"""Structured per-call logging."""

import logging

from loom import Loom


def test_successful_call_logs_at_info(monkeypatch, caplog):
    def fake_generate(provider, modality, model, params, prompt):
        return {
            "kind": "text",
            "text": "ok",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})

    with caplog.at_level(logging.INFO, logger="loom"):
        client.generate(
            provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
        )

    records = [r for r in caplog.records if r.name == "loom"]
    assert len(records) == 1
    extras = records[0].__dict__.get("loom") or {}
    assert extras["provider"] == "openai"
    assert extras["modality"] == "text"
    assert extras["model"] == "gpt-4o-mini"
    assert extras["input_tokens"] == 10
    assert extras["output_tokens"] == 5
    assert extras["ok"] is True
    assert extras["cost_usd"] is not None


def test_failed_call_logs_at_warning(monkeypatch, caplog):
    def fake_generate(provider, modality, model, params, prompt):
        raise RuntimeError("boom")

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})

    with caplog.at_level(logging.WARNING, logger="loom"):
        try:
            client.generate(
                provider="openai",
                modality="text",
                model="gpt-4o-mini",
                prompt="hi",
            )
        except RuntimeError:
            pass

    records = [r for r in caplog.records if r.name == "loom"]
    assert any(
        (r.__dict__.get("loom") or {}).get("ok") is False for r in records
    )
