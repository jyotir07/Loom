import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Navbar } from "@/components/nav/Navbar";
import { Footer } from "@/components/sections/Footer";
import { CodeBlock } from "@/components/ui/CodeBlock";

export const metadata: Metadata = {
  title: "Docs — Loom",
  description:
    "How to use Loom: install, configure, call generate(), handle responses, and turn on caching, routing, batching, and observability.",
};

const toc = [
  { id: "overview", label: "Mental model" },
  { id: "install", label: "Install" },
  { id: "calling", label: "Three ways to call" },
  { id: "keys", label: "Configuring API keys" },
  { id: "generate", label: "The generate call" },
  { id: "response", label: "Response shape" },
  { id: "async", label: "Async" },
  { id: "errors", label: "Error handling" },
  { id: "catalog", label: "Custom catalogs" },
  { id: "optimize", label: "Optimization features" },
  { id: "observability", label: "Observability" },
];

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28 border-b border-white/5 pb-14 mb-14 last:border-none">
      <h2 className="text-2xl md:text-3xl font-semibold tracking-tight text-gradient mb-5">
        {title}
      </h2>
      <div className="space-y-4 text-[15px] leading-relaxed text-white/70">
        {children}
      </div>
    </section>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-base font-semibold text-white/90 mt-8 mb-3 tracking-tight">
      {children}
    </h3>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded-md border border-white/10 bg-white/[0.05] px-1.5 py-0.5 text-[13px] font-mono text-electric-400">
      {children}
    </code>
  );
}

