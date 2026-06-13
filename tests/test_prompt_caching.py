"""Vendor-native prompt caching — usage surfacing + discounted cost."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from loom import Loom
from loom._pricing import compute_cost
from loom._prompt_cache_rates import (
    cache_write_premium_for,
    cached_discount_for,
)
from loom.catalog import Catalog
from loom.providers._openai_compatible import _attach_usage as _compat_attach


# ---------------- discount tables ----------------

def test_cached_discount_lookup_defaults_to_one():
    assert cached_discount_for("nope") == 1.0
    assert cached_discount_for("openai") == 0.5
    assert cached_discount_for("anthropic") == 0.1
    assert cached_discount_for("deepseek") == 0.1


def test_cache_write_premium_defaults_to_one():
    assert cache_write_premium_for("openai") == 1.0
    assert cache_write_premium_for("anthropic") == 1.25


# ---------------- cost discount ----------------

def test_compute_cost_applies_openai_cached_discount():
    c = Catalog()
    # 1M input, all cached. gpt-4o-mini input = 14.4578 INR / 1M.
    full = compute_cost(
        catalog=c, provider="openai", modality="text", model_id="gpt-4o-mini",
        usage={"input_tokens": 1_000_000, "output_tokens": 0},
    )
    cached = compute_cost(
        catalog=c, provider="openai", modality="text", model_id="gpt-4o-mini",
        usage={"input_tokens": 1_000_000, "output_tokens": 0,
               "cached_tokens": 1_000_000},
    )
    assert full is not None and cached is not None
    # All-cached should cost exactly the 50% discount rate.
    assert cached["local"] == pytest.approx(full["local"] * 0.5, rel=1e-3)


def test_compute_cost_applies_anthropic_cached_discount():
    c = Catalog()
    full = compute_cost(
        catalog=c, provider="anthropic", modality="text",
        model_id="claude-haiku-4-5",
        usage={"input_tokens": 1_000_000, "output_tokens": 0},
    )
    cached = compute_cost(
        catalog=c, provider="anthropic", modality="text",
        model_id="claude-haiku-4-5",
        usage={"input_tokens": 1_000_000, "output_tokens": 0,
               "cached_tokens": 1_000_000},
    )
    assert full is not None and cached is not None
    assert cached["local"] == pytest.approx(full["local"] * 0.1, rel=1e-3)


def test_compute_cost_anthropic_cache_write_premium():
    c = Catalog()
    full = compute_cost(
        catalog=c, provider="anthropic", modality="text",
        model_id="claude-haiku-4-5",
        usage={"input_tokens": 1_000_000, "output_tokens": 0},
    )
    write = compute_cost(
        catalog=c, provider="anthropic", modality="text",
        model_id="claude-haiku-4-5",
        usage={"input_tokens": 1_000_000, "output_tokens": 0,
               "cache_creation_tokens": 1_000_000},
    )
    assert full is not None and write is not None
    assert write["local"] == pytest.approx(full["local"] * 1.25, rel=1e-3)


def test_compute_cost_mixed_cached_and_normal():
    """Half cached, half regular -> midpoint between full and full*discount."""
    c = Catalog()
    full = compute_cost(
        catalog=c, provider="openai", modality="text", model_id="gpt-4o-mini",
        usage={"input_tokens": 2_000_000, "output_tokens": 0},
    )
    mixed = compute_cost(
        catalog=c, provider="openai", modality="text", model_id="gpt-4o-mini",
        usage={"input_tokens": 2_000_000, "output_tokens": 0,
               "cached_tokens": 1_000_000},
    )
    assert full is not None and mixed is not None
    # 1M @ full + 1M @ 0.5 = 1.5M @ full -> 75% of the 2M-at-full price.
    assert mixed["local"] == pytest.approx(full["local"] * 0.75, rel=1e-3)


# ---------------- OpenAI usage surfacing ----------------

def test_openai_provider_surfaces_cached_tokens(monkeypatch):
    """gpt-4o-mini response with prompt_tokens_details.cached_tokens=400 ->
    usage.cached_tokens = 400 in Loom's normalized payload."""
    from loom.providers import openai_provider

    fake_resp = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="hello")
        )],
        usage=SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=50,
            total_tokens=1050,
            prompt_tokens_details=SimpleNamespace(cached_tokens=400),
        ),
    )

    class FakeChat:
        def __init__(self):
            self.completions = SimpleNamespace(create=lambda **kw: fake_resp)

    class FakeOpenAI:
        def __init__(self, **kw):
            self.chat = FakeChat()

    monkeypatch.setattr(openai_provider, "_client", lambda: FakeOpenAI())

    result = openai_provider.generate("text", "gpt-4o-mini", {}, "hi")
    assert result["usage"]["input_tokens"] == 1000
    assert result["usage"]["cached_tokens"] == 400


def test_openai_provider_omits_cached_when_zero(monkeypatch):
    from loom.providers import openai_provider

    fake_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
        usage=SimpleNamespace(
            prompt_tokens=10, completion_tokens=2, total_tokens=12,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0),
        ),
    )

    class FakeOpenAI:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: fake_resp)
            )

    monkeypatch.setattr(openai_provider, "_client", lambda: FakeOpenAI())
    result = openai_provider.generate("text", "gpt-4o-mini", {}, "hi")
    assert "cached_tokens" not in result["usage"]


# ---------------- DeepSeek usage surfacing (via OpenAI-compat helper) ----------------

