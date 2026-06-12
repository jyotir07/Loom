"""End-to-end smoke tests for the OpenAI provider — text and image.

These are gated on OPENAI_API_KEY. They make a real API call (low-cost
mini model + low-quality image) and verify the unified response shape.
Skipped automatically when the key is missing, so CI without secrets
won't fail.

To run them locally:

    pytest tests/test_openai_smoke.py -v --run-live

To skip the live calls and only run if explicitly enabled:
    they're off by default — pass --run-live.
"""

import os

import pytest

from loom import Loom


@pytest.fixture(scope="module")
def client():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skipping live smoke tests")
    return Loom.from_env()


def _live_enabled(request):
    return bool(request.config.getoption("--run-live", default=False))


@pytest.fixture
def require_live(request):
    if not _live_enabled(request):
        pytest.skip("live smoke tests disabled — pass --run-live to run them")


def test_openai_text_smoke(client, require_live):
    result = client.generate(
        provider="openai",
        modality="text",
        model="gpt-4o-mini",
        prompt="Say exactly: pong",
    )
    assert result["kind"] == "text"
    assert isinstance(result["text"], str)
    assert len(result["text"]) > 0


def test_openai_image_smoke(client, require_live):
    result = client.generate(
        provider="openai",
        modality="image",
        model="gpt-image-1-low",
        prompt="a single red apple on a white background",
    )
    assert result["kind"] == "image"
    assert isinstance(result["images"], list)
    assert len(result["images"]) >= 1
    first = result["images"][0]
    assert first["mime_type"].startswith("image/")
    assert len(first["data_b64"]) > 100
