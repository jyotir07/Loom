"""Catalog of providers and the models they expose, grouped by modality.

Schema for each model entry:
    {
        "id":     str  - stable identifier sent from the UI to the backend
        "name":   str  - human-readable label shown in the dropdown
        "model":  str  - (optional) real model ID passed to the upstream API.
                         If omitted, "id" is used.
        "params": dict - (optional) extra params merged into the upstream call
                         (e.g. {"quality": "high"} for OpenAI tiers).
    }

Add new providers or models here. The frontend reads this via /api/catalog
and uses it to populate the provider / modality / model dropdowns.

Note: vendor model IDs change frequently and some entries below are best
guesses based on each vendor's naming convention. If an upstream call 4xxs
with "model not found", update the `model` field — no other code change
should be needed.
"""

CATALOG = {
    "openai": {
        "label": "OpenAI",
        "modalities": {
            "text": [
                {"id": "gpt-5-nano",  "name": "GPT-5 nano",
                 "input_inr_per_1m": 4.8193, "output_inr_per_1m": 38.5541},
                {"id": "gpt-4.1-nano","name": "GPT-4.1 nano",
                 "input_inr_per_1m": 9.6385, "output_inr_per_1m": 38.5541},
                {"id": "gpt-4o-mini", "name": "GPT-4o mini",
                 "input_inr_per_1m": 14.4578, "output_inr_per_1m": 57.8312},
                {"id": "gpt-5-mini",  "name": "GPT-5 mini",
                 "input_inr_per_1m": 24.0963, "output_inr_per_1m": 192.7706},
                {"id": "gpt-4.1-mini","name": "GPT-4.1 mini",
                 "input_inr_per_1m": 38.5541, "output_inr_per_1m": 154.2165},
                {"id": "gpt-4o",      "name": "GPT-4o",
                 "input_inr_per_1m": 241.25, "output_inr_per_1m": 965.00},
                {"id": "gpt-4.1",     "name": "GPT-4.1",
                 "input_inr_per_1m": 193.00, "output_inr_per_1m": 772.00},
                {"id": "gpt-5",       "name": "GPT-5 (high)",
                 "model": "gpt-5", "params": {"reasoning_effort": "high"},
                 "input_inr_per_1m": 120.4816, "output_inr_per_1m": 963.8530},
                {"id": "gpt-5.1",     "name": "GPT-5.1",
                 "input_inr_per_1m": 120.4816, "output_inr_per_1m": 963.8530},
                {"id": "gpt-5.2-codex","name": "GPT-5.2 / 5.3 Codex",
                 "model": "gpt-5.2-codex",
                 "input_inr_per_1m": 168.6743, "output_inr_per_1m": 1349.3942},
                {"id": "o3",          "name": "o3",
                 "input_inr_per_1m": 192.7706, "output_inr_per_1m": 771.0824},
                {"id": "gpt-5.4",     "name": "GPT-5.4",
                 "input_inr_per_1m": 240.9633, "output_inr_per_1m": 1445.7795},
                {"id": "gpt-5.5",     "name": "GPT-5.5",
                 "input_inr_per_1m": 481.9265, "output_inr_per_1m": 2891.5590},
                {"id": "gpt-5.4-pro", "name": "GPT-5.4 Pro / 5.5 Pro",
                 "model": "gpt-5.5-pro",
                 "input_inr_per_1m": 2891.5590, "output_inr_per_1m": 17349.3540},
                {"id": "o1-pro",      "name": "o1-pro",
                 "input_inr_per_1m": 14457.7950, "output_inr_per_1m": 57831.1800},
                {"id": "gpt-3.5-turbo","name": "GPT-3.5 Turbo",
                 "input_inr_per_1m": 48.25, "output_inr_per_1m": 144.75},
                {"id": "gpt-4-turbo", "name": "GPT-4 Turbo",
                 "input_inr_per_1m": 965.00, "output_inr_per_1m": 2895.00},
            ],
            "image": [
                {"id": "gpt-image-1-mini-low",
                 "name": "GPT Image 1 Mini (Low)",
                 "model": "gpt-image-1-mini",
                 "params": {"quality": "low"},
                 "cost_inr": 0.4819265},
                {"id": "gpt-image-1-low",
                 "name": "GPT Image 1 (Low)",
                 "model": "gpt-image-1",
                 "params": {"quality": "low"},
                 "cost_inr": 1.0602383},
                {"id": "gpt-image-1-medium",
                 "name": "GPT Image 1 (Medium)",
                 "model": "gpt-image-1",
                 "params": {"quality": "medium"},
                 "cost_inr": 4.0481826},
                {"id": "gpt-image-1-high",
                 "name": "GPT Image 1 (High)",
                 "model": "gpt-image-1",
                 "params": {"quality": "high"},
                 "cost_inr": 16.0963431},
                {"id": "gpt-image-1-5-std",
                 "name": "GPT Image 1.5 (Std)",
                 "model": "gpt-image-1.5",
                 "params": {"quality": "standard"},
                 "cost_inr": 3.855412},
                {"id": "dall-e-3", "name": "DALL-E 3 (Std)",
                 "model": "dall-e-3",
                 "params": {"quality": "standard"},
                 "cost_inr": 3.855412},
                {"id": "dall-e-2", "name": "DALL-E 2", "model": "dall-e-2",
                 "cost_inr": 1.93},
            ],
        },
    },
    "gemini": {
        "label": "Google Gemini",
        "modalities": {
            "text": [
                {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash-Lite",
                 "input_inr_per_1m": 9.6385, "output_inr_per_1m": 38.5541},
                {"id": "gemini-2.5-flash",      "name": "Gemini 2.5 Flash",
                 "input_inr_per_1m": 14.4578, "output_inr_per_1m": 57.8312},
                {"id": "gemini-3-flash",        "name": "Gemini 3 Flash",
                 "input_inr_per_1m": 48.1927, "output_inr_per_1m": 289.1559},
                {"id": "gemini-2.5-pro",        "name": "Gemini 2.5 Pro",
                 "input_inr_per_1m": 120.4816, "output_inr_per_1m": 963.8530},
                {"id": "gemini-3.1-pro",        "name": "Gemini 3.1 Pro",
                 "input_inr_per_1m": 192.7706, "output_inr_per_1m": 1156.6236},
                {"id": "gemini-2.0-flash",      "name": "Gemini 2.0 Flash",      "free": True},
                {"id": "gemini-1.5-pro",        "name": "Gemini 1.5 Pro",        "free": True},
                {"id": "gemini-1.5-flash",      "name": "Gemini 1.5 Flash",      "free": True},
            ],
            "image": [
                {"id": "imagen-4.0-fast-generate-001",
                 "name": "Imagen 4 Fast", "cost_inr": 1.927706},
                {"id": "imagen-4.0-generate-001",
                 "name": "Imagen 4 Standard", "cost_inr": 3.855412},
                {"id": "imagen-4.0-ultra-generate-001",
                 "name": "Imagen 4 Ultra", "cost_inr": 5.783118},
                {"id": "gemini-3-pro-image-preview",
                 "name": "Gemini 3 Pro Image", "cost_inr": 3.3734855},
            ],
            "video": [
                {"id": "veo-3.0-fast-generate-001",
                 "name": "Veo 3 Fast", "cost_inr": 14.48},
                {"id": "veo-3.0-generate-001",
                 "name": "Veo 3", "cost_inr": 38.60},
                {"id": "veo-2.0-generate-001",
                 "name": "Veo 2", "cost_inr": 33.78},
            ],
        },
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "modalities": {
            "text": [
                {"id": "claude-haiku-4-5",
                 "name": "Claude Haiku 4.5",
                 "model": "claude-haiku-4-5-20251001",
                 "input_inr_per_1m": 96.3853, "output_inr_per_1m": 481.9265},
                {"id": "claude-sonnet-4-6",
                 "name": "Claude Sonnet 4.6",
                 "model": "claude-sonnet-4-6",
                 "input_inr_per_1m": 289.1559, "output_inr_per_1m": 1445.7795},
                {"id": "claude-opus-4-7",
                 "name": "Claude Opus 4.7",
                 "model": "claude-opus-4-7",
                 "input_inr_per_1m": 481.9265, "output_inr_per_1m": 2409.6325},
                {"id": "claude-opus-4-1",
                 "name": "Claude 4.1 Opus",
                 "model": "claude-opus-4-1-20250805",
                 "input_inr_per_1m": 1445.7795, "output_inr_per_1m": 7228.8975},
                {"id": "claude-mythos-preview",
                 "name": "Claude Mythos Preview",
                 "model": "claude-mythos-preview",
                 "input_inr_per_1m": 2409.6325, "output_inr_per_1m": 12048.1625},
            ],
            "image": [],
        },
    },
    "xai": {
        "label": "xAI (Grok)",
        "modalities": {
            "text": [
                {"id": "grok-4-fast", "name": "Grok 4.1 Fast",
                 "model": "grok-4-fast",
                 "input_inr_per_1m": 19.2771, "output_inr_per_1m": 48.1927},
            ],
            "image": [],
        },
    },
    "mistral": {
        "label": "Mistral",
        "modalities": {
            "text": [
                {"id": "ministral-3b",   "name": "Ministral 3 3B",
                 "model": "ministral-3b-latest",
                 "input_inr_per_1m": 9.6385, "output_inr_per_1m": 9.6385},
                {"id": "mistral-large-3","name": "Mistral Large 3",
                 "model": "mistral-large-latest",
                 "input_inr_per_1m": 48.1927, "output_inr_per_1m": 144.5780},
            ],
            "image": [],
        },
    },
    "deepseek": {
        "label": "DeepSeek",
        "modalities": {
            "text": [
                {"id": "deepseek-v3",     "name": "DeepSeek V3",
                 "model": "deepseek-chat",
                 "input_inr_per_1m": 26.0240, "output_inr_per_1m": 106.0238},
                {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro",
                 "model": "deepseek-reasoner",
                 "input_inr_per_1m": 167.7104, "output_inr_per_1m": 335.4208},
            ],
            "image": [],
        },
    },
    "minimax": {
        "label": "MiniMax",
        "modalities": {
            "text": [
                {"id": "minimax-m2.7", "name": "MiniMax M2.7",
                 "model": "MiniMax-M2.7",
                 "input_inr_per_1m": 28.9156, "output_inr_per_1m": 115.6624},
            ],
            "image": [],
        },
    },
    "zhipu": {
        "label": "Z.AI (GLM)",
        "modalities": {
            "text": [
                {"id": "glm-5-reasoning", "name": "GLM-5 (Reasoning)",
                 "model": "glm-5-reasoning",
                 "input_inr_per_1m": 96.3853, "output_inr_per_1m": 308.4330},
            ],
            "image": [],
        },
    },
    "bfl": {
        "label": "Black Forest Labs",
        "modalities": {
            "text": [],
            "image": [
                {"id": "flux-2-klein-4b", "name": "Flux 2 Klein 4B (fast)",
                 "cost_inr": 1.4457795},
                {"id": "flux-2-klein-9b", "name": "Flux 2 Klein 9B",
                 "cost_inr": 1.45},
                {"id": "flux-2-flex", "name": "Flux 2 Flex (dev)",
                 "cost_inr": 2.4096325},
                {"id": "flux-2-pro", "name": "Flux 2 Pro",
                 "cost_inr": 5.3011915},
                {"id": "flux-2-max", "name": "Flux 2 Max",
                 "cost_inr": 6.76},
                {"id": "flux-pro-1.1", "name": "Flux 1.1 Pro",
                 "cost_inr": 3.86},
            ],
        },
    },
    "seedream": {
        "label": "ByteDance Seedream",
        "modalities": {
            "text": [],
            "image": [
                {"id": "doubao-seedream-4-5",
                 "name": "Seedream 4.5",
                 "model": "doubao-seedream-4-5-t2i-250115",
                 "cost_inr": 3.3734855},
            ],
        },
    },
    "hunyuan": {
        "label": "Tencent Hunyuan",
        "modalities": {
            "text": [],
            "image": [
                {"id": "hunyuan-image-3.0", "name": "Hunyuan Image 3.0",
                 "cost_inr": 2.891559},
            ],
        },
    },
    "ideogram": {
        "label": "Ideogram",
        "modalities": {
            "text": [],
            "image": [
                {"id": "V_2", "name": "Ideogram 2.0", "cost_inr": 3.855412},
            ],
        },
    },
    "perplexity": {
        "label": "Perplexity",
        "modalities": {
            "text": [
                {"id": "sonar", "name": "sonar",
                 "input_inr_per_1m": 96.50, "output_inr_per_1m": 96.50},
            ],
        },
    },
    "together": {
        "label": "Together AI",
        "modalities": {
            "text": [
                {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "name": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                 "input_inr_per_1m": 84.92, "output_inr_per_1m": 84.92},
            ],
        },
    },
    "kimi": {
        "label": "Kimi ( Moonshot )",
        "modalities": {
            "text": [
                {"id": "kimi-k2-0905-preview", "name": "kimi K2"},
            ],
        },
    },
    "moonshot": {
        "label": "Moonshot (kimi)",
        "modalities": {
            "text": [
                {"id": "kimi-k2-0905-preview", "name": "Kimi K2 (0905 Preview)"},
            ],
        },
    },
}


def resolve(provider: str, modality: str, model_id: str):
    """Look up a catalog entry by provider/modality/id.

    Returns (model_name_to_send_upstream, extra_params_dict) or
    raises KeyError if not found.
    """
    if provider not in CATALOG:
        raise KeyError(f"unknown provider '{provider}'")
    modalities = CATALOG[provider]["modalities"]
    if modality not in modalities:
        raise KeyError(f"unknown modality '{modality}' for {provider}")
    for entry in modalities[modality]:
        if entry["id"] == model_id:
            upstream_model = entry.get("model", entry["id"])
            params = dict(entry.get("params") or {})
            return upstream_model, params
    raise KeyError(f"unknown model '{model_id}' for {provider}/{modality}")
