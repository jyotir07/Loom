"""Structured outputs — schema= (issues #59, #63). Fully offline.

#59 covers the provider-agnostic interface (parsing/validation); #63
covers the native per-provider implementations + JSON fallback.
"""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from loom import AsyncLoom, Loom, StructuredOutputError
from loom.catalog import Catalog
from loom.providers import _prepare_params, supports_structured_output
from loom._structured import RESPONSE_SCHEMA_KEY

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


# ======================================================================
# #63 — native per-provider implementations + JSON fallback
# ======================================================================

_NATIVE_DATA = {
    "openai": {
        "label": "OpenAI",
        "modalities": {"text": [{"id": "gpt", "name": "GPT"}]},
    },
    "anthropic": {
        "label": "Anthropic",
        "modalities": {"text": [{"id": "claude", "name": "Claude"}]},
    },
    "gemini": {
        "label": "Gemini",
        "modalities": {"text": [{"id": "gem", "name": "Gem"}]},
    },
}


def _native_catalog():
    return Catalog(data=_NATIVE_DATA)


_VALID_JSON = '{"name": "Ada", "age": 36}'


# ---------- dispatch-level reserved-key handling ----------


def test_prepare_params_strips_key_for_unsupported_provider():
    params = {RESPONSE_SCHEMA_KEY: {"name": "User", "schema": {}}, "temperature": 0.5}
    cleaned = _prepare_params("mistral", params)
    assert RESPONSE_SCHEMA_KEY not in cleaned
    assert cleaned["temperature"] == 0.5


def test_prepare_params_keeps_key_for_native_provider():
    params = {RESPONSE_SCHEMA_KEY: {"name": "User", "schema": {}}}
    assert RESPONSE_SCHEMA_KEY in _prepare_params("openai", params)


# ---------- OpenAI native ----------


def test_openai_uses_native_response_format(monkeypatch):
    from loom.providers import openai_provider

    captured: dict = {}

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=_VALID_JSON))],
            usage=None,
        )

    class FakeOpenAI:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=create)
            )

    monkeypatch.setattr(openai_provider, "_client", lambda: FakeOpenAI())
    client = Loom(catalog=_native_catalog(), api_keys={})
    user = client.generate(provider="openai", model="gpt", prompt="x", schema=User)

    assert isinstance(user, User) and user.name == "Ada"
    rf = captured["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "User"
    assert set(rf["json_schema"]["schema"]["properties"]) == {"name", "age"}
    # Reserved key never reaches the SDK.
    assert RESPONSE_SCHEMA_KEY not in captured


# ---------- Anthropic native ----------


def test_anthropic_uses_native_tool(monkeypatch):
    from loom.providers import anthropic_provider

    captured: dict = {}

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="tool_use", input={"name": "Ada", "age": 36})
            ],
            usage=None,
        )

    class FakeAnthropic:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=create)

    monkeypatch.setattr(anthropic_provider, "_client", lambda: FakeAnthropic())
    client = Loom(catalog=_native_catalog(), api_keys={})
    user = client.generate(
        provider="anthropic", model="claude", prompt="x", schema=User
    )

    assert isinstance(user, User) and user.age == 36
    assert captured["tool_choice"]["type"] == "tool"
    assert captured["tools"][0]["input_schema"]["properties"].keys() >= {"name", "age"}
    assert RESPONSE_SCHEMA_KEY not in captured


# ---------- Gemini native ----------


def test_gemini_uses_native_response_schema(monkeypatch):
    from loom.providers import gemini_provider

    captured: dict = {}

    def generate_content(**kw):
        captured.update(kw)
        return SimpleNamespace(text=_VALID_JSON, usage_metadata=None)

    class FakeClient:
        def __init__(self):
            self.models = SimpleNamespace(generate_content=generate_content)

    monkeypatch.setattr(gemini_provider, "_client", lambda: FakeClient())
    client = Loom(catalog=_native_catalog(), api_keys={})
    user = client.generate(provider="gemini", model="gem", prompt="x", schema=User)

    assert isinstance(user, User) and user.name == "Ada"
    cfg = captured["config"]
    assert cfg["response_mime_type"] == "application/json"
    assert set(cfg["response_schema"]["properties"]) == {"name", "age"}
    assert RESPONSE_SCHEMA_KEY not in captured


# ---------- non-native fallback ----------


def _register_fake_provider(monkeypatch, recorder):
    """Register a non-native provider that records the params it receives."""
    import types

    from loom.providers import _LAZY, _LOADED

    mod = types.ModuleType("fake_structured_provider")

    def generate(modality, model, params, prompt):
        recorder["params"] = params
        recorder["prompt"] = prompt
        return {"kind": "text", "text": _VALID_JSON}

    mod.generate = generate  # type: ignore[attr-defined]
    monkeypatch.setitem(_LAZY, "fakep", "fake_structured_provider")
    monkeypatch.setitem(_LOADED, "fakep", mod)


def test_unsupported_provider_falls_back_to_json(monkeypatch):
    recorder: dict = {}
    _register_fake_provider(monkeypatch, recorder)
    cat = Catalog(
        data={
            "fakep": {
                "label": "Fake",
                "modalities": {"text": [{"id": "fm", "name": "FM"}]},
            }
        }
    )
    client = Loom(catalog=cat, api_keys={})
    user = client.generate(provider="fakep", model="fm", prompt="Who?", schema=User)

    # Same validated return type as the native providers.
    assert isinstance(user, User) and user.name == "Ada"
    # The reserved key was stripped before reaching the adapter...
    assert RESPONSE_SCHEMA_KEY not in recorder["params"]
    # ...and the schema instruction rode in on the prompt instead.
    assert "JSON Schema" in recorder["prompt"]


def test_supports_flag_matches_native_set():
    assert supports_structured_output("openai")
    assert supports_structured_output("anthropic")
    assert supports_structured_output("gemini")
    assert not supports_structured_output("mistral")
