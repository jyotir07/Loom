"""Anthropic batch adapter — direct unit tests against a fake SDK."""

from __future__ import annotations

import pytest

from loom import BatchRequest, Loom
from loom.batch_providers import anthropic_batch
from loom.errors import ProviderError


# ---------- fake anthropic SDK ----------


class _FakeBatchMeta:
    def __init__(self, id_: str, processing_status: str):
        self.id = id_
        self.processing_status = processing_status


class _FakeBatchesAPI:
    def __init__(self):
        self.created: list[dict] = []
        self.retrieved: list[str] = []
        self.cancelled: list[str] = []
        self.next_id = 0
        self.status_by_id: dict[str, str] = {}
        self.results_by_id: dict[str, list[dict]] = {}

    def create(self, *, requests):
        self.next_id += 1
        bid = f"msgbatch_{self.next_id}"
        self.created.append({"id": bid, "requests": list(requests)})
        self.status_by_id[bid] = "in_progress"
        return _FakeBatchMeta(bid, "in_progress")

    def retrieve(self, batch_id):
        self.retrieved.append(batch_id)
        return _FakeBatchMeta(batch_id, self.status_by_id.get(batch_id, "in_progress"))

    def cancel(self, batch_id):
        self.cancelled.append(batch_id)
        self.status_by_id[batch_id] = "canceling"

    def results(self, batch_id):
        yield from self.results_by_id.get(batch_id, [])


class _FakeMessages:
    def __init__(self):
        self.batches = _FakeBatchesAPI()


class _FakeAnthropic:
    def __init__(self):
        self.messages = _FakeMessages()


@pytest.fixture
def fake(monkeypatch):
    f = _FakeAnthropic()
    monkeypatch.setattr(anthropic_batch, "_client", lambda: f)
    return f


def _resolve_passthrough(provider, modality, model):
    """Identity resolver — upstream model == model, no catalog params."""
    return model, {}


# ---------- submit ----------


def test_submit_rejects_empty():
    with pytest.raises(ProviderError):
        anthropic_batch.submit([], _resolve_passthrough)


def test_submit_rejects_image_modality(fake):
    reqs = [
        BatchRequest(provider="anthropic", modality="image",
                     model="claude-haiku-4-5", prompt="cat")
    ]
    with pytest.raises(ProviderError):
        anthropic_batch.submit(reqs, _resolve_passthrough)


def test_submit_rejects_duplicate_custom_id(fake):
    reqs = [
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="a", custom_id="dup"),
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="b", custom_id="dup"),
    ]
    with pytest.raises(ProviderError):
        anthropic_batch.submit(reqs, _resolve_passthrough)


def test_submit_builds_request_payload(fake):
    reqs = [
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="hello",
                     custom_id="row-1",
                     params={"max_tokens": 256, "temperature": 0.3}),
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="world",
                     custom_id="row-2"),
    ]
    bid = anthropic_batch.submit(reqs, _resolve_passthrough)
    assert bid == "msgbatch_1"

    sent = fake.messages.batches.created[0]["requests"]
    assert [r["custom_id"] for r in sent] == ["row-1", "row-2"]

    body1 = sent[0]["params"]
    assert body1["model"] == "claude-haiku-4-5"
    assert body1["max_tokens"] == 256
    assert body1["temperature"] == 0.3
    assert body1["messages"] == [{"role": "user", "content": "hello"}]

    body2 = sent[1]["params"]
    assert body2["max_tokens"] == 1024  # default from _build_kwargs


def test_submit_forwards_cache_system_knob(fake):
    """Loom-side cache_system knob should produce the right Anthropic block."""
    reqs = [
        BatchRequest(
            provider="anthropic", modality="text",
            model="claude-haiku-4-5", prompt="question",
            custom_id="row-1",
            params={"system": "long static prompt", "cache_system": True},
        ),
    ]
    anthropic_batch.submit(reqs, _resolve_passthrough)
    body = fake.messages.batches.created[0]["requests"][0]["params"]
    assert body["system"] == [
        {"type": "text", "text": "long static prompt",
         "cache_control": {"type": "ephemeral"}}
    ]
    # The Loom-side knobs themselves shouldn't leak into the vendor body.
    assert "cache_system" not in body


