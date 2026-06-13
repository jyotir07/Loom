"""Patch loom/providers/__init__.py to register a new provider.

The registry is a single dict literal `_LAZY: dict[str, str] = { ... }`.
We insert a new key->module-path mapping at the end of that dict.
"""

from __future__ import annotations

import re
from pathlib import Path

_LAZY_BLOCK_RE = re.compile(
    r"_LAZY: dict\[str, str\] = \{(?P<body>.*?)\n\}",
    re.DOTALL,
)


def add_provider_to_registry(
    init_path: str | Path,
    *,
    provider_key: str,
    module_path: str,
) -> str:
    """Add `provider_key -> module_path` to the _LAZY dict.

    Returns "added", "updated", or "exists".
    """
    path = Path(init_path)
    source = path.read_text(encoding="utf-8")
    match = _LAZY_BLOCK_RE.search(source)
    if match is None:
        raise RuntimeError("could not find _LAZY dict in providers/__init__.py")

    body = match.group("body")
    key_token = f'"{provider_key}":'

    new_line = f'    "{provider_key}": "{module_path}",'

    if key_token in body:
        # Same module path? -> exists. Different? -> update.
        existing = re.search(
            r'\n    "' + re.escape(provider_key) + r'":\s*"([^"]+)",',
            body,
        )
        if existing and existing.group(1) == module_path:
            return "exists"
        new_body = re.sub(
            r'\n    "' + re.escape(provider_key) + r'":[^\n]*,',
            "\n" + new_line,
            body,
            count=1,
        )
        status = "updated"
    else:
        # Append before the closing `}`.
        new_body = body.rstrip("\n") + "\n" + new_line + "\n"
        status = "added"

    new_source = (
        source[: match.start("body")] + new_body + source[match.end("body") :]
    )
    path.write_text(new_source, encoding="utf-8")
    return status
