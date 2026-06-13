"""Generate a starter provider module for a brand-new vendor.

The default template assumes an OpenAI-shape chat completions API
(by far the most common case). For native-SDK vendors, the generated
file is a starting point — a human still has to wire up the SDK.
"""

from __future__ import annotations

_TEXT_TEMPLATE = '''"""{label} — OpenAI-compatible chat completions at {base_url}.

Auto-generated starter. If the vendor has a non-OpenAI shape, swap
the body for a native-SDK implementation following the contract:

    def generate(modality, model, params, prompt) -> dict
    async def agenerate(modality, model, params, prompt) -> dict
"""

from __future__ import annotations

from typing import Any

from loom.providers._openai_compatible import atext_only, text_only

_API_KEY_ENV = "{api_key_env}"
_BASE_URL = "{base_url}"


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return text_only(
        api_key_env=_API_KEY_ENV,
        base_url=_BASE_URL,
        modality=modality,
        model=model,
        params=params,
        prompt=prompt,
        provider_label="{key}",
    )


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return await atext_only(
        api_key_env=_API_KEY_ENV,
        base_url=_BASE_URL,
        modality=modality,
        model=model,
        params=params,
        prompt=prompt,
        provider_label="{key}",
    )
'''


def generate_provider_source(
    *,
    provider_key: str,
    provider_label: str,
    base_url: str = "https://api.example.com/v1",
    api_key_env: str | None = None,
) -> str:
    """Render the source for a new loom/providers/<key>_provider.py."""
    env = api_key_env or f"{provider_key.upper()}_API_KEY"
    return _TEXT_TEMPLATE.format(
        label=provider_label,
        key=provider_key,
        base_url=base_url,
        api_key_env=env,
    )
