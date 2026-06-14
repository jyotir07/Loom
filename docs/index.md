# Loom

*One contract for every AI vendor.*

```python
import loom

result = loom.generate(
    provider="openai",
    modality="text",
    model="gpt-4o-mini",
    prompt="Say hi in five words.",
)
print(result["text"])
print(result["cost"]["usd"])
```

Same call shape for OpenAI, Anthropic, Gemini, xAI, Mistral, DeepSeek,
Perplexity, Together, and 14+ other vendors. Native SDKs preserved so
vendor-specific features (prompt caching, grounding, image polling,
streaming, structured output) are kept — not flattened.

---

## The idea

Every team building with AI ends up writing the same plumbing: pick a
provider, learn their SDK, manage their keys, handle their errors,
track their costs, repeat for the next provider. Multiply across a
dozen projects and the company is paying for the same integration work
over and over.

Loom is a Python library that sits between your projects and the AI
providers. Projects make one kind of call. Loom handles the rest:
which vendor, which model, which SDK, which retry policy, which cache,
which batch endpoint. New providers, new models, and new optimizations
land in Loom and every consumer inherits them.

It is **not** an aggregator. Each vendor is integrated with its own
native SDK so vendor-specific capabilities are preserved.

---

## What Loom gives you for free

- **Unified contract** — one `generate(...)` for every provider.
- **Cost on every call** — `result["cost"]` in USD and your local
  currency.
- **Structured logs** — one INFO line per call with provider, model,
  latency, tokens, cost.
- **Retry + cache + dedup** — exponential backoff with jitter,
  in-process or Redis cache, single-flight request coalescing.
- **Vendor-native prompt caching** — automatic for OpenAI/DeepSeek,
  opt-in for Anthropic, discounted in `cost`.
- **Batch API** — OpenAI and Anthropic batch endpoints behind one
  `client.submit_batch(...)`.
- **Context cache** — Gemini `CachedContent` resource lifecycle via
  `client.create_context_cache(...)`.
- **Smart routing** — cheap-first with caller-supplied validator;
  cross-vendor failover via a bundled equivalence map.
- **Async** — every call has a sibling `agenerate(...)`.
- **Key vault** — AWS Secrets Manager / GCP Secret Manager /
  HashiCorp Vault backends ship in the box.
- **Observability** — SQLite event sink + Flask Blueprint dashboard
  with cost / latency / cache / dedup rollups.

---

## Install

```bash
pip install "loom[openai]"      # or loom[all] for every supported vendor
```

Extras are optional dependency groups: `openai`, `anthropic`, `gemini`,
`tencent`, `yaml`, `redis`, `all`. Loom itself has only `requests` and
`python-dotenv` as hard deps.

---

## Next steps

- **[Getting started](migration_guide.md)** — incremental adoption playbook.
- **[API reference](api_reference.md)** — full surface.
- **[Stability](stability.md)** — v1.0 commitment, what's public, what isn't.
- **[Roadmap](roadmap.md)** — phases shipped and what's next.

---

## License & contact

Proprietary © Eyas Ventures. See repo for license details.