# ---------- status ----------


def test_status_maps_ended_to_completed(fake):
    fake.messages.batches.status_by_id["msgbatch_x"] = "ended"
    assert anthropic_batch.status("msgbatch_x") == "completed"


def test_status_maps_in_progress(fake):
    fake.messages.batches.status_by_id["msgbatch_y"] = "in_progress"
    assert anthropic_batch.status("msgbatch_y") == "in_progress"


def test_status_maps_canceling_as_in_progress(fake):
    fake.messages.batches.status_by_id["msgbatch_z"] = "canceling"
    assert anthropic_batch.status("msgbatch_z") == "in_progress"


# ---------- cancel ----------


def test_cancel_invokes_sdk(fake):
    anthropic_batch.cancel("msgbatch_42")
    assert fake.messages.batches.cancelled == ["msgbatch_42"]


# ---------- results parsing ----------


def test_results_aligned_with_success_and_error_rows(fake):
    fake.messages.batches.results_by_id["msgbatch_1"] = [
        {
            "custom_id": "row-1",
            "result": {
                "type": "succeeded",
                "message": {
                    "content": [{"type": "text", "text": "hello back"}],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 100,
                        "cache_creation_input_tokens": 0,
                    },
                },
            },
        },
        {
            "custom_id": "row-2",
            "result": {
                "type": "errored",
                "error": {"type": "overloaded_error", "message": "try later"},
            },
        },
        {
            "custom_id": "row-3",
            "result": {"type": "expired"},
        },
    ]
    reqs = [
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="p1", custom_id="row-1"),
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="p2", custom_id="row-2"),
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="p3", custom_id="row-3"),
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="p4", custom_id="row-missing"),
    ]
    out = anthropic_batch.results("msgbatch_1", reqs)
    assert len(out) == 4

    # row-1: success with normalized usage (input_tokens = non_cached + cache_read)
    assert out[0]["kind"] == "text"
    assert out[0]["text"] == "hello back"
    assert out[0]["custom_id"] == "row-1"
    assert out[0]["usage"]["input_tokens"] == 110
    assert out[0]["usage"]["cached_tokens"] == 100
    assert out[0]["usage"]["output_tokens"] == 5

    # row-2: error
    assert out[1]["kind"] == "error"
    assert "try later" in out[1]["error"]
    assert out[1]["code"] == "overloaded_error"

    # row-3: expired -> per-row error with code
    assert out[2]["kind"] == "error"
    assert out[2]["code"] == "expired"

    # row-missing: not in stream -> placeholder error
    assert out[3]["kind"] == "error"
    assert out[3]["custom_id"] == "row-missing"


# ---------- Loom integration ----------


def test_loom_submit_batch_uses_anthropic_adapter(fake):
    client = Loom(api_keys={"ANTHROPIC_API_KEY": "k"})
    reqs = [
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="hi", custom_id="x"),
    ]
    handle = client.submit_batch(reqs)
    assert handle.provider == "anthropic"
    assert handle.id.startswith("msgbatch_")


def test_loom_run_batch_anthropic_end_to_end(fake):
    """submit_batch + wait + results, against the fake SDK."""
    client = Loom(api_keys={"ANTHROPIC_API_KEY": "k"})
    reqs = [
        BatchRequest(provider="anthropic", modality="text",
                     model="claude-haiku-4-5", prompt="hi", custom_id="r1"),
    ]
    # Submit (creates the batch), then pre-bake "ended" + results.
    handle = client.submit_batch(reqs)
    fake.messages.batches.status_by_id[handle.id] = "ended"
    fake.messages.batches.results_by_id[handle.id] = [
        {
            "custom_id": "r1",
            "result": {
                "type": "succeeded",
                "message": {"content": [{"type": "text", "text": "ok"}]},
            },
        }
    ]
    out = handle.wait(poll_interval=0.0, timeout=5.0)
    assert out == [{"kind": "text", "text": "ok", "custom_id": "r1"}]
