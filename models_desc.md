# Multi-provider AI demo

A small Flask app that exposes a single prompt box and three dropdowns —
**Provider**, **Type** (modality), and **Model** — and routes each request to
the right vendor API. Each provider is hit with its own native SDK / HTTP API
(no aggregators), so this can double as a reference for how to integrate any
one of them on its own.

## Supported providers

### Text + image
| Provider | Text models | Image models |
| --- | --- | --- |
| **OpenAI** | GPT-5 nano · GPT-4.1 nano · GPT-4o mini · GPT-5 mini · GPT-4.1 mini · GPT-4o · GPT-4.1 · GPT-5 (high) · GPT-5.1 · GPT-5.2 / 5.3 Codex · o3 · GPT-5.4 · GPT-5.5 · GPT-5.4 Pro / 5.5 Pro · o1-pro · GPT-3.5 / GPT-4 Turbo | GPT Image 1 Mini (Low) · GPT Image 1 (Low / Med / High) · GPT Image 1.5 (Std) · DALL-E 3 · DALL-E 2 |
| **Google Gemini** | Gemini 3.1 Flash-Lite / 2.5 Flash / 3 Flash · Gemini 2.5 Pro / 3.1 Pro · Gemini 2.0 Flash · Gemini 1.5 Pro / Flash | Imagen 4 Fast / Standard / Ultra · Gemini 3 Pro Image |

### Text only
| Provider | Models |
| --- | --- |
| **Anthropic Claude** | Claude Haiku 4.5 · Claude Sonnet 4.6 · Claude Opus 4.7 · Claude 4.1 Opus · Claude Mythos Preview |
| **xAI (Grok)** | Grok 4.1 Fast |
| **Mistral** | Ministral 3 3B · Mistral Large 3 |
| **DeepSeek** | DeepSeek V3 · DeepSeek V4 Pro |
| **MiniMax** | MiniMax M2.7 |
| **Z.AI (GLM)** | GLM-5 (Reasoning) |

### Image only
| Provider | Models |
| --- | --- |
| **Black Forest Labs** | Flux 2 Schnell · Flux 2 Dev · Flux 2 Pro v1.1 |
| **ByteDance Seedream** | Seedream 4.5 (via Volcano Engine ARK) |
| **Tencent Hunyuan** | Hunyuan Image 3.0 (via Tencent Cloud) |
| **Ideogram** | Ideogram 2.0 |

Video is reserved in the catalog structure but not implemented yet.

> Vendor model IDs change frequently. The IDs in `models_catalog.py` reflect
> each vendor's public docs / naming convention at the time of writing — if a
> call returns "model not found", update the `model` field on that catalog
> entry; no other code change is needed.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
# edit .env and paste keys for the providers you actually want to test

python app.py
```

App runs at <http://127.0.0.1:5000>. Visit
<http://127.0.0.1:5000/api/diagnostic> to confirm which API keys the server
loaded (presence + length only — never values).

You only need keys for the providers you want to call — the others will simply
error with a "not set" message when you select them.

## API keys

| Env var | Where to get it |
| --- | --- |
| `OPENAI_API_KEY` | <https://platform.openai.com/api-keys> |
| `GEMINI_API_KEY` | <https://aistudio.google.com/apikey> |
| `ANTHROPIC_API_KEY` | <https://console.anthropic.com/settings/keys> |
| `XAI_API_KEY` | <https://console.x.ai/> |
| `MISTRAL_API_KEY` | <https://console.mistral.ai/api-keys> |
| `DEEPSEEK_API_KEY` | <https://platform.deepseek.com/api_keys> |
| `MINIMAX_API_KEY` | <https://platform.minimax.io> |
| `ZAI_API_KEY` | <https://docs.z.ai/> |
| `BFL_API_KEY` | <https://dashboard.bfl.ai/> |
| `IDEOGRAM_API_KEY` | <https://ideogram.ai/manage-api> |
| `ARK_API_KEY` | Volcano Engine ARK console (Seedream) |
| `TENCENT_SECRET_ID` + `TENCENT_SECRET_KEY` | <https://console.cloud.tencent.com/cam/capi> (Hunyuan) |
| `TENCENT_REGION` | optional, defaults to `ap-guangzhou` |

After editing `.env`, **restart Flask** — env vars are read at process start.

## Project layout

```
app.py                          # Flask routes + JSON glue
models_catalog.py               # Provider / modality / model registry
providers/
  __init__.py                   # Dispatcher: provider name -> module
  _common.py                    # require_env, base64 helpers, image fetcher
  _openai_compatible.py         # Shared OpenAI-shape chat helper
  openai_provider.py            # openai SDK (chat + images)
  gemini_provider.py            # google-genai SDK (text, Imagen, Gemini image)
  anthropic_provider.py         # anthropic SDK (Messages API)
  mistral_provider.py           # OpenAI-compat @ api.mistral.ai
  deepseek_provider.py          # OpenAI-compat @ api.deepseek.com
  xai_provider.py               # OpenAI-compat @ api.x.ai
  minimax_provider.py           # OpenAI-compat @ api.minimax.io
  zhipu_provider.py             # OpenAI-compat @ api.z.ai
  bfl_provider.py               # api.bfl.ai async polling (Flux)
  ideogram_provider.py          # api.ideogram.ai
  seedream_provider.py          # Volcano Engine ARK (OpenAI-shape)
  hunyuan_provider.py           # Tencent Cloud SDK, async polling
templates/index.html            # UI shell
static/script.js                # Dropdown filtering + fetch
static/style.css                # Styling
requirements.txt
.env.example
```

## How filtering works

`models_catalog.py` is the single source of truth. Each model entry can carry
an `id` (what the UI sends), an optional `model` (the real upstream model ID),
and optional `params` (e.g. `{"quality": "high"}` for OpenAI quality tiers,
or `{"reasoning_effort": "high"}` for GPT-5 reasoning tiers).

The frontend calls `/api/catalog`, populates the provider dropdown, and
refilters the model dropdown whenever provider or modality changes. The
backend resolves the catalog entry, then dispatches to the matching
`providers/*.py` module.

## Adding a new provider

1. Add an entry to `CATALOG` in `models_catalog.py`.
2. Create `providers/<name>_provider.py` exposing
   `generate(modality, model, params, prompt)`. For OpenAI-compatible APIs
   that's ~10 lines — see `mistral_provider.py` for the template.
3. Register it in `providers/__init__.py`.
4. Add any new env vars to `.env.example` and to `ENV_KEYS` in `app.py`.

No frontend changes required.

## Notes

- All keys live server-side; the browser only talks to this Flask app.
- Image responses are returned as base64 data URLs and rendered inline — no files written.
- Upstream errors are surfaced verbatim in the UI, which is handy while wiring new models.
- BFL and Hunyuan use async APIs; the backend polls for up to ~2–3 min before timing out.
- Mistral, DeepSeek, xAI, MiniMax, and Z.AI all expose the OpenAI chat-completions
  shape, so they share one ~12-line helper (`providers/_openai_compatible.py`).
