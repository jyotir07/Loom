"""Single-flight dedup: concurrent identical calls coalesce."""

import asyncio
import threading
import time

import pytest

from loom import AsyncLoom, Loom
from loom.errors import ProviderError


def test_sync_dedup_collapses_concurrent_calls(monkeypatch):
    calls = {"n": 0}
    started_first = threading.Event()
    release = threading.Event()

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        started_first.set()
        release.wait(timeout=2.0)
        return {"kind": "text", "text": "shared"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None, dedup=True)

    results: dict = {}

    def worker(label):
        results[label] = client.generate(
            provider="openai", modality="text", model="gpt-4o-mini",
            prompt="same-prompt",
        )

    t1 = threading.Thread(target=worker, args=("a",))
    t1.start()
    started_first.wait(timeout=2.0)

    t2 = threading.Thread(target=worker, args=("b",))
    t2.start()
    # Give worker B a moment to enter and find the in-flight slot.
    time.sleep(0.05)

    release.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert calls["n"] == 1, "expected one upstream call when two callers raced"
    assert results["a"]["text"] == results["b"]["text"] == "shared"


def test_sync_dedup_propagates_error_to_waiters(monkeypatch):
    calls = {"n": 0}
    started = threading.Event()
    release = threading.Event()

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        started.set()
        release.wait(timeout=2.0)
        raise ProviderError("upstream is sad")

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None, dedup=True)

    errors: dict = {}

    def worker(label):
        try:
            client.generate(
                provider="openai", modality="text", model="gpt-4o-mini",
                prompt="boom",
            )
        except BaseException as exc:
            errors[label] = exc

    t1 = threading.Thread(target=worker, args=("a",))
    t1.start()
    started.wait(timeout=2.0)
    t2 = threading.Thread(target=worker, args=("b",))
    t2.start()
    time.sleep(0.05)
    release.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert calls["n"] == 1
    assert isinstance(errors["a"], ProviderError)
    assert isinstance(errors["b"], ProviderError)


def test_dedup_disabled_runs_every_call(monkeypatch):
    """With dedup=False, two concurrent identical calls both hit upstream."""
    calls = {"n": 0}
    started = threading.Event()
    release = threading.Event()

    def fake_provider_generate(provider, modality, model, params, prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            started.set()
            release.wait(timeout=2.0)
        return {"kind": "text", "text": "x"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_provider_generate)
    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None, dedup=False)

    def worker():
        client.generate(
            provider="openai", modality="text", model="gpt-4o-mini", prompt="x"
        )

    t1 = threading.Thread(target=worker)
    t1.start()
    started.wait(timeout=2.0)
    t2 = threading.Thread(target=worker)
    t2.start()
    time.sleep(0.05)
    release.set()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)
    assert calls["n"] == 2


def test_async_dedup_collapses_concurrent_calls(monkeypatch):
    calls = {"n": 0}

    async def go():
        gate = asyncio.Event()
        ready = asyncio.Event()

        async def fake_agenerate(provider, modality, model, params, prompt):
            calls["n"] += 1
            ready.set()
            await gate.wait()
            return {"kind": "text", "text": "shared"}

        monkeypatch.setattr("loom._loom._providers.agenerate", fake_agenerate)
        client = AsyncLoom(api_keys={"OPENAI_API_KEY": "k"}, retry=None, dedup=True)

        async def caller():
            return await client.generate(
                provider="openai", modality="text", model="gpt-4o-mini",
                prompt="same",
            )

        task_a = asyncio.create_task(caller())
        await ready.wait()
        task_b = asyncio.create_task(caller())
        # Let task_b reach the waiter branch.
        await asyncio.sleep(0)
        gate.set()
        return await asyncio.gather(task_a, task_b)

    a, b = asyncio.run(go())
    assert calls["n"] == 1
    assert a["text"] == b["text"] == "shared"
