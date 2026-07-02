"""Structured outputs — provider-agnostic schema= (issue #59). Offline."""

import asyncio

import pytest
from pydantic import BaseModel

from loom import AsyncLoom, Loom, StructuredOutputError
from loom.catalog import Catalog
from loom.providers import supports_structured_output

_DATA = {
    "openai": {
        "label": "OpenAI",
        "modalities": {"text": [{"id": "m", "name": "M"}]},
    },
}


def _catalog():
    return Catalog(data=_DATA)


class User(BaseModel):
    name: str
    age: int


def _fake(text, *, captured=None):
    """Provider fake that returns `text`, optionally recording the prompt."""

    def fake(provider, modality, model, params, prompt):
        if captured is not None:
            captured["prompt"] = prompt
        return {"kind": "text", "text": text}

    return fake


def _client(text, *, captured=None):
    return Loom(catalog=_catalog(), api_keys={}), _fake(text, captured=captured)


# ---------- happy path ----------


def test_schema_returns_validated_instance(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate",
        _fake('{"name": "Ada", "age": 36}'),
    )
    client = Loom(catalog=_catalog(), api_keys={})
    user = client.generate(
        provider="openai", model="m", prompt="Who?", schema=User
    )
    assert isinstance(user, User)
    assert user.name == "Ada"
    assert user.age == 36


def test_schema_parses_fenced_json(monkeypatch):
    fenced = '```json\n{"name": "Ada", "age": 36}\n```'
    monkeypatch.setattr("loom._loom._providers.generate", _fake(fenced))
    client = Loom(catalog=_catalog(), api_keys={})
    user = client.generate(provider="openai", model="m", prompt="x", schema=User)
    assert user.name == "Ada"


def test_schema_parses_json_amid_prose(monkeypatch):
    prose = 'Sure! Here it is: {"name": "Ada", "age": 36} — enjoy.'
    monkeypatch.setattr("loom._loom._providers.generate", _fake(prose))
    client = Loom(catalog=_catalog(), api_keys={})
    user = client.generate(provider="openai", model="m", prompt="x", schema=User)
    assert user.age == 36


def test_schema_augments_prompt(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "loom._loom._providers.generate",
        _fake('{"name": "Ada", "age": 36}', captured=captured),
    )
    client = Loom(catalog=_catalog(), api_keys={})
    client.generate(provider="openai", model="m", prompt="Who?", schema=User)
    sent = captured["prompt"]
    assert "Who?" in sent
    assert "JSON Schema" in sent
    assert "name" in sent and "age" in sent


def test_no_schema_returns_dict(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake("plain text"))
    client = Loom(catalog=_catalog(), api_keys={})
    result = client.generate(provider="openai", model="m", prompt="x")
    assert isinstance(result, dict)
    assert result["text"] == "plain text"


# ---------- validation / parse failures ----------


def test_schema_validation_failure_raises(monkeypatch):
    # Missing required 'age'.
    monkeypatch.setattr(
        "loom._loom._providers.generate", _fake('{"name": "Ada"}')
    )
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError) as exc:
        client.generate(provider="openai", model="m", prompt="x", schema=User)
    assert "validation" in str(exc.value).lower()


def test_schema_non_json_raises(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.generate", _fake("no json here at all")
    )
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError):
        client.generate(provider="openai", model="m", prompt="x", schema=User)


def test_schema_empty_text_raises(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake(""))
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError):
        client.generate(provider="openai", model="m", prompt="x", schema=User)


# ---------- guard rails ----------


def test_schema_must_be_pydantic_model(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake("{}"))
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError):
        client.generate(provider="openai", model="m", prompt="x", schema=str)


def test_schema_rejects_non_text_modality(monkeypatch):
    monkeypatch.setattr("loom._loom._providers.generate", _fake("{}"))
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError):
        client.generate(
            provider="openai", modality="image", model="m",
            prompt="x", schema=User,
        )


def test_missing_pydantic_raises_clear_error(monkeypatch):
    # Simulate pydantic not being installed.
    monkeypatch.setattr("loom._structured._HAS_PYDANTIC", False)
    monkeypatch.setattr("loom._loom._providers.generate", _fake("{}"))
    client = Loom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError) as exc:
        client.generate(provider="openai", model="m", prompt="x", schema=User)
    assert "pydantic" in str(exc.value).lower()


# ---------- provider capability ----------


def test_provider_structured_capability():
    assert supports_structured_output("openai") is True
    assert supports_structured_output("anthropic") is True
    assert supports_structured_output("gemini") is True
    assert supports_structured_output("mistral") is False
    assert supports_structured_output("nonexistent") is False


# ---------- async ----------


def _afake(text):
    async def fake(provider, modality, model, params, prompt):
        return {"kind": "text", "text": text}

    return fake


def test_async_schema_returns_instance(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.agenerate", _afake('{"name": "Ada", "age": 36}')
    )
    client = AsyncLoom(catalog=_catalog(), api_keys={})
    user = asyncio.run(
        client.generate(provider="openai", model="m", prompt="x", schema=User)
    )
    assert isinstance(user, User)
    assert user.name == "Ada"


def test_async_schema_validation_failure_raises(monkeypatch):
    monkeypatch.setattr(
        "loom._loom._providers.agenerate", _afake('{"name": "Ada"}')
    )
    client = AsyncLoom(catalog=_catalog(), api_keys={})
    with pytest.raises(StructuredOutputError):
        asyncio.run(
            client.generate(
                provider="openai", model="m", prompt="x", schema=User
            )
        )
