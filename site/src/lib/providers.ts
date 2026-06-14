export type ProviderCategory = "text" | "image" | "both";

export interface Provider {
  key: string;
  label: string;
  short: string;
  category: ProviderCategory;
  accent: string;
}

export const providers: Provider[] = [
  { key: "openai", label: "OpenAI", short: "OAI", category: "both", accent: "#10a37f" },
  { key: "anthropic", label: "Anthropic", short: "ANT", category: "text", accent: "#d97757" },
  { key: "gemini", label: "Gemini", short: "GEM", category: "both", accent: "#4285f4" },
  { key: "xai", label: "xAI Grok", short: "XAI", category: "text", accent: "#e4e4e7" },
  { key: "mistral", label: "Mistral", short: "MST", category: "text", accent: "#ff7a00" },
  { key: "deepseek", label: "DeepSeek", short: "DSK", category: "text", accent: "#7c3aed" },
  { key: "minimax", label: "MiniMax", short: "MNM", category: "text", accent: "#22d3ee" },
  { key: "zai", label: "Z.AI", short: "ZAI", category: "text", accent: "#f43f5e" },
  { key: "bfl", label: "Black Forest Labs", short: "BFL", category: "image", accent: "#a3e635" },
  { key: "ideogram", label: "Ideogram", short: "IDG", category: "image", accent: "#f59e0b" },
  { key: "bytedance", label: "ByteDance Seedream", short: "BYT", category: "image", accent: "#06b6d4" },
  { key: "tencent", label: "Tencent Hunyuan", short: "TNC", category: "image", accent: "#ec4899" },
];