def test_openai_compat_attaches_deepseek_cache_hit():
    out: dict = {"kind": "text", "text": "hi"}
    resp = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=50,
            total_tokens=1050,
            prompt_cache_hit_tokens=600,
            prompt_cache_miss_tokens=400,
        )
    )
    _compat_attach(out, resp)
    assert out["usage"]["input_tokens"] == 1000
    assert out["usage"]["cached_tokens"] == 600


def test_openai_compat_no_cache_field_means_no_cached_tokens():
    out: dict = {"kind": "text", "text": "hi"}
    resp = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=100, completion_tokens=10, total_tokens=110,
        )
    )
    _compat_attach(out, resp)
    assert "cached_tokens" not in out["usage"]


# ---------------- Anthropic usage normalization ----------------

def test_anthropic_normalizes_input_to_total_prompt(monkeypatch):
    """Anthropic reports input_tokens as non-cached; Loom normalizes so
    input_tokens = non_cached + cache_read + cache_creation."""
    from loom.providers import anthropic_provider

    fake_resp = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=SimpleNamespace(
            input_tokens=200,                  # non-cached portion
            cache_read_input_tokens=800,       # cached read
            cache_creation_input_tokens=100,   # cache write
            output_tokens=30,
        ),
    )

    class FakeAnthropic:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **kw: fake_resp)

    monkeypatch.setattr(anthropic_provider, "_client", lambda: FakeAnthropic())

    result = anthropic_provider.generate(
        "text", "claude-haiku-4-5", {}, "hi"
    )
    assert result["usage"]["input_tokens"] == 1100   # 200 + 800 + 100
    assert result["usage"]["cached_tokens"] == 800
    assert result["usage"]["cache_creation_tokens"] == 100
    assert result["usage"]["output_tokens"] == 30


# ---------------- Anthropic cache_control plumbing ----------------

def test_anthropic_cache_system_wraps_string_system(monkeypatch):
    from loom.providers import anthropic_provider

    captured: dict = {}

    fake_resp = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=SimpleNamespace(
            input_tokens=10, output_tokens=5,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        ),
    )

    def fake_create(**kwargs):
        captured.update(kwargs)
        return fake_resp

    class FakeAnthropic:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=fake_create)

    monkeypatch.setattr(anthropic_provider, "_client", lambda: FakeAnthropic())

    anthropic_provider.generate(
        "text", "claude-haiku-4-5",
        {"system": "Long system prompt", "cache_system": True},
        "hi",
    )
    system_arg = captured["system"]
    assert isinstance(system_arg, list)
    assert system_arg[0]["cache_control"] == {"type": "ephemeral"}
    assert system_arg[0]["text"] == "Long system prompt"
    # cache_system / system should be consumed, not forwarded as-is.
    assert "cache_system" not in captured


def test_anthropic_passes_through_list_system_verbatim(monkeypatch):
    """If caller supplies system as a list of blocks, we don't rewrap it."""
    from loom.providers import anthropic_provider

    captured: dict = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text="ok")],
            usage=SimpleNamespace(
                input_tokens=1, output_tokens=1,
                cache_read_input_tokens=0, cache_creation_input_tokens=0,
            ),
        )

    class FakeAnthropic:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=fake_create)

    monkeypatch.setattr(anthropic_provider, "_client", lambda: FakeAnthropic())

    explicit_system = [
        {"type": "text", "text": "static prefix",
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "dynamic suffix"},
    ]
    anthropic_provider.generate(
        "text", "claude-haiku-4-5",
        {"system": explicit_system, "cache_system": True},  # cache_system ignored
        "hi",
    )
    assert captured["system"] == explicit_system


def test_anthropic_cache_user_wraps_user_message(monkeypatch):
    from loom.providers import anthropic_provider

    captured: dict = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text="ok")],
            usage=SimpleNamespace(
                input_tokens=1, output_tokens=1,
                cache_read_input_tokens=0, cache_creation_input_tokens=0,
            ),
        )

    class FakeAnthropic:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=fake_create)

    monkeypatch.setattr(anthropic_provider, "_client", lambda: FakeAnthropic())

    anthropic_provider.generate(
        "text", "claude-haiku-4-5",
        {"cache_user": True},
        "user prompt that should be cached",
    )
    messages = captured["messages"]
    assert isinstance(messages[0]["content"], list)
    assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert messages[0]["content"][0]["text"] == "user prompt that should be cached"


# ---------------- end-to-end via Loom (cost reflects cache discount) ----------------

def test_loom_records_discounted_cost_for_cached_call(monkeypatch):
    def fake_provider_generate(provider, modality, model, params, prompt):
        return {
            "kind": "text",
            "text": "hi",
            "usage": {
                "input_tokens": 100_000,
                "output_tokens": 100,
                "total_tokens": 100_100,
                "cached_tokens": 80_000,
            },
        }

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    result = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi",
    )
    # Sanity: cost present.
    assert "cost" in result
    # The 80k cached tokens at 50% are cheaper than treating them as full.
    # Build the "no cache" baseline to compare.
    monkeypatch.setattr(
        "loom._loom._providers.generate",
        lambda p, mo, m, pa, pr: {
            "kind": "text", "text": "hi",
            "usage": {
                "input_tokens": 100_000, "output_tokens": 100,
                "total_tokens": 100_100,
            },
        },
    )
    no_cache = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi",
        use_cache=False,
    )
    assert result["cost"]["local"] < no_cache["cost"]["local"]
