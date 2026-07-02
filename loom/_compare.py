"""Provider benchmarking — run one prompt across many providers at once.

Choosing a model usually means trying the same task on several providers
and eyeballing the trade-offs. `Loom.compare()` / `AsyncLoom.compare()`
does that in a single call: it fans the prompt out concurrently, times
each response, and returns a row per provider (latency, tokens, cost,
output) plus a small summary naming the cheapest / fastest / highest-
quality result.

Benchmarking rides the normal generation pipeline — each row is just a
`generate()` call — so caching, retry, health tracking, and logging all
behave exactly as they do everywhere else. Two deliberate defaults:

* **Cache is bypassed** (``use_cache=False``) so latency reflects a real
  upstream call rather than a memory hit.
* **Per-row failures are captured, not raised.** A provider that 429s or
  times out becomes a row with ``ok=False`` and an ``error`` string; the
  rest of the comparison still returns.

This module only *executes and tabulates*. Which model represents each
provider is decided by the client via the routing selector before the
candidates ever reach here.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from loom._router import Candidate
from loom.routing.signals import RoutingSignals

if TYPE_CHECKING:
    from loom._loom import AsyncLoom, Loom

# Quality tiers, weakest to strongest — mirrors StrategySelector so the
# "highest_quality" summary agrees with how routing ranks quality. Unknown
# tiers sort below every known one.
_QUALITY_RANK: dict[str, int] = {
    "nano": 0,
    "cheap": 1,
    "standard": 2,
    "frontier": 3,
}
_WORST_QUALITY = -1


@dataclass
class CompareResult:
    """One provider's result in a benchmark run.

    ``ok`` distinguishes a successful call from a captured failure. On
    failure the metric fields stay ``None`` and ``error`` holds the reason;
    ``latency_ms`` is still populated (time spent before the error) so a
    slow failure is visible.
    """

    provider: str
    model: str
    modality: str
    ok: bool
    latency_ms: float
    tokens: int | None = None
    cost_usd: float | None = None
    output: str | None = None
    error: str | None = None
    # Catalog quality rank (-1 unknown); used only to build the summary.
    quality: int = _WORST_QUALITY

    def label(self) -> str:
        return f"{self.provider}:{self.modality}:{self.model}"


@dataclass
class CompareSummary:
    """The standout row along each axis (computed over successful rows)."""

    cheapest: CompareResult | None = None
    fastest: CompareResult | None = None
    highest_quality: CompareResult | None = None


@dataclass
class CompareReport:
    """The result of `compare()` — iterable rows plus a `summary`.

    Iterating or indexing yields the per-provider :class:`CompareResult`
    rows in the order the providers were given::

        report = client.compare(prompt="...", providers=["openai", "gemini"])
        for row in report:
            print(row.provider, row.latency_ms, row.cost_usd)
        print("cheapest:", report.summary.cheapest.provider)
    """

    rows: list[CompareResult] = field(default_factory=list)
    summary: CompareSummary = field(default_factory=CompareSummary)

    def __iter__(self) -> Iterator[CompareResult]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> CompareResult:
        return self.rows[index]


# -- metric extraction ------------------------------------------------------


def _tokens_of(result: dict[str, Any]) -> int | None:
    usage = result.get("usage")
    if not usage:
        return None
    total = usage.get("total_tokens")
    if total is not None:
        return int(total)
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    if inp is None and out is None:
        return None
    return int(inp or 0) + int(out or 0)


def _cost_of(result: dict[str, Any]) -> float | None:
    cost = result.get("cost")
    if not cost:
        return None
    usd = cost.get("usd")
    return None if usd is None else float(usd)


def _row_from_result(
    candidate: Candidate, result: dict[str, Any], latency_ms: float
) -> CompareResult:
    return CompareResult(
        provider=candidate.provider,
        model=candidate.model,
        modality=candidate.modality,
        ok=True,
        latency_ms=latency_ms,
        tokens=_tokens_of(result),
        cost_usd=_cost_of(result),
        output=result.get("text"),
    )


def _row_from_error(
    candidate: Candidate, exc: BaseException, latency_ms: float
) -> CompareResult:
    return CompareResult(
        provider=candidate.provider,
        model=candidate.model,
        modality=candidate.modality,
        ok=False,
        latency_ms=latency_ms,
        error=f"{type(exc).__name__}: {exc}",
    )


# -- summary ----------------------------------------------------------------


def _quality_rank(catalog: Any, candidate: Candidate) -> int:
    signals = RoutingSignals(catalog).for_model(
        candidate.provider, candidate.modality, candidate.model
    )
    return _QUALITY_RANK.get(signals.get("quality_tier"), _WORST_QUALITY)


def _build_summary(rows: list[CompareResult]) -> CompareSummary:
    ok_rows = [r for r in rows if r.ok]
    summary = CompareSummary()
    if not ok_rows:
        return summary

    priced = [r for r in ok_rows if r.cost_usd is not None]
    if priced:
        summary.cheapest = min(priced, key=lambda r: (r.cost_usd, r.label()))

    summary.fastest = min(ok_rows, key=lambda r: (r.latency_ms, r.label()))

    ranked = [r for r in ok_rows if r.quality >= 0]
    if ranked:
        summary.highest_quality = max(ranked, key=lambda r: (r.quality, r.label()))
    return summary


def _assemble(
    client: Any, candidates: list[Candidate], rows: list[CompareResult]
) -> CompareReport:
    # Attach quality ranks (catalog-derived) so the summary can name a
    # "highest quality" winner without the executor caring about it.
    quality_by_label = {
        cand.label(): _quality_rank(client.catalog, cand) for cand in candidates
    }
    for row in rows:
        row.quality = quality_by_label.get(row.label(), _WORST_QUALITY)
    return CompareReport(rows=rows, summary=_build_summary(rows))


# -- drivers ----------------------------------------------------------------


def run_compare_sync(
    client: "Loom",
    candidates: list[Candidate],
    *,
    prompt: str,
    params: dict[str, Any] | None,
    use_cache: bool,
) -> CompareReport:
    """Benchmark `candidates` concurrently on a threaded fan-out."""

    def _one(candidate: Candidate) -> CompareResult:
        started = time.perf_counter()
        try:
            result = client.generate(
                provider=candidate.provider,
                modality=candidate.modality,
                model=candidate.model,
                prompt=prompt,
                params=params,
                use_cache=use_cache,
            )
        except BaseException as exc:  # noqa: BLE001 — captured per row, not raised
            elapsed = (time.perf_counter() - started) * 1000.0
            return _row_from_error(candidate, exc, elapsed)
        elapsed = (time.perf_counter() - started) * 1000.0
        return _row_from_result(candidate, result, elapsed)

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        rows = list(pool.map(_one, candidates))
    return _assemble(client, candidates, rows)


async def run_compare_async(
    client: "AsyncLoom",
    candidates: list[Candidate],
    *,
    prompt: str,
    params: dict[str, Any] | None,
    use_cache: bool,
) -> CompareReport:
    """Benchmark `candidates` concurrently with asyncio.gather."""
    import asyncio

    async def _one(candidate: Candidate) -> CompareResult:
        started = time.perf_counter()
        try:
            result = await client.generate(
                provider=candidate.provider,
                modality=candidate.modality,
                model=candidate.model,
                prompt=prompt,
                params=params,
                use_cache=use_cache,
            )
        except BaseException as exc:  # noqa: BLE001 — captured per row, not raised
            elapsed = (time.perf_counter() - started) * 1000.0
            return _row_from_error(candidate, exc, elapsed)
        elapsed = (time.perf_counter() - started) * 1000.0
        return _row_from_result(candidate, result, elapsed)

    rows = list(await asyncio.gather(*(_one(c) for c in candidates)))
    return _assemble(client, candidates, rows)


__all__ = [
    "CompareResult",
    "CompareSummary",
    "CompareReport",
    "run_compare_sync",
    "run_compare_async",
]
