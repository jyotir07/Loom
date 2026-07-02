[![PyPI version](https://img.shields.io/pypi/v/loom-router)](https://pypi.org/project/loom-router/)
[![Python](https://img.shields.io/pypi/pyversions/loom-router)](https://pypi.org/project/loom-router/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
<!-- [![GitHub Stars](https://img.shields.io/github/stars/jyotir07/Loom?style=social)](https://github.com/jyotir07/Loom) -->
# Loom

*One API for every AI provider. Built once, used everywhere*

---

## The idea

Every team that builds something with AI ends up writing the same plumbing: pick a provider, learn their SDK, manage their API keys, handle their errors, track their costs, repeat for the next provider. Multiply this across a dozen projects and the company is paying for the same integration work over and over — while still losing out on cost optimizations that no single project has the time to build.

Loom is a Python framework that sits between your projects and the AI providers. Projects make one kind of call. Loom handles the rest: which vendor, which model, which SDK, which retry policy, which cache, which batch endpoint. The provider list grows in one place. The optimizations land in one place. Every project benefits the moment they upgrade.

It is not an aggregator. Each vendor is integrated with its own native SDK so vendor-specific features (prompt caching, grounding, image polling, streaming, structured output) are preserved instead of flattened to a lowest common denominator.

## What problem it solves

In a typical org without something like Loom:

- **Every project re-integrates the same vendors.** Five projects calling OpenAI means five sets of retry logic, five places where the key lives, five different ways of handling rate limits.
- **Switching models requires a code change in each project.** When a cheaper model launches, or a vendor deprecates a model ID, somebody has to file PRs across every repo.
- **Cost optimizations get skipped.** Prompt caching, batch APIs, smart routing to cheaper models — these all require real engineering effort that no single project can justify on its own.
- **API keys live in too many places.** Each project repo has its own `.env`, its own secrets manager entry, its own potential leak surface.
- **There's no unified view of cost.** Finance asks "what are we spending on AI?" and the answer is "we'll get back to you."
- **Vendor breaking changes hurt N times.** When a provider changes their response shape, every consuming project breaks.

Loom collapses all of this into **ONE** library.

## What Loom provides

### A single, stable contract

Every call goes through one function:

```python
from loom import generate

result = generate(
    provider="anthropic",
    model="claude-opus-4-7",
    prompt="Summarize this contract in three bullets.",
    params={"max_tokens": 500},
)
```

The return shape is consistent across providers:

```python
# Text response
{"kind": "text", "text": "..."}

# Image response
{"kind": "image", "images": [{"mime_type": "...", "data_b64": "..."}]}
```

Sync and async both supported. Type-hinted responses available for IDE autocomplete.

### A pluggable provider registry

Loom ships with 14+ providers wired up:

- **Text and image:** OpenAI, Google Gemini
- **Text only:** Anthropic, xAI (Grok), Mistral, DeepSeek, MiniMax, Z.AI (GLM), Perplexity, Together AI
- **Image only:** Black Forest Labs (Flux), ByteDance Seedream, Tencent Hunyuan, Ideogram

Any OpenAI-compatible provider can be added in roughly ten lines of code via a shared adapter. Native-SDK providers follow a documented `generate(modality, model, params, prompt) -> dict` contract.

### A catalog of models

Models are registered as data, not code. Each entry carries:

- Stable ID and display name
- Upstream model ID (the one the vendor expects)
- Default parameters
- Pricing (per 1M input/output tokens for text, per image for image)
- Free-tier flag

Adding a new model is a one-line catalog entry. The catalog can be backed by an in-memory dict, a YAML file, or Postgres — pick what fits the consuming project.

### A cost optimization layer

This is where Loom pays for itself. These optimizations are built once, in the framework, and every consuming project inherits them on upgrade.

- **Response caching.** Identical `(provider, model, prompt, params)` calls hit a cache instead of the API. Realistic savings of 20–60% on workloads with repeated queries.
- **Vendor-native prompt caching.** Anthropic, OpenAI, Gemini, and DeepSeek all offer 50–90% discounts on cached prefix tokens. Loom wires this up automatically for repeated system prompts and few-shot examples.
- **Smart model routing.** Try a cheap model first (Haiku, GPT-4o-mini, Gemini Flash); escalate to expensive ones only when confidence is low or validation fails. Realistic savings of 50–80% on mixed workloads.
- **Batch API usage.** OpenAI, Anthropic, and Gemini all offer 50% discounts on batch endpoints with 24-hour turnaround. Loom can auto-batch non-urgent calls.
- **Centralized retry and failover.** Exponential backoff done correctly once. If one vendor is down or rate-limited, fall back to an equivalent model on another vendor instead of failing.
- **Request deduplication.** When the same call fires from multiple places within a short window, collapse to one upstream request.

These numbers are ceilings, not guarantees — actual savings depend on workload. A project making 100% unique real-time calls won't benefit much from caching. The point is: the headroom exists, and projects don't have to build any of it themselves.

### Intelligent routing (v2)

v2 turns Loom from a provider abstraction into an intelligent routing layer — applications state *intent*, and Loom decides which provider and model to call. Every feature is additive; the explicit `generate(provider=, model=)` call is unchanged.

```python
# Let Loom choose the model
client.generate(prompt="Summarize this contract.")

# Named strategy — cheapest | fastest | highest_quality | balanced
client.generate(router="cheapest", prompt=...)

# Preferred providers, in order (health-aware, skips degraded ones)
client.generate(providers=["gemini", "openai", "anthropic"], prompt=...)

# Automatic cross-vendor fallback on retryable failures
from loom import FallbackPolicy
client.generate(prompt=..., fallback=FallbackPolicy(retries=3))

# Validated, provider-agnostic structured output  (pip install loom[structured])
from pydantic import BaseModel
class User(BaseModel):
    name: str
    age: int
user = client.generate(prompt="Extract the user...", schema=User)

# Benchmark providers side-by-side for a task
report = client.compare(providers=["openai", "anthropic", "gemini"], prompt=...)
print(report.summary.cheapest.provider, report.summary.fastest.provider)

# Zero-config usage analytics
client.analytics().summary(window="24h")
```

Backing all of this: a **health monitor** (per-provider circuit breaker, EWMA latency, rate-limit cooldown) that routing consults automatically, and an optional **load balancer** (`round_robin` / `weighted` / `least_latency` / `least_failures`) to spread traffic across a pool. See [`docs/routing_cookbook.md`](docs/routing_cookbook.md) for the full tour and [`CHANGELOG.md`](CHANGELOG.md) for the complete 2.0.0 list.

### Centralized key management

API keys live in one place — the Loom deployment — not in each consuming project's repo or environment. Projects authenticate to Loom with their own credentials and never see vendor keys.

### Observability

Every call is logged with provider, model, latency, token counts, and cost (in both USD and the configured local currency). Projects get a per-call cost field on every response. Finance gets a unified dashboard. Engineering gets to find the prompts that are burning the budget.

## Architecture

### Where Loom sits

```
┌─────────────────────────────────────────────────────────────┐
│                    Company projects                         │
│  Support bot │ Analytics │ Marketing │ Doc search │ Sales   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │  generate(provider, model, prompt)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                         Loom                                │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Auth + keys │  │    Cache    │  │   Router    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Batcher   │  │    Retry    │  │  Cost logs  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │   Catalog  +  Provider registry  +  Adapters        │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      AI providers                           │
│  OpenAI │ Anthropic │ Gemini │ BFL │ + 10 more vendors      │
└─────────────────────────────────────────────────────────────┘
```

### Internal layers

1. **Public API.** The single `generate(...)` function (sync and async). Stable across versions.
2. **Optimization layer.** Cache, router, batcher, retry, dedup, logging. Each is independently toggleable per call.
3. **Core services.** Catalog (what models exist), provider registry (who knows how to call them), observability (what happened).
4. **Provider adapters.** One module per vendor. OpenAI-compatible vendors share a single ~12-line adapter; native-SDK vendors get their own module.
5. **Upstream.** The actual vendor APIs. Out of our control, but their churn is absorbed inside Loom.

## Integration

### Installation

```bash
pip install loom-router
```

### Minimum viable usage

```python
from loom import Loom

c = Loom.from_env()  # picks up keys from environment variables

response = c.generate(
    provider="anthropic",
    model="claude-sonnet-4-6",
    prompt="Write three subject lines for a launch email.",
)

print(response["text"])
```

### Programmatic configuration

For projects that don't want to use environment variables:

```python
from loom import Loom, Catalog

catalog = Catalog()
catalog.register_model(
    provider="openai",
    model_id="gpt-5",
    upstream_model="gpt-5-2026-01",
    input_cost_per_1m=2.50,
    output_cost_per_1m=10.00,
)

c = Loom(
    catalog=catalog,
    api_keys={"openai": "sk-...", "anthropic": "sk-ant-..."},
    cache_backend="redis://localhost:6379",
)
```

### Async usage

```python
import asyncio
from loom import Loom

async def main():
    c = Loom.from_env()
    response = await c.agenerate(
        provider="gemini",
        model="gemini-2.5-pro",
        prompt="...",
    )
    return response

asyncio.run(main())
```

### Adding a new provider

Most new providers are OpenAI-compatible. For these, registration is a one-liner:

```python
c.register_openai_compatible(
    key="newco",
    label="NewCo AI",
    base_url="https://api.newco.ai/v1",
    api_key_env="NEWCO_API_KEY",
)
```

For providers with native SDKs or async polling patterns (like BFL or Hunyuan), implement the contract:

```python
# providers/newco_provider.py
def generate(modality: str, model: str, params: dict, prompt: str) -> dict:
    ...
    return {"kind": "text", "text": "..."}
```

Register it once in `providers/__init__.py` and it's available everywhere.

### Framework-agnostic by design

Loom doesn't care what's calling it. It works inside:

- Flask, FastAPI, or Django apps
- Celery workers and background jobs
- CLI scripts
- Jupyter notebooks
- AWS Lambda or other serverless runtimes

There is no web framework lock-in. Loom is a library, not a service — though it can be deployed as a service if a team wants to centralize it behind an internal HTTP API.

## Migration path for existing projects

Loom is designed for incremental adoption. A project doesn't have to rewrite anything to start using it.

**Step 1 — Install and replace the simplest call site.**
Pick one place where the project currently calls a vendor SDK directly. Replace that call with `loom.generate(...)`. Ship it. Verify cost logging shows up in the dashboard.

**Step 2 — Migrate the remaining call sites at the team's own pace.**
There's no "big bang" cutover. Old direct-SDK calls and new Loom calls coexist fine.

**Step 3 — Remove vendor SDKs from the project's dependencies.**
Once all call sites are migrated, the project can drop `openai`, `anthropic`, `google-genai`, etc. from its requirements. Loom owns those dependencies now.

**Step 4 — Opt into optimization features.**
Enable caching, smart routing, or batching per-call or globally. These are off by default to preserve exact behavior during migration, then turned on once the team is comfortable.

## What this delivers

For **engineering**:

- One API to learn, not fourteen
- One place to upgrade SDKs, not N project repos
- One place where retry logic, error handling, and timeouts live
- New AI projects go from "spec" to "first call" in hours

For **finance**:

- Per-project, per-model, per-day cost reporting
- Budget alerts before a runaway prompt empties the account
- Visibility into which optimizations are actually saving money

For **security**:

- API keys live in one audited location
- No vendor credentials in project repos or developer laptops
- Centralized rate limiting prevents one bug from burning the entire org's quota

For **the org**:

- Lower per-call cost via centralized optimization
- Faster product velocity on anything AI-touching
- Insulation from vendor lock-in — switching providers is a config change

## Status

**Loom 2.0.0 is released and stable.** Everything described above is shipped and
installable today with `pip install loom-router`:

- **Packaged and published** — proper Python package on PyPI, 14+ vendors wired up,
  the single `generate(...)` contract live in sync and async.
- **Optimization layer** — response caching, vendor-native prompt caching, batch
  APIs, cross-vendor failover, and request dedup, all toggleable per call.
- **Intelligent routing (new in 2.0)** — intent-based provider/model selection,
  named strategies, health-aware fallback, load balancing, provider benchmarking,
  provider-agnostic structured outputs, and zero-config analytics.
- **Observability** — per-call cost logging and a read-only dashboard blueprint.

The public API documented in [`docs/stability.md`](docs/stability.md) is bound by
semantic versioning: no breaking changes within the 2.x line. Every 2.0 addition is
backward-compatible with 1.x — see [`CHANGELOG.md`](CHANGELOG.md) for the full list
and [`docs/migration_guide.md`](docs/migration_guide.md) for the upgrade path.

Development continues on the [GitHub repository](https://github.com/jyotir07/Loom);
issues and contributions are welcome.