export default function DocsPage() {
  return (
    <main className="relative">
      <Navbar />

      {/* Background texture, matched to the landing page */}
      <div className="pointer-events-none fixed inset-0 -z-10 bg-grid mask-radial-fade opacity-[0.12]" />
      <div className="glow-orb -z-10 h-[420px] w-[420px] -top-32 left-1/2 -translate-x-1/2 bg-electric-500/20" />

      <div className="relative mx-auto max-w-7xl px-6 pt-36 pb-10">
        <header className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs font-mono uppercase tracking-[0.18em] text-white/60">
            <span className="h-1.5 w-1.5 rounded-full bg-electric-500 animate-pulse-soft" />
            Documentation
          </span>
          <h1 className="mt-5 text-4xl md:text-5xl font-semibold tracking-tight text-gradient">
            Using Loom
          </h1>
          <p className="mt-4 text-lg text-white/60 leading-relaxed">
            One contract for every AI vendor. This guide takes you from install
            to production — calling{" "}
            <Code>generate()</Code>, reading the response, and turning on the
            optimization layer.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link
              href="https://github.com/jyotir07/Loom"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-white text-ink-950 px-4 py-2 text-sm font-medium hover:bg-white/90 transition-colors"
            >
              GitHub <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/#dx"
              className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-4 py-2 text-sm text-white/80 hover:bg-white/[0.08] transition-colors"
            >
              Code samples
            </Link>
          </div>
        </header>
      </div>

      <div className="relative mx-auto max-w-7xl px-6 pb-24">
        <div className="grid grid-cols-1 lg:grid-cols-[210px_minmax(0,1fr)] gap-12">
          {/* Sidebar TOC */}
          <aside className="hidden lg:block">
            <nav className="sticky top-28 border-l border-white/10 pl-5">
              <span className="block text-[11px] font-mono uppercase tracking-[0.2em] text-white/40 mb-4">
                On this page
              </span>
              <ul className="space-y-1">
                {toc.map((t) => (
                  <li key={t.id}>
                    <a
                      href={`#${t.id}`}
                      className="block py-1 text-sm text-white/55 hover:text-white transition-colors"
                    >
                      {t.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>

          {/* Content */}
          <article className="min-w-0 max-w-3xl">
            <Section id="overview" title="The mental model">
              <p>
                Loom gives you <strong className="text-white/90">one function</strong>{" "}
                for every provider:
              </p>
              <CodeBlock
                language="python"
                filename="quickstart.py"
                code={`import loom

result = loom.generate(
    provider="openai",
    modality="text",
    model="gpt-4o-mini",
    prompt="Say hi in five words.",
)
print(result["text"])
print(result["cost"]["usd"])`}
              />
              <p>
                Four things identify <em>what</em> to run — <Code>provider</Code>,{" "}
                <Code>modality</Code>, <Code>model</Code>, <Code>prompt</Code> — and
                the return shape is the same no matter which vendor answered.
                Everything else (keys, retries, caching, cost accounting, logging)
                is handled inside Loom.
              </p>
              <ul className="list-disc pl-5 space-y-2 marker:text-white/30">
                <li>
                  <strong className="text-white/90">Catalog</strong> — the list of
                  models Loom knows about. A <Code>model</Code> string like{" "}
                  <Code>gpt-4o-mini</Code> resolves to an upstream model ID plus
                  default params.
                </li>
                <li>
                  <strong className="text-white/90">Provider adapter</strong> — the
                  per-vendor module that makes the call with the vendor&apos;s native
                  SDK.
                </li>
                <li>
                  <strong className="text-white/90">Loom client</strong> — ties a
                  catalog, your API keys, and the optimization layer together. The
                  module-level <Code>loom.generate(...)</Code> runs on a default
                  client built from your environment.
                </li>
              </ul>
            </Section>

            <Section id="install" title="Install">
              <CodeBlock
                language="bash"
                filename="terminal"
                code={`pip install "loom-router[openai]"      # one vendor
pip install "loom-router[all]"         # every supported vendor`}
              />
              <p>
                Extras are optional dependency groups: <Code>openai</Code>,{" "}
                <Code>anthropic</Code>, <Code>gemini</Code>, <Code>tencent</Code>,{" "}
                <Code>yaml</Code>, <Code>redis</Code>, <Code>all</Code>. Loom&apos;s
                only hard dependencies are <Code>requests</Code> and{" "}
                <Code>python-dotenv</Code>, so installing with no extra gives you the
                catalog and dispatcher but no vendor SDK.
              </p>
            </Section>

            <Section id="calling" title="Three ways to call">
              <p>
                All three share the same catalog, cost computation, and logging —
                pick based on how much control you need over configuration.
              </p>

              <H3>Module-level — simplest</H3>
              <p>
                Runs on a default client built from <Code>Loom.from_env()</Code>.
                Best for scripts and notebooks.
              </p>
              <CodeBlock
                language="python"
                code={`import loom

result = loom.generate(
    provider="anthropic",
    modality="text",
    model="claude-sonnet-4-6",
    prompt="Write three subject lines for a launch email.",
)`}
              />

              <H3>from_env — long-lived</H3>
              <p>
                Build one client at startup and reuse it. Best for web apps and
                workers — avoids re-reading config on every call.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import Loom

client = Loom.from_env()        # reads keys from .env + environment

result = client.generate(
    provider="anthropic",
    modality="text",
    model="claude-sonnet-4-6",
    prompt="...",
)`}
              />

              <H3>Explicit construction</H3>
              <p>
                Pass everything in directly — keys, catalog, cache. Best when config
                comes from a secrets manager rather than the environment.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import Loom

client = Loom(
    api_keys={"OPENAI_API_KEY": "sk-...", "ANTHROPIC_API_KEY": "sk-ant-..."},
    local_currency="USD",
    local_to_usd=1.0,
)`}
              />
            </Section>

            <Section id="keys" title="Configuring API keys">
              <p>
                Loom looks for a vendor key in three places, in order: the{" "}
                <Code>api_keys</Code> dict you passed the client, the process
                environment, then an optional vault backend. Keys use the standard
                vendor names (<Code>OPENAI_API_KEY</Code>,{" "}
                <Code>ANTHROPIC_API_KEY</Code>, <Code>GEMINI_API_KEY</Code>, …).
              </p>

              <H3>Environment / .env — the default</H3>
              <p>
                <Code>Loom.from_env()</Code> loads a <Code>.env</Code> file from the
                working directory if present, without overriding values already set
                in the environment.
              </p>
              <CodeBlock
                language="bash"
                filename=".env"
                code={`OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...`}
              />

              <H3>Programmatic</H3>
              <p>
                Pass keys in; they win over the environment — the right hook for
                services pulling secrets at boot.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import Loom

client = Loom(api_keys={
    "OPENAI_API_KEY": secrets_manager.get("openai/prod"),
})`}
              />

              <H3>Vault</H3>
              <p>
                Point Loom at a bundled backend (AWS Secrets Manager, GCP Secret
                Manager, HashiCorp Vault) and let it fetch keys lazily, cached
                in-process with a 5-minute TTL.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import Loom, AWSSecretsManagerVault

client = Loom.from_env(
    vault=AWSSecretsManagerVault(region_name="us-east-1", prefix="prod/loom/"),
)`}
              />
            </Section>

            <Section id="generate" title="The generate call">
              <CodeBlock
                language="python"
                code={`client.generate(
    provider="openai",     # vendor key
    modality="text",       # "text" | "image" | "video"
    model="gpt-4o-mini",   # catalog model id
    prompt="...",          # the user prompt
    params={...},          # optional, merged over catalog defaults
    use_cache=True,        # optional, per-call cache opt-out
)`}
              />
              <ul className="list-disc pl-5 space-y-2 marker:text-white/30">
                <li>
                  <Code>params</Code> is merged on top of the catalog defaults for
                  that model, so you only specify what you want to override
                  (<Code>max_tokens</Code>, <Code>temperature</Code>,
                  vendor-specific flags like <Code>system</Code>, <Code>size</Code>).
                </li>
                <li>
                  <Code>use_cache=False</Code> forces a fresh upstream call even when
                  a cache is configured.
                </li>
                <li>
                  Some catalog model IDs bake params in. For example{" "}
                  <Code>gpt-image-1-low</Code> sets <Code>quality=low</Code> for you —
                  you can still override via <Code>params</Code>.
                </li>
              </ul>
            </Section>

            <Section id="response" title="The response shape">
              <p>
                Every successful call returns a dict with a <Code>kind</Code>{" "}
                discriminator plus <Code>usage</Code> and <Code>cost</Code>.
              </p>
              <H3>Text</H3>
              <CodeBlock
                language="python"
                code={`{
    "kind": "text",
    "text": "...",
    "usage": {"input_tokens": 12, "output_tokens": 30, "cached_tokens": 0},
    "cost": {"usd": 0.000028, "local": 0.0023, "local_currency": "INR"},
}`}
              />
              <H3>Image</H3>
              <CodeBlock
                language="python"
                code={`{
    "kind": "image",
    "images": [{"mime_type": "image/png", "data_b64": "..."}],
    "cost": {"usd": 0.01, "local": 0.83, "local_currency": "INR"},
}`}
              />
              <p>Cost is reported in USD and a configurable local currency (default INR):</p>
              <CodeBlock
                language="python"
                code={`Loom(local_currency="USD", local_to_usd=1.0)    # report USD only
Loom(local_currency="EUR", local_to_usd=1.08)   # 1 EUR ~= 1.08 USD`}
              />
            </Section>

            <Section id="async" title="Async">
              <p>
                Every call has an async sibling. Use the module-level{" "}
                <Code>agenerate</Code>, or an <Code>AsyncLoom</Code> client for a
                long-lived service.
              </p>
              <CodeBlock
                language="python"
                filename="api.py"
                code={`import asyncio
from loom import AsyncLoom

aclient = AsyncLoom.from_env()

async def main():
    result = await aclient.generate(
        provider="gemini",
        modality="text",
        model="gemini-2.5-pro",
        prompt="...",
    )
    return result["text"]

asyncio.run(main())`}
              />
            </Section>

            <Section id="errors" title="Error handling">
              <p>
                Loom maps each vendor&apos;s exception hierarchy onto one shared set,
                so you catch the same types regardless of provider.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import AuthError, RateLimitError, ModelNotFoundError, ProviderError

try:
    result = loom.generate(provider=..., modality=..., model=..., prompt=...)
except AuthError:
    ...            # missing / invalid key - a config problem
except RateLimitError:
    ...            # back off, retry, or fail over to another model
except ModelNotFoundError:
    ...            # catalog doesn't know that (provider, modality, model)
except ProviderError:
    ...            # anything else from the upstream call`}
              />
            </Section>

            <Section id="catalog" title="Custom catalogs">
              <p>
                To run your own model list (different pricing, internal IDs, an
                approved subset), point Loom at a YAML file. The schema matches the
                bundled catalog.
              </p>
              <CodeBlock
                language="yaml"
                filename="models.yaml"
                code={`openai:
  label: OpenAI
  modalities:
    text:
      - id: small
        name: Cheap default
        model: gpt-4o-mini
        input_inr_per_1m: 14.4578
        output_inr_per_1m: 57.8312`}
              />
              <CodeBlock
                language="python"
                code={`from loom import Loom, Catalog

client = Loom(catalog=Catalog.from_yaml("models.yaml"))
client.generate(provider="openai", modality="text", model="small", prompt="hi")`}
              />
              <p>
                You can also register models programmatically with{" "}
                <Code>catalog.register_model(...)</Code>.
              </p>
            </Section>

            <Section id="optimize" title="Optimization features">
              <p>
                These are off (cache) or on with safe defaults (retry, dedup). Turn
                them on once your behavior is stable. Each composes with the others.
              </p>

              <H3>Response cache</H3>
              <p>
                Identical <Code>(provider, model, prompt, params)</Code> calls hit
                the cache instead of the API.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import Loom, InMemoryCache, RedisCache

client = Loom(cache=InMemoryCache(maxsize=10_000, ttl=3600))

# multi-process deployments - share the cache across workers
client = Loom(cache=RedisCache(url="redis://internal:6379/0", ttl=3600))`}
              />

              <H3>Vendor prompt caching</H3>
              <p>
                OpenAI and DeepSeek cache long prompt prefixes automatically — the
                saving shows up in <Code>result[&quot;usage&quot;][&quot;cached_tokens&quot;]</Code>{" "}
                and is already discounted in <Code>result[&quot;cost&quot;]</Code>.
                Anthropic is opt-in:
              </p>
              <CodeBlock
                language="python"
                code={`loom.generate(
    provider="anthropic", modality="text", model="claude-haiku-4-5",
    prompt=user_question,
    params={"system": LONG_STATIC_SYSTEM_PROMPT, "cache_system": True},
)`}
              />
              <p>
                Gemini uses an uploaded context-cache <em>resource</em> referenced by
                ID — the right shape when one big context answers many small
                questions:
              </p>
              <CodeBlock
                language="python"
                code={`cache = client.create_context_cache(
    provider="gemini", model="gemini-2.5-flash",
    contents=long_static_document, ttl_seconds=600,
)
result = client.generate(
    provider="gemini", modality="text", model="gemini-2.5-flash",
    prompt=user_question, params={"cached_content": cache.id},
)
client.delete_context_cache(cache)`}
              />

              <H3>Cheap-first routing</H3>
              <p>
                Try a small model first; escalate only when a validator says the
                answer isn&apos;t good enough.
              </p>
              <CodeBlock
                language="python"
                code={`from loom import Loom, Router

router = Router(
    candidates=[
        ("openai", "text", "gpt-4o-mini"),   # try cheap first
        ("openai", "text", "gpt-4o"),        # escalate
    ],
    validator=lambda result: "I don't know" not in result["text"],
)

result = Loom.from_env().route(router, prompt=user_question)
print(result["_router"]["used"])   # which model actually answered`}
              />

              <H3>Cross-vendor failover</H3>
              <p>Stay up when one vendor flakes by falling through an equivalence map.</p>
              <CodeBlock
                language="python"
                code={`from loom import Loom, Router

router = Router.failover(provider="openai", modality="text", model="gpt-4o-mini")
result = Loom.from_env().route(router, prompt=question)`}
              />
              <p>
                Loom tries OpenAI first; on failure it falls through bundled
                equivalents (<Code>claude-haiku-4-5</Code>, <Code>gemini-2.5-flash</Code>,{" "}
                <Code>deepseek-v3</Code> by default). You need keys for every vendor
                in the chain.
              </p>

              <H3>Batch API</H3>
              <p>
                For workloads that tolerate ~24h latency, vendor batch endpoints are
                ~50% cheaper. OpenAI and Anthropic batch adapters ship today.
              </p>
              <CodeBlock
                language="python"
                filename="batch.py"
                code={`from loom import Loom, BatchRequest

client = Loom.from_env()

handle = client.submit_batch([
    BatchRequest(provider="openai", modality="text",
                 model="gpt-4o-mini", prompt=text, custom_id=row_id)
    for row_id, text in rows
])
results = handle.wait()          # aligned to input order; pick up later via handle.id

# or block until done:
results = client.run_batch(requests, poll_interval=60.0)`}
              />

              <H3>Per-call opt-outs</H3>
              <CodeBlock
                language="python"
                code={`client.generate(..., use_cache=False)   # skip the cache for this call
Loom(dedup=False)                       # don't coalesce concurrent identical calls
Loom(retry=None)                        # don't retry on rate limits`}
              />
            </Section>

            <Section id="observability" title="Observability">
              <p>
                Turn on the bundled SQLite sink + Flask dashboard for a queryable
                record of every call and a one-page cost/latency/cache summary.
              </p>
              <CodeBlock
                language="python"
                filename="admin.py"
                code={`import logging
from flask import Flask
from loom.observability import SQLiteSink, LoomLogHandler, make_dashboard

sink = SQLiteSink("loom_events.db")
logging.getLogger("loom").addHandler(LoomLogHandler(sink))

app = Flask(__name__)
app.register_blueprint(make_dashboard(sink), url_prefix="/loom-admin")`}
              />
              <p>
                Every call now lands in <Code>loom_events.db</Code>, and{" "}
                <Code>/loom-admin/</Code> shows cost by provider, top spend by model,
                cache-hit rate, dedup rate, and the last 25 calls. The dashboard
                ships without auth — wrap it in your host app&apos;s login like any
                internal admin page.
              </p>
            </Section>
          </article>
        </div>
      </div>

      <Footer />
    </main>
  );
}
