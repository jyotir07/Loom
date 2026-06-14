"""Batch submission, polling, result alignment.

Uses a registered fake adapter so tests are fully offline. The real
OpenAI adapter is exercised via its own (gated) integration test.
"""

from __future__ import annotations

import sys
import types

import pytest

from loom import BatchRequest, Loom
from loom.batch import TERMINAL_STATUSES
from loom.errors import ProviderError


# ---------------- fake adapter ----------------

def _build_fake_adapter():
    """Return a module-like object usable as a batch-provider adapter."""
    mod = types.ModuleType("fake_batch")
    mod.state = {  # type: ignore[attr-defined]
        "next_id": 0,
        "batches": {},     # id -> {"status": str, "requests": list, "results": list | None}
        "cancelled": set(),
    }

    def submit(requests, resolve, **kw):
        mod.state["next_id"] += 1
        bid = f"fake-batch-{mod.state['next_id']}"
        # Pre-bake results: one per request, success.
        rs = [
            {
                "kind": "text",
                "text": f"echo:{r.prompt}",
                "custom_id": r.custom_id,
            }
            for r in requests
        ]
        mod.state["batches"][bid] = {
            "status": "validating",
            "requests": list(requests),
            "results": rs,
        }
        return bid

    def status(batch_id):
        b = mod.state["batches"].get(batch_id)
        if b is None:
            raise ProviderError(f"unknown batch {batch_id}")
        return b["status"]

    def results(batch_id, requests):
        b = mod.state["batches"].get(batch_id)
        if b is None:
            raise ProviderError(f"unknown batch {batch_id}")
        # Align to caller's request order.
        by_id = {r["custom_id"]: r for r in b["results"]}
        return [
            by_id.get(req.custom_id, {
                "kind": "error",
                "error": "missing row",
                "custom_id": req.custom_id,
            })
            for req in requests
        ]

    def cancel(batch_id):
        mod.state["cancelled"].add(batch_id)
        if batch_id in mod.state["batches"]:
            mod.state["batches"][batch_id]["status"] = "cancelled"

    mod.submit = submit          # type: ignore[attr-defined]
    mod.status = status          # type: ignore[attr-defined]
    mod.results = results        # type: ignore[attr-defined]
    mod.cancel = cancel          # type: ignore[attr-defined]
    return mod


@pytest.fixture
def fake_batch_provider(monkeypatch):
    """Register a fake "openai" batch adapter and a matching chat provider
    so the catalog resolve still works."""
    adapter = _build_fake_adapter()

    # Stash under a synthetic module name.
    sys.modules["fake_batch"] = adapter

    from loom.batch_providers import _LAZY, _LOADED

    monkeypatch.setitem(_LAZY, "openai", "fake_batch")
    monkeypatch.setitem(_LOADED, "openai", adapter)

    yield adapter

    # Cleanup
    _LOADED.pop("openai", None)
    sys.modules.pop("fake_batch", None)


# ---------------- tests ----------------

def test_submit_returns_handle_with_id_and_requests(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    reqs = [
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="hello"),
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="world"),
    ]
    h = client.submit_batch(reqs)
    assert h.id.startswith("fake-batch-")
    assert h.provider == "openai"
    assert len(h.requests) == 2


def test_status_and_is_ready(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    h = client.submit_batch([
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="x"),
    ])
    assert h.status() == "validating"
    assert not h.is_ready()
    # Flip the fake state to completed and re-check.
    fake_batch_provider.state["batches"][h.id]["status"] = "completed"
    assert h.is_ready()


def test_results_aligned_to_request_order(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    reqs = [
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="alpha"),
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="beta"),
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="gamma"),
    ]
    h = client.submit_batch(reqs)
    fake_batch_provider.state["batches"][h.id]["status"] = "completed"
    rs = h.results()
    assert [r["text"] for r in rs] == ["echo:alpha", "echo:beta", "echo:gamma"]


def test_wait_returns_results_when_completed(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    h = client.submit_batch([
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="one"),
    ])
    fake_batch_provider.state["batches"][h.id]["status"] = "completed"
    rs = h.wait(poll_interval=0.0, timeout=2.0)
    assert rs[0]["text"] == "echo:one"


def test_wait_raises_on_failed_batch(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    h = client.submit_batch([
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="x"),
    ])
    fake_batch_provider.state["batches"][h.id]["status"] = "failed"
    with pytest.raises(ProviderError):
        h.wait(poll_interval=0.0, timeout=2.0)


def test_wait_times_out(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    h = client.submit_batch([
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="x"),
    ])
    # status stays "validating" — wait() should give up at the deadline.
    with pytest.raises(ProviderError, match="did not finish"):
        h.wait(poll_interval=0.05, timeout=0.15)


def test_cancel_invokes_adapter(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    h = client.submit_batch([
        BatchRequest(provider="openai", modality="text",
                     model="gpt-4o-mini", prompt="x"),
    ])
    h.cancel()
    assert h.id in fake_batch_provider.state["cancelled"]
    assert h.status() == "cancelled"


def test_run_batch_is_submit_plus_wait(fake_batch_provider):
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})

    # Flip to completed as soon as we submit.
    original_submit = fake_batch_provider.submit

    def auto_complete_submit(requests, resolve, **kw):
        bid = original_submit(requests, resolve, **kw)
        fake_batch_provider.state["batches"][bid]["status"] = "completed"
        return bid

    fake_batch_provider.submit = auto_complete_submit

    rs = client.run_batch(
        [
            BatchRequest(provider="openai", modality="text",
                         model="gpt-4o-mini", prompt="quick"),
        ],
        poll_interval=0.0,
        timeout=2.0,
    )
    assert rs[0]["text"] == "echo:quick"


def test_mixed_providers_rejected():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ProviderError, match="single provider"):
        client.submit_batch([
            BatchRequest(provider="openai", modality="text",
                         model="gpt-4o-mini", prompt="x"),
            BatchRequest(provider="anthropic", modality="text",
                         model="claude-haiku-4-5", prompt="y"),
        ])


def test_empty_batch_rejected():
    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    with pytest.raises(ProviderError, match="at least one"):
        client.submit_batch([])


def test_provider_without_batch_adapter_rejected():
    # Gemini has a catalog entry and a live adapter, but no batch adapter yet.
    client = Loom(api_keys={"GEMINI_API_KEY": "k"})
    with pytest.raises(ProviderError, match="no Loom batch adapter"):
        client.submit_batch([
            BatchRequest(provider="gemini", modality="text",
                         model="gemini-2.5-flash", prompt="x"),
        ])


def test_batch_request_auto_generates_custom_id():
    r = BatchRequest(
        provider="openai", modality="text",
        model="gpt-4o-mini", prompt="x",
    )
    assert r.custom_id.startswith("loom-")
    r2 = BatchRequest(
        provider="openai", modality="text",
        model="gpt-4o-mini", prompt="x",
    )
    assert r.custom_id != r2.custom_id


def test_explicit_custom_id_preserved():
    r = BatchRequest(
        provider="openai", modality="text",
        model="gpt-4o-mini", prompt="x", custom_id="my-row-42",
    )
    assert r.custom_id == "my-row-42"


def test_terminal_statuses_constant():
    assert "completed" in TERMINAL_STATUSES
    assert "failed" in TERMINAL_STATUSES
    assert "cancelled" in TERMINAL_STATUSES
    assert "expired" in TERMINAL_STATUSES
    assert "in_progress" not in TERMINAL_STATUSES
