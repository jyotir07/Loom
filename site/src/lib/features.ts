import type { LucideIcon } from "lucide-react";
import {
  Boxes,
  Cable,
  GitBranch,
  Repeat,
  ShieldCheck,
  Database,
  Layers3,
  Fingerprint,
  DollarSign,
  Activity,
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
    title: "Unified AI API",
    body: "One stable contract — generate(provider, model, prompt) — across every vendor and modality.",
    icon: Boxes,
  },
  {
    title: "Native SDK preservation",
    body: "Each vendor integrated with its native SDK. Prompt caching, grounding, streaming — preserved, not flattened.",
    icon: Cable,
  },
  {
    title: "Smart model routing",
    body: "Cheap-first router with caller-supplied validators. Tries candidates in order, returns the first that passes.",
    icon: GitBranch,
  },
  {
    title: "Centralized retries",
    body: "Exponential backoff with jitter, configurable per client. RetryPolicy(max_attempts=3, base_delay=0.5).",
    icon: Repeat,
  },
  {
    title: "Vendor failover",
    body: "Cross-vendor failover via a bundled equivalence map. When OpenAI is down, Anthropic answers instead.",
    icon: ShieldCheck,
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
    title: "Unified observability",
    body: "Structured INFO line per call: provider, model, latency, tokens, cost. SQLite sink + Flask dashboard.",
    icon: Activity,
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
