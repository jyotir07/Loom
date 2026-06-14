"""Smart model routing — Router + Loom.route() + AsyncLoom.route()."""

import asyncio

import pytest

import loom
from loom import AsyncLoom, Candidate, Loom, Router
from loom.errors import AuthError, ProviderError, RateLimitError


# ---------- Router construction ----------


def test_router_requires_candidates():
    with pytest.raises(ValueError):
        Router(candidates=[])


def test_router_accepts_tuple_shorthand():
    r = Router(candidates=[("openai", "text", "gpt-4o-mini")])
    assert len(r.candidates) == 1
    assert r.candidates[0].provider == "openai"
    assert r.candidates[0].modality == "text"
    assert r.candidates[0].model == "gpt-4o-mini"
    assert r.candidates[0].params is None


def test_router_accepts_four_tuple_with_params():
    r = Router(candidates=[("openai", "text", "gpt-4o", {"temperature": 0.7})])
    assert r.candidates[0].params == {"temperature": 0.7}


def test_router_accepts_candidate_objects():
    c = Candidate(provider="openai", modality="text", model="gpt-4o-mini")
    r = Router(candidates=[c])
    assert r.candidates[0] is c


def test_router_rejects_invalid_candidate():
    with pytest.raises(TypeError):
        Router(candidates=["openai/text/gpt-4o-mini"])


# ---------- sync routing ----------


def _fake_provider_factory(responses_by_model: dict, raise_for: dict | None = None):
    """Build a (calls, fake_generate) pair.

    `responses_by_model` maps upstream model -> response dict.
    `raise_for` maps upstream model -> exception instance to raise instead.
    """
    calls: list[dict] = []
    raise_for = raise_for or {}

    def fake_generate(provider, modality, model, params, prompt):
        calls.append({"provider": provider, "model": model, "params": dict(params)})
        if model in raise_for:
            raise raise_for[model]
        return responses_by_model[model]

    return calls, fake_generate


def test_route_first_candidate_passes_validator(monkeypatch):
    calls, fake = _fake_provider_factory(
        {
            "gpt-4o-mini": {"kind": "text", "text": "a sufficiently long answer here"},
            "gpt-4o": {"kind": "text", "text": "should not be reached"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 10,
    )
    result = client.route(router, prompt="hi")
    assert result["text"].startswith("a sufficiently")
    assert result["_router"]["used"] == "openai:text:gpt-4o-mini"
    assert result["_router"]["passed"] is True
    assert result["_router"]["tried"] == ["openai:text:gpt-4o-mini"]
    assert len(calls) == 1


def test_route_escalates_on_validator_failure(monkeypatch):
    calls, fake = _fake_provider_factory(
        {
            "gpt-4o-mini": {"kind": "text", "text": "short"},
            "gpt-4o": {"kind": "text", "text": "much more elaborate answer"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 10,
    )
    result = client.route(router, prompt="hi")
    assert result["text"] == "much more elaborate answer"
    assert result["_router"]["used"] == "openai:text:gpt-4o"
    assert result["_router"]["passed"] is True
    assert result["_router"]["tried"] == [
        "openai:text:gpt-4o-mini",
        "openai:text:gpt-4o",
    ]
    assert len(calls) == 2


def test_route_returns_last_result_when_all_fail_validator(monkeypatch):
    _, fake = _fake_provider_factory(
        {
            "gpt-4o-mini": {"kind": "text", "text": "no"},
            "gpt-4o": {"kind": "text", "text": "nope"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 50,
    )
    result = client.route(router, prompt="hi")
    assert result["text"] == "nope"
    assert result["_router"]["used"] == "openai:text:gpt-4o"
    assert result["_router"]["passed"] is False


def test_route_skips_candidate_on_loom_error(monkeypatch):
    _, fake = _fake_provider_factory(
        {
            "gpt-4o": {"kind": "text", "text": "fallback worked"},
        },
        raise_for={"gpt-4o-mini": RateLimitError("hit cap")},
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
    )
    result = client.route(router, prompt="hi")
    assert result["text"] == "fallback worked"
    assert result["_router"]["used"] == "openai:text:gpt-4o"


def test_route_reraises_last_error_when_all_candidates_fail(monkeypatch):
    _, fake = _fake_provider_factory(
        {},
        raise_for={
            "gpt-4o-mini": AuthError("missing key A"),
            "gpt-4o": ProviderError("upstream went home"),
        },
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"}, retry=None)
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
    )
    with pytest.raises(ProviderError) as ei:
        client.route(router, prompt="hi")
    assert "upstream went home" in str(ei.value)


def test_route_merges_per_candidate_params(monkeypatch):
    calls, fake = _fake_provider_factory(
        {
            "gpt-4o": {"kind": "text", "text": "ok"},
        }
    )
    monkeypatch.setattr("loom._loom._providers.generate", fake)

    client = Loom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            Candidate(
                provider="openai",
                modality="text",
                model="gpt-4o",
                params={"temperature": 0.9},
            ),
        ],
    )
    client.route(router, prompt="hi", params={"temperature": 0.1, "top_p": 0.5})
    # candidate params win on conflict
    assert calls[0]["params"]["temperature"] == 0.9
    # caller params still flow through
    assert calls[0]["params"]["top_p"] == 0.5


# ---------- async routing ----------


def test_async_route_escalates(monkeypatch):
    async def fake_agenerate(provider, modality, model, params, prompt):
        if model == "gpt-4o-mini":
            return {"kind": "text", "text": "tiny"}
        return {"kind": "text", "text": "this one is properly long"}

    monkeypatch.setattr("loom._loom._providers.agenerate", fake_agenerate)
    client = AsyncLoom(api_keys={"OPENAI_API_KEY": "k"})
    router = Router(
        candidates=[
            ("openai", "text", "gpt-4o-mini"),
            ("openai", "text", "gpt-4o"),
        ],
        validator=lambda r: len(r["text"]) > 10,
    )
    result = asyncio.run(client.route(router, prompt="hi"))
    assert result["text"].startswith("this one")
    assert result["_router"]["used"] == "openai:text:gpt-4o"
    assert result["_router"]["passed"] is True
