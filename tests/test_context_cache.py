"""Gemini context caching — handle lifecycle + cached_tokens surfacing + cost."""

import types

import pytest

from loom import ContextCacheHandle, Loom
from loom._pricing import compute_cost
from loom.catalog import Catalog


# ---------- fake google-genai client ----------


class _FakeCachedContent:
    def __init__(self, name, display_name=None, expire_time=None):
        self.name = name
        self.display_name = display_name
        self.expire_time = expire_time


class _FakeCaches:
    def __init__(self):
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self._next_id = 0

    def create(self, *, model, config):
        self._next_id += 1
        cid = f"cachedContents/abc{self._next_id}"
        self.created.append({"model": model, "config": dict(config), "id": cid})
        return _FakeCachedContent(
            name=cid,
            display_name=config.get("display_name"),
            expire_time="2026-12-31T00:00:00Z",
        )

    def delete(self, *, name):
        self.deleted.append(name)

    def get(self, *, name):
        return _FakeCachedContent(name=name, display_name="from-get")


class _FakeUsageMeta:
    def __init__(self, prompt, candidates, total, cached=0):
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates
        self.total_token_count = total
        self.cached_content_token_count = cached


class _FakeGenResponse:
    def __init__(self, text, usage=None):
        self.text = text
        self.usage_metadata = usage


class _FakeModels:
    def __init__(self):
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, **kwargs):
        self.calls.append({"model": model, "contents": contents, **kwargs})
        return _FakeGenResponse(
            text="from-gemini",
            usage=_FakeUsageMeta(
                prompt=2000, candidates=100, total=2100, cached=1800
            ),
        )


class _FakeClient:
    def __init__(self):
        self.caches = _FakeCaches()
        self.models = _FakeModels()


@pytest.fixture
def fake_gemini(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(
        "loom.context_cache_providers.gemini_context_cache._client",
        lambda: fake,
    )
    monkeypatch.setattr(
        "loom.providers.gemini_provider._client",
        lambda: fake,
    )
    return fake


# ---------- create / delete ----------


def test_create_context_cache_returns_handle(fake_gemini):
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    handle = client.create_context_cache(
        provider="gemini",
        model="gemini-2.5-flash",
        contents="a long static document",
        system_instruction="be helpful",
        ttl_seconds=300,
        display_name="policy-doc",
    )
    assert isinstance(handle, ContextCacheHandle)
    assert handle.id == "cachedContents/abc1"
    assert handle.provider == "gemini"
    assert handle.model == "gemini-2.5-flash"
    assert handle.ttl_seconds == 300
    # Check the SDK was called with the right config shape.
    cfg = fake_gemini.caches.created[0]["config"]
    assert cfg["ttl"] == "300s"
    assert cfg["system_instruction"] == "be helpful"
    assert cfg["display_name"] == "policy-doc"
    # String contents got wrapped.
    assert isinstance(cfg["contents"], list)
    assert cfg["contents"][0]["role"] == "user"


def test_create_context_cache_passes_list_contents_through(fake_gemini):
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    contents = [{"role": "user", "parts": [{"text": "verbatim block"}]}]
    client.create_context_cache(
        provider="gemini", model="gemini-2.5-flash", contents=contents
    )
    cfg = fake_gemini.caches.created[0]["config"]
    assert cfg["contents"] == contents


def test_delete_context_cache(fake_gemini):
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    handle = client.create_context_cache(
        provider="gemini", model="gemini-2.5-flash", contents="x"
    )
    client.delete_context_cache(handle)
    assert fake_gemini.caches.deleted == [handle.id]


def test_handle_delete_method(fake_gemini):
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    handle = client.create_context_cache(
        provider="gemini", model="gemini-2.5-flash", contents="x"
    )
    handle.delete()
    assert fake_gemini.caches.deleted == [handle.id]


def test_unsupported_provider_raises(monkeypatch):
    from loom.errors import ProviderError

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ProviderError):
        client.create_context_cache(
            provider="openai", model="gpt-4o-mini", contents="x"
        )


# ---------- generate() consumes cached_content + surfaces cached_tokens ----------


def test_generate_passes_cached_content_into_config(fake_gemini):
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    handle = client.create_context_cache(
        provider="gemini", model="gemini-2.5-flash", contents="x"
    )
    result = client.generate(
        provider="gemini",
        modality="text",
        model="gemini-2.5-flash",
        prompt="Summarize.",
        params={"cached_content": handle.id},
    )
    # config dict reached the SDK.
    last = fake_gemini.models.calls[-1]
    assert last["config"]["cached_content"] == handle.id
    # cached_tokens surfaced on the result.
    assert result["usage"]["cached_tokens"] == 1800


def test_generate_no_cached_content_means_no_config(fake_gemini):
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    client.generate(
        provider="gemini",
        modality="text",
        model="gemini-2.5-flash",
        prompt="Hi.",
    )
    last = fake_gemini.models.calls[-1]
    assert "config" not in last


# ---------- cost discount end-to-end ----------


def test_cached_tokens_discount_cost_for_gemini():
    """Gemini cached_discount=0.25 — make sure pricing math reflects that."""
    cat = Catalog.from_mapping(
        {
            "gemini": {
                "label": "Gemini",
                "modalities": {
                    "text": [
                        {
                            "id": "test-model",
                            "name": "Test",
                            "input_inr_per_1m": 100.0,
                            "output_inr_per_1m": 200.0,
                        }
                    ]
                },
            }
        }
    )
    full = compute_cost(
        catalog=cat, provider="gemini", modality="text", model_id="test-model",
        usage={"input_tokens": 1_000_000, "output_tokens": 0},
        local_currency="INR", local_to_usd=1.0,
    )
    discounted = compute_cost(
        catalog=cat, provider="gemini", modality="text", model_id="test-model",
        usage={
            "input_tokens": 1_000_000,
            "cached_tokens": 800_000,
            "output_tokens": 0,
        },
        local_currency="INR", local_to_usd=1.0,
    )
    # 200k @ 1.0 + 800k @ 0.25 = 200 + 200 = 400 ; full = 1_000_000 @ 1.0 = 1000
    assert full["local"] == pytest.approx(100.0)
    # non_cached=200k @100 + cached=800k @100*0.25 -> (20M + 20M)/1M = 40
    assert discounted["local"] == pytest.approx(40.0)
    assert discounted["local"] < full["local"]
