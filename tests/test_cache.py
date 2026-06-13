"""Response cache: InMemoryCache + Loom integration."""

import time

import pytest

from loom import InMemoryCache, Loom


def test_inmemory_get_miss_returns_none():
    c = InMemoryCache()
    assert c.get("nope") is None


def test_inmemory_set_then_get():
    c = InMemoryCache(ttl=None)
    c.set("k", {"kind": "text", "text": "hi"})
    out = c.get("k")
    assert out == {"kind": "text", "text": "hi"}


def test_inmemory_ttl_expires():
    c = InMemoryCache(ttl=0.05)
    c.set("k", {"x": 1})
    assert c.get("k") == {"x": 1}
    time.sleep(0.08)
    assert c.get("k") is None


def test_inmemory_lru_evicts_oldest():
    c = InMemoryCache(maxsize=2, ttl=None)
    c.set("a", {"v": 1})
    c.set("b", {"v": 2})
    c.set("c", {"v": 3})  # should evict "a"
    assert c.get("a") is None
    assert c.get("b") == {"v": 2}
    assert c.get("c") == {"v": 3}


def test_inmemory_returns_deep_copy():
    c = InMemoryCache(ttl=None)
    original = {"images": [{"data_b64": "abc"}]}
    c.set("k", original)
    got = c.get("k")
    got["images"][0]["data_b64"] = "MUTATED"
    again = c.get("k")
    assert again["images"][0]["data_b64"] == "abc"


def test_loom_cache_hits_avoid_provider(monkeypatch):
    calls = {"n": 0}

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        return {"kind": "text", "text": "fresh"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)

    cache = InMemoryCache(ttl=None)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, cache=cache, retry=None)
    r1 = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hello"
    )
    r2 = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hello"
    )
    assert calls["n"] == 1
    assert r1["text"] == r2["text"] == "fresh"
    assert r1["provider"] == "openai"


def test_loom_use_cache_false_skips_lookup(monkeypatch):
    calls = {"n": 0}

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        return {"kind": "text", "text": "x"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)

    cache = InMemoryCache(ttl=None)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, cache=cache, retry=None)
    client.generate(provider="openai", modality="text", model="gpt-4o-mini", prompt="x")
    client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="x",
        use_cache=False,
    )
    assert calls["n"] == 2


def test_loom_different_prompts_different_cache_entries(monkeypatch):
    calls = {"n": 0}

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        return {"kind": "text", "text": prompt + "!"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)

    cache = InMemoryCache(ttl=None)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, cache=cache, retry=None)
    a = client.generate(provider="openai", modality="text", model="gpt-4o-mini", prompt="a")
    b = client.generate(provider="openai", modality="text", model="gpt-4o-mini", prompt="b")
    assert calls["n"] == 2
    assert a["text"] == "a!"
    assert b["text"] == "b!"


def test_cache_stores_enriched_response(monkeypatch):
    """Cached responses include the cost/provider fields that Loom adds, so
    served-from-cache hits don't drop observability data."""
    def fake_provider_generate(provider, modality, model, params, prompt):
        return {
            "kind": "text",
            "text": "x",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)

    cache = InMemoryCache(ttl=None)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, cache=cache, retry=None)
    client.generate(provider="openai", modality="text", model="gpt-4o-mini", prompt="x")
    second = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="x"
    )
    assert second["provider"] == "openai"
    assert "cost" in second
    assert second["cost"]["usd"] > 0
