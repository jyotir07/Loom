"""Catalog backends — memory + YAML."""

import pytest

from loom.catalog import Catalog, MemoryBackend, YamlBackend


SAMPLE_CATALOG = {
    "fake": {
        "label": "Fake",
        "modalities": {
            "text": [
                {"id": "fast", "name": "Fast"},
                {"id": "smart", "name": "Smart", "model": "real-smart-v2"},
            ]
        },
    }
}


def test_memory_backend():
    c = Catalog(backend=MemoryBackend(SAMPLE_CATALOG))
    assert c.providers() == ["fake"]
    assert c.resolve("fake", "text", "smart") == ("real-smart-v2", {})


def test_from_mapping():
    c = Catalog.from_mapping(SAMPLE_CATALOG)
    assert c.providers() == ["fake"]


def test_yaml_backend_roundtrip(tmp_path):
    pytest.importorskip("yaml")
    import yaml

    path = tmp_path / "catalog.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(SAMPLE_CATALOG, f)

    c = Catalog.from_yaml(path)
    assert c.providers() == ["fake"]
    upstream, params = c.resolve("fake", "text", "smart")
    assert upstream == "real-smart-v2"
    assert params == {}


def test_yaml_backend_missing_file(tmp_path):
    pytest.importorskip("yaml")
    with pytest.raises(FileNotFoundError):
        Catalog.from_yaml(tmp_path / "nope.yaml")


def test_yaml_backend_rejects_non_mapping(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Catalog.from_yaml(path)


def test_data_argument_still_works():
    """Backwards compatibility: Catalog(data=...) still constructs in-memory."""
    c = Catalog(data=SAMPLE_CATALOG)
    assert c.providers() == ["fake"]
