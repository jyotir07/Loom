import type { LucideIcon } from "lucide-react";
import {
  GitBranch,
  ShieldCheck,
  HeartPulse,
  Scale,
  BarChart3,
  Braces,
  Activity,
  Boxes,
  Cable,
  Repeat,
  Database,
  Layers3,
  Fingerprint,
  DollarSign,
  KeyRound,
  Plug,
} from "lucide-react";

export interface Feature {
  title: string;
  body: string;
  icon: LucideIcon;
}

export const features: Feature[] = [
  {
    title: "Intelligent routing",
    body: 'State intent, not a vendor. router="cheapest" | "fastest" | "highest_quality" | "balanced", providers=[...] in order, or just a prompt — Loom picks the provider and model.',
    icon: GitBranch,
  },
  {
    title: "Automatic fallback",
    body: "FallbackPolicy(retries=3, providers=[...]) walks the chain on timeouts, rate limits, and 5xx — each attempt under your retry policy. Cross-vendor equivalence map included.",
    icon: ShieldCheck,
  },
  {
    title: "Health monitoring",
    body: "Per-provider circuit breaker with EWMA latency, rolling failure counts, and rate-limit cooldown. Routing skips open circuits and deprioritizes recovering ones.",
    icon: HeartPulse,
  },
  {
    title: "Load balancing",
    body: "Spread traffic across a pool: round_robin, weighted, least_latency, or least_failures. Wired once via Loom(balancer=...).",
    icon: Scale,
  },
  {
    title: "Provider benchmarking",
    body: "compare(providers=[...], prompt=...) runs candidates concurrently and returns latency, tokens, cost, and output side by side — cheapest, fastest, and best named.",
    icon: BarChart3,
  },
  {
    title: "Structured outputs",
    body: "generate(schema=User) returns a validated Pydantic model, not a dict. Native response_format, tool-JSON, and response_schema per provider, with prompt-driven fallback.",
    icon: Braces,
  },
  {
    title: "Analytics & observability",
    body: "client.analytics() — summary, by-provider, by-model, recent — over a zero-config in-memory sink. Plus a SQLite sink and read-only Flask dashboard for history.",
    icon: Activity,
  },
  {
    title: "Unified AI API",
    body: "One stable contract — generate(provider, model, prompt) — across every vendor and modality. The explicit path is unchanged and fully supported in v2.",
    icon: Boxes,
  },
  {
    title: "Native SDK preservation",
    body: "Each vendor integrated with its native SDK. Prompt caching, grounding, streaming — preserved, not flattened.",
    icon: Cable,
  },
  {
    title: "Centralized retries",
    body: "Exponential backoff with jitter, configurable per client. RetryPolicy(max_attempts=3, base_delay=0.5).",
    icon: Repeat,
  },
  {
    title: "Prompt caching",
    body: "Vendor-native prompt caching for OpenAI, Anthropic, DeepSeek, and Gemini — discounts already applied in cost.",
    icon: Database,
  },
  {
    title: "Batch processing",
    body: "OpenAI and Anthropic batch endpoints behind a single submit_batch() with poll and wait primitives.",
    icon: Layers3,
  },
  {
    title: "Request deduplication",
    body: "Single-flight coalescing collapses identical concurrent calls into one upstream request.",
    icon: Fingerprint,
  },
  {
    title: "Cost tracking",
    body: "Every result carries cost.usd and cost.local computed from the catalog. Pricing tracked per model.",
    icon: DollarSign,
  },
  {
    title: "API key centralization",
    body: "AWS Secrets Manager, GCP Secret Manager, and HashiCorp Vault backends in the box. Keys live in one place.",
    icon: KeyRound,
  },
  {
    title: "OpenAI-compatible adapters",
    body: "Register any OpenAI-shape vendor in ~10 lines with register_openai_compatible(key, base_url, env).",
    icon: Plug,
  },
];
