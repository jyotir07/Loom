"""Smart model routing.

The cheap-first / escalate-on-failure pattern. You declare an ordered
list of model candidates (cheapest first) and an optional `validator`.
Loom tries them in order; the first response that passes the validator
wins. If none pass, the last response is returned with a `_router`
trace so the caller can decide what to do.

Typical use:

    from loom import Loom, Router, Candidate

    router = Router(
        candidates=[
            Candidate("openai", "text", "gpt-4o-mini"),
            Candidate("openai", "text", "gpt-4o"),
        ],
        validator=lambda result: len(result["text"]) > 40,
    )
    client = Loom.from_env()
    result = client.route(router, prompt="Explain X.")
    # result["_router"]["used"] is the candidate that actually answered.

Per-candidate `params` are merged on top of `params` passed to `route()`,
candidate values winning — that's how you bake quality knobs into the
escalation tier (e.g., a temperature bump on the expensive model).

Failure semantics:
    - Per-candidate ProviderError (incl. AuthError, RateLimitError,
      ModelNotFoundError) is recorded and we move on.
    - Non-Loom exceptions surface immediately — those are programmer
      errors, not vendor flakiness.
    - If every candidate raises, the last exception is re-raised.
    - If candidates succeed but no validator passes, the last successful
      response is returned with `_router.passed=False`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Union

from loom.errors import LoomError


Validator = Callable[[dict[str, Any]], bool]


@dataclass
class Candidate:
    """One model option in a routing chain."""

    provider: str
    modality: str
    model: str
    params: dict[str, Any] | None = None

    def label(self) -> str:
        return f"{self.provider}:{self.modality}:{self.model}"


# Shorthand accepted by Router(candidates=...): a 3-tuple of strings or
# a Candidate.
CandidateLike = Union[
    Candidate,
    tuple[str, str, str],
    tuple[str, str, str, dict[str, Any]],
]


def _coerce(c: CandidateLike) -> Candidate:
    if isinstance(c, Candidate):
        return c
    if isinstance(c, tuple) and len(c) == 3:
        return Candidate(provider=c[0], modality=c[1], model=c[2])
    if isinstance(c, tuple) and len(c) == 4:
        return Candidate(provider=c[0], modality=c[1], model=c[2], params=c[3])
    raise TypeError(
        f"Router candidate must be Candidate or (provider, modality, model[, params]) tuple — got {c!r}"
    )


@dataclass
class Router:
    """Ordered list of model candidates + an optional validator.

    The Router itself is stateless; pass it to `Loom.route(...)`.
    """

    candidates: list[Candidate] = field(default_factory=list)
    validator: Validator | None = None

    def __init__(
        self,
        candidates: Iterable[CandidateLike],
        validator: Validator | None = None,
    ) -> None:
        self.candidates = [_coerce(c) for c in candidates]
        if not self.candidates:
            raise ValueError("Router requires at least one candidate")
        self.validator = validator


def _merge_params(
    base: dict[str, Any] | None, override: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not base and not override:
        return None
    out: dict[str, Any] = dict(base or {})
    if override:
        out.update(override)
    return out


def _tag(result: dict[str, Any], *, used: Candidate, tried: list[str], passed: bool) -> dict[str, Any]:
    result["_router"] = {
        "used": used.label(),
        "tried": tried,
        "passed": passed,
    }
    return result


def run_route_sync(
    client: Any,
    router: Router,
    *,
    prompt: str,
    params: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Sync routing driver — used by Loom.route()."""
    tried: list[str] = []
    last_result: dict[str, Any] | None = None
    last_used: Candidate | None = None
    last_exc: BaseException | None = None

    for cand in router.candidates:
        tried.append(cand.label())
        merged = _merge_params(params, cand.params)
        try:
            result = client.generate(
                provider=cand.provider,
                modality=cand.modality,
                model=cand.model,
                prompt=prompt,
                params=merged,
                use_cache=use_cache,
            )
        except LoomError as exc:
            last_exc = exc
            continue

        if router.validator is None or router.validator(result):
            return _tag(result, used=cand, tried=tried, passed=True)

        last_result = result
        last_used = cand

    if last_result is not None and last_used is not None:
        return _tag(last_result, used=last_used, tried=tried, passed=False)

    assert last_exc is not None
    raise last_exc


async def run_route_async(
    client: Any,
    router: Router,
    *,
    prompt: str,
    params: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Async routing driver — used by AsyncLoom.route()."""
    tried: list[str] = []
    last_result: dict[str, Any] | None = None
    last_used: Candidate | None = None
    last_exc: BaseException | None = None

    for cand in router.candidates:
        tried.append(cand.label())
        merged = _merge_params(params, cand.params)
        try:
            result = await client.generate(
                provider=cand.provider,
                modality=cand.modality,
                model=cand.model,
                prompt=prompt,
                params=merged,
                use_cache=use_cache,
            )
        except LoomError as exc:
            last_exc = exc
            continue

        if router.validator is None or router.validator(result):
            return _tag(result, used=cand, tried=tried, passed=True)

        last_result = result
        last_used = cand

    if last_result is not None and last_used is not None:
        return _tag(last_result, used=last_used, tried=tried, passed=False)

    assert last_exc is not None
    raise last_exc
