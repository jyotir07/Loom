"""Version sync — pyproject.toml and loom.__version__ must agree."""

from __future__ import annotations

import re
from pathlib import Path

import loom


def _pyproject_version() -> str:
    text = Path(__file__).parent.parent.joinpath("pyproject.toml").read_text(
        encoding="utf-8"
    )
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m is not None, "pyproject.toml has no version field"
    return m.group(1)


def test_pyproject_and_module_version_agree():
    assert loom.__version__ == _pyproject_version()


def test_version_is_semver():
    # Loose semver: MAJOR.MINOR.PATCH (no prerelease handling required yet).
    assert re.match(r"^\d+\.\d+\.\d+", loom.__version__) is not None


def test_version_is_at_least_one():
    major = int(loom.__version__.split(".")[0])
    assert major >= 1, "v1.0+ stability commitment is in force"
