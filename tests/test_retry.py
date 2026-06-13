"""Retry policy: backoff, classification, sync + async."""

import asyncio

import pytest

from loom import Loom, RetryPolicy
from loom._retry import arun_with_retry, run_with_retry
from loom.errors import AuthError, ModelNotFoundError, RateLimitError


def test_run_with_retry_returns_on_success():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    assert run_with_retry(RetryPolicy(max_attempts=3), fn) == "ok"
    assert len(calls) == 1


def test_retries_on_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _x: None)  # speed up the test
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RateLimitError("slow down")
        return "got it"

    result = run_with_retry(RetryPolicy(max_attempts=5, base_delay=0.01), fn)
    assert result == "got it"
    assert attempts["n"] == 3


def test_does_not_retry_auth_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _x: None)
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise AuthError("nope")

    with pytest.raises(AuthError):
        run_with_retry(RetryPolicy(max_attempts=5), fn)
    assert attempts["n"] == 1


def test_does_not_retry_model_not_found(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _x: None)
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise ModelNotFoundError("nope")

    with pytest.raises(ModelNotFoundError):
        run_with_retry(RetryPolicy(max_attempts=5), fn)
    assert attempts["n"] == 1


def test_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _x: None)
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise RateLimitError("always")

    with pytest.raises(RateLimitError):
        run_with_retry(RetryPolicy(max_attempts=3, base_delay=0.01), fn)
    assert attempts["n"] == 3


def test_policy_none_means_no_retry():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise RateLimitError("oh")

    with pytest.raises(RateLimitError):
        run_with_retry(None, fn)
    assert attempts["n"] == 1


def test_async_retry(monkeypatch):
    async def _go():
        async def fn():
            if not state["done"]:
                state["done"] = True
                raise RateLimitError("once")
            return "ok"

        state = {"done": False}
        return await arun_with_retry(
            RetryPolicy(max_attempts=3, base_delay=0.001), fn
        )

    assert asyncio.run(_go()) == "ok"


def test_loom_uses_retry_policy(monkeypatch):
    """End-to-end: Loom.generate retries a transient RateLimitError."""
    monkeypatch.setattr("time.sleep", lambda _x: None)
    calls = {"n": 0}

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError("backoff")
        return {"kind": "text", "text": "hi"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=RetryPolicy(max_attempts=3, base_delay=0.0))
    result = client.generate(
        provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
    )
    assert result["text"] == "hi"
    assert calls["n"] == 2


def test_loom_retry_can_be_disabled(monkeypatch):
    calls = {"n": 0}

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        raise RateLimitError("nope")

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    with pytest.raises(RateLimitError):
        client.generate(
            provider="openai", modality="text", model="gpt-4o-mini", prompt="hi"
        )
    assert calls["n"] == 1


def test_delay_for_attempt_grows_exponentially():
    p = RetryPolicy(base_delay=1.0, max_delay=100.0, jitter=0.0)
    assert p.delay_for_attempt(1) == 1.0
    assert p.delay_for_attempt(2) == 2.0
    assert p.delay_for_attempt(3) == 4.0
    assert p.delay_for_attempt(10) == 100.0  # capped at max_delay
