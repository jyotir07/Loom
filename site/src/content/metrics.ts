export interface Metric {
  value: string;
  label: string;
  hint: string;
}

export const trustMetrics: Metric[] = [
  { value: "14+", label: "AI providers", hint: "OpenAI, Anthropic, Gemini, xAI, Mistral, DeepSeek, BFL, Ideogram…" },
  { value: "1", label: "Unified SDK", hint: "Single stable contract across text and image modalities." },
  { value: "Smart", label: "Routing engine", hint: "Cheap-first, validator-driven, with cross-vendor failover." },
  { value: "100%", label: "Observability", hint: "Cost, latency, tokens, retries — captured on every call." },
];

export const costMetrics: Metric[] = [
  { value: "20–60%", label: "Response cache", hint: "Saved on workloads with repeated queries." },
  { value: "50–90%", label: "Prompt cache", hint: "Discount on cached prefix tokens at the vendor." },
  { value: "50–80%", label: "Smart routing", hint: "Saved on mixed workloads via cheap-first dispatch." },
  { value: "~50%", label: "Batch API", hint: "Cheaper than real-time calls with a ~24h SLA." },
];
