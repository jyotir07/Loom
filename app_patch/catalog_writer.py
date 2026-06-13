"""Patch loom/catalog/_data.py to add or remove a model entry.

The file contains a single top-level dict literal `CATALOG = {...}`.
Each provider is a key into that dict; each modality is a list under
`"modalities"`. We insert before the closing bracket of the target
list, or create a brand-new provider block before the dict's closing
`}` when the provider doesn't exist yet.

Text-based edits, not AST — `_data.py` has hand-tuned formatting,
inline comments, and tight one-line entries we don't want to lose to
`ast.unparse`. The trade-off is that the writer is strict about the
file's overall shape; the tests cover the cases that matter.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PROVIDER_BLOCK_RE = re.compile(
    r'(?P<header>    "(?P<key>[a-z][a-z0-9_]*)": \{\n'
    r'        "label": "[^"]*",\n'
    r'        "modalities": \{)'
    r'(?P<body>.*?)'
    r'(?P<footer>\n        \},\n    \},\n)',
    re.DOTALL,
)

_MODALITY_LIST_RE_TMPL = (
    r'("{modality}": \[)'                # opening
    r'(?P<entries>.*?)'                  # entries
    r'(\n            \],)'              # closing
)


def _format_entry(
    *,
    model_id: str,
    model_name: str,
    upstream_model: str | None,
    params: dict[str, Any] | None,
    input_inr_per_1m: float | None,
    output_inr_per_1m: float | None,
    cost_inr: float | None,
    is_free: bool,
) -> str:
    """Format a single model entry as a Python dict literal."""
    parts: list[str] = [
        f'"id": "{model_id}"',
        f'"name": "{model_name}"',
    ]
    if upstream_model and upstream_model != model_id:
        parts.append(f'"model": "{upstream_model}"')
    if params:
        parts.append(f'"params": {params!r}')
    if input_inr_per_1m is not None:
        parts.append(f'"input_inr_per_1m": {input_inr_per_1m}')
    if output_inr_per_1m is not None:
        parts.append(f'"output_inr_per_1m": {output_inr_per_1m}')
    if cost_inr is not None:
        parts.append(f'"cost_inr": {cost_inr}')
    if is_free:
        parts.append('"free": True')
    return "                {" + ", ".join(parts) + "},"


def _new_provider_block(
    provider_key: str,
    provider_label: str,
    modality: str,
    entry: str,
) -> str:
    modalities = ["text", "image"]
    if modality not in modalities:
        modalities.append(modality)
    lines = [
        f'    "{provider_key}": {{',
        f'        "label": "{provider_label}",',
        f'        "modalities": {{',
    ]
    for m in modalities:
        if m == modality:
            lines.append(f'            "{m}": [')
            lines.append(entry)
            lines.append("            ],")
        else:
            lines.append(f'            "{m}": [],')
    lines.append("        },")
    lines.append("    },")
    return "\n".join(lines) + "\n"


def add_catalog_entry(
    data_path: str | Path,
    *,
    provider_key: str,
    provider_label: str,
    modality: str,
    model_id: str,
    model_name: str,
    upstream_model: str | None = None,
    params: dict[str, Any] | None = None,
    input_inr_per_1m: float | None = None,
    output_inr_per_1m: float | None = None,
    cost_inr: float | None = None,
    is_free: bool = False,
) -> dict[str, str]:
    """Insert (or update) a model entry in loom/catalog/_data.py.

    Returns a status dict describing whether the provider/modality
    block already existed.
    """
    path = Path(data_path)
    source = path.read_text(encoding="utf-8")

    entry = _format_entry(
        model_id=model_id,
        model_name=model_name,
        upstream_model=upstream_model,
        params=params,
        input_inr_per_1m=input_inr_per_1m,
        output_inr_per_1m=output_inr_per_1m,
        cost_inr=cost_inr,
        is_free=is_free,
    )

    provider_match = _PROVIDER_BLOCK_RE.search(
        source,
    )
    # Iterate matches to find this specific provider
    target = None
    for m in _PROVIDER_BLOCK_RE.finditer(source):
        if m.group("key") == provider_key:
            target = m
            break

    if target is None:
        # New provider — insert a fresh block before the closing `}` of CATALOG.
        block = _new_provider_block(provider_key, provider_label, modality, entry)
        closing_idx = source.rfind("\n}")
        if closing_idx < 0:
            raise RuntimeError(
                "could not find closing `}` of CATALOG in _data.py"
            )
        new_source = source[:closing_idx] + "\n" + block + source[closing_idx:]
        path.write_text(new_source, encoding="utf-8")
        return {"provider": "created", "modality": "created", "entry": "created"}

    # Provider exists. Try the multi-line modality list first.
    block_text = source[target.start() : target.end()]
    modality_re = re.compile(
        _MODALITY_LIST_RE_TMPL.format(modality=re.escape(modality)),
        re.DOTALL,
    )
    mod_match = modality_re.search(block_text)

    if mod_match is not None:
        entries_text = mod_match.group("entries")
        id_token = f'"id": "{model_id}"'
        if id_token in entries_text:
            existing_line_re = re.compile(
                r"\n                \{[^\n]*" + re.escape(id_token) + r"[^\n]*\},",
            )
            new_entries = existing_line_re.sub("\n" + entry, entries_text)
            status = "updated"
        elif entries_text.strip() == "":
            new_entries = "\n" + entry
            status = "created"
        else:
            new_entries = entries_text.rstrip("\n") + "\n" + entry
            status = "created"
        new_block = (
            block_text[: mod_match.start("entries")]
            + new_entries
            + block_text[mod_match.end("entries") :]
        )
        new_source = source[: target.start()] + new_block + source[target.end() :]
        path.write_text(new_source, encoding="utf-8")
        return {"provider": "exists", "modality": "exists", "entry": status}

    # Modality list might be in single-line empty form, e.g. `"image": [],`.
    empty_re = re.compile(
        r'            "' + re.escape(modality) + r'": \[\],'
    )
    if empty_re.search(block_text):
        expanded = (
            f'            "{modality}": [\n'
            f"{entry}\n"
            f"            ],"
        )
        new_block = empty_re.sub(expanded, block_text, count=1)
        new_source = source[: target.start()] + new_block + source[target.end() :]
        path.write_text(new_source, encoding="utf-8")
        return {"provider": "exists", "modality": "expanded", "entry": "created"}

    raise RuntimeError(
        f"provider '{provider_key}' exists but has no '{modality}' modality list "
        "in _data.py — add it manually before using this endpoint"
    )


def rollback_catalog_entry(
    data_path: str | Path,
    *,
    provider_key: str,
    modality: str,
    model_id: str,
) -> bool:
    """Remove a previously added entry. Returns True if anything was removed."""
    path = Path(data_path)
    source = path.read_text(encoding="utf-8")
    id_token = f'"id": "{model_id}"'
    if id_token not in source:
        return False
    # Find the matching entry line and strip it (plus the trailing newline).
    line_re = re.compile(
        r"\n                \{[^\n]*" + re.escape(id_token) + r"[^\n]*\},",
    )
    new_source, n = line_re.subn("", source)
    if n == 0:
        return False
    path.write_text(new_source, encoding="utf-8")
    return True
