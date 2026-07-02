"""Provider-agnostic structured outputs — the shared interface (issue #59).

Every vendor spells structured output differently (OpenAI `response_format`,
Anthropic tool schemas, Gemini `response_schema`). This module is the
vendor-neutral layer above them: it turns a caller's schema into a JSON
instruction and parses + validates the model's reply back into a typed
object, so applications rely on one mechanism regardless of provider.

Today the strategy is provider-agnostic JSON: the schema is described to the
model in the prompt and the reply is parsed against it — which works on
*every* provider. Native structured-output modes (which guarantee
well-formed JSON) get wired per provider in later work, gated on each
provider's ``supports_structured_output`` capability; the parse/validate
contract here does not change when they land.

Pydantic is an **optional** dependency. Importing Loom never requires it;
only passing ``schema=`` does. When it's absent, a clear
:class:`StructuredOutputError` is raised instead of an ``ImportError`` at
import time.
"""

from __future__ import annotations

import json
from typing import Any

from loom.errors import StructuredOutputError

try:  # optional dependency — only needed when schema= is used
    from pydantic import BaseModel, ValidationError

    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover - covered via monkeypatch in tests
    BaseModel = None  # type: ignore[assignment,misc]
    ValidationError = None  # type: ignore[assignment,misc]
    _HAS_PYDANTIC = False


# Reserved params key carrying the JSON schema down to native-capable
# provider adapters. It never reaches a vendor SDK: native adapters pop it
# (see take_response_schema) and translate it into their own structured-
# output shape, while the dispatch layer strips it for providers without
# native support (they rely on the augmented-prompt JSON fallback instead).
RESPONSE_SCHEMA_KEY = "_loom_response_schema"


def is_schema(schema: Any) -> bool:
    """Whether `schema` is a schema type Loom understands (Pydantic today)."""
    return (
        _HAS_PYDANTIC
        and isinstance(schema, type)
        and issubclass(schema, BaseModel)
    )


def ensure_available(schema: Any) -> None:
    """Validate that `schema=` can be honoured, else raise a clear error."""
    if not _HAS_PYDANTIC:
        raise StructuredOutputError(
            "structured outputs require the optional 'pydantic' dependency — "
            "install it with `pip install pydantic` (or `pip install loom[structured]`)"
        )
    if not is_schema(schema):
        raise StructuredOutputError(
            "schema= must be a pydantic BaseModel subclass, got "
            f"{schema!r}"
        )


def _json_schema(schema: Any) -> dict[str, Any]:
    # pydantic v2 -> model_json_schema; v1 -> schema()
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    return schema.schema()


def _validate(schema: Any, data: Any) -> Any:
    # pydantic v2 -> model_validate; v1 -> parse_obj
    if hasattr(schema, "model_validate"):
        return schema.model_validate(data)
    return schema.parse_obj(data)


def augment_prompt(prompt: str, schema: Any) -> str:
    """Append a JSON-Schema instruction so any provider emits parseable JSON.

    This is the provider-agnostic path used until native structured-output
    modes are wired per provider.
    """
    rendered = json.dumps(_json_schema(schema), indent=2)
    return (
        f"{prompt}\n\n"
        "Respond with a single JSON object that conforms to the JSON Schema "
        "below. Output only the JSON — no markdown code fences, no "
        "commentary.\n\n"
        f"JSON Schema:\n{rendered}"
    )


def response_schema_spec(schema: Any) -> dict[str, Any]:
    """The provider-neutral schema descriptor carried to native adapters.

    ``{"name": <schema name>, "schema": <JSON Schema dict>}`` — each native
    adapter maps this onto its own SDK shape (OpenAI ``response_format``,
    Anthropic tool ``input_schema``, Gemini ``response_schema``).
    """
    return {
        "name": getattr(schema, "__name__", "Response"),
        "schema": _json_schema(schema),
    }


def take_response_schema(
    params: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Split the reserved schema spec out of `params`.

    Returns ``(params_without_key, spec_or_None)``. Native adapters call
    this first so the reserved key is never forwarded to the vendor SDK.
    """
    rest = dict(params or {})
    spec = rest.pop(RESPONSE_SCHEMA_KEY, None)
    return rest, spec


def strip_response_schema(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop the reserved schema key — used for providers without a native
    structured-output path (the augmented prompt already carries the schema)."""
    if not params or RESPONSE_SCHEMA_KEY not in params:
        return params or {}
    return {k: v for k, v in params.items() if k != RESPONSE_SCHEMA_KEY}


def _strip_fences(text: str) -> str:
    """Drop a leading ```/```json fence and its closing ``` if present."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json(text: Any) -> Any:
    """Best-effort parse of a JSON object out of model text."""
    if not isinstance(text, str) or not text.strip():
        raise StructuredOutputError("model returned no text to parse as JSON")
    candidate = _strip_fences(text.strip())
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Fallback: slice the outermost { ... } in case the model added prose.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise StructuredOutputError(
        "could not parse a JSON object from the model output"
    )


def parse(schema: Any, text: Any) -> Any:
    """Parse `text` into JSON and validate it against `schema`.

    Returns a validated schema instance. Raises
    :class:`StructuredOutputError` if the text can't be parsed as JSON or
    fails schema validation.
    """
    data = _extract_json(text)
    try:
        return _validate(schema, data)
    except ValidationError as exc:  # type: ignore[misc]
        name = getattr(schema, "__name__", str(schema))
        raise StructuredOutputError(
            f"model output failed {name} validation: {exc}"
        ) from exc


__all__ = [
    "is_schema",
    "ensure_available",
    "augment_prompt",
    "parse",
    "RESPONSE_SCHEMA_KEY",
    "response_schema_spec",
    "take_response_schema",
    "strip_response_schema",
]
