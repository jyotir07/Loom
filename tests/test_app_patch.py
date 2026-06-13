"""Tests for the app_patch helpers — catalog writer, registry writer, codegen."""

from __future__ import annotations

import pytest

from app_patch import (
    add_catalog_entry,
    add_provider_to_registry,
    generate_provider_source,
    rollback_catalog_entry,
)


SAMPLE_DATA = '''"""docstring"""

CATALOG = {
    "openai": {
        "label": "OpenAI",
        "modalities": {
            "text": [
                {"id": "gpt-4o-mini", "name": "GPT-4o mini", "input_inr_per_1m": 14.4578, "output_inr_per_1m": 57.8312},
            ],
            "image": [],
        },
    },
}
'''


SAMPLE_INIT = '''"""providers init"""

_LAZY: dict[str, str] = {
    "openai": "loom.providers.openai_provider",
}
'''


def test_add_entry_to_existing_provider_existing_modality(tmp_path):
    data = tmp_path / "_data.py"
    data.write_text(SAMPLE_DATA, encoding="utf-8")
    status = add_catalog_entry(
        data,
        provider_key="openai",
        provider_label="OpenAI",
        modality="text",
        model_id="gpt-5-mini",
        model_name="GPT-5 mini",
        input_inr_per_1m=24.0,
        output_inr_per_1m=192.0,
    )
    assert status["provider"] == "exists"
    assert status["entry"] == "created"
    text = data.read_text(encoding="utf-8")
    assert '"id": "gpt-5-mini"' in text
    # The existing entry must still be present.
    assert '"id": "gpt-4o-mini"' in text


def test_add_entry_to_existing_provider_empty_modality(tmp_path):
    data = tmp_path / "_data.py"
    data.write_text(SAMPLE_DATA, encoding="utf-8")
    status = add_catalog_entry(
        data,
        provider_key="openai",
        provider_label="OpenAI",
        modality="image",
        model_id="dall-e-3",
        model_name="DALL-E 3",
        cost_inr=3.86,
    )
    assert status["entry"] == "created"
    text = data.read_text(encoding="utf-8")
    assert '"id": "dall-e-3"' in text
    assert '"cost_inr": 3.86' in text


def test_add_entry_replaces_existing_same_id(tmp_path):
    data = tmp_path / "_data.py"
    data.write_text(SAMPLE_DATA, encoding="utf-8")
    # Same id, different output rate — should update.
    status = add_catalog_entry(
        data,
        provider_key="openai",
        provider_label="OpenAI",
        modality="text",
        model_id="gpt-4o-mini",
        model_name="GPT-4o mini",
        input_inr_per_1m=14.4578,
        output_inr_per_1m=99.0,
    )
    assert status["entry"] == "updated"
    text = data.read_text(encoding="utf-8")
    # Only one occurrence of gpt-4o-mini left.
    assert text.count('"id": "gpt-4o-mini"') == 1
    assert '"output_inr_per_1m": 99.0' in text


def test_add_entry_creates_new_provider_block(tmp_path):
    data = tmp_path / "_data.py"
    data.write_text(SAMPLE_DATA, encoding="utf-8")
    status = add_catalog_entry(
        data,
        provider_key="newco",
        provider_label="NewCo AI",
        modality="text",
        model_id="newco-fast",
        model_name="NewCo Fast",
        input_inr_per_1m=10.0,
        output_inr_per_1m=20.0,
    )
    assert status["provider"] == "created"
    text = data.read_text(encoding="utf-8")
    assert '"newco": {' in text
    assert '"label": "NewCo AI"' in text
    assert '"id": "newco-fast"' in text
    # Catalog dict still parses as Python.
    ns: dict = {}
    exec(text, ns)
    assert "newco" in ns["CATALOG"]
    assert ns["CATALOG"]["newco"]["modalities"]["text"][0]["id"] == "newco-fast"


def test_rollback_removes_entry(tmp_path):
    data = tmp_path / "_data.py"
    data.write_text(SAMPLE_DATA, encoding="utf-8")
    add_catalog_entry(
        data,
        provider_key="openai",
        provider_label="OpenAI",
        modality="text",
        model_id="temp-model",
        model_name="Temp",
        input_inr_per_1m=1.0,
        output_inr_per_1m=2.0,
    )
    assert '"id": "temp-model"' in data.read_text(encoding="utf-8")
    removed = rollback_catalog_entry(
        data, provider_key="openai", modality="text", model_id="temp-model"
    )
    assert removed is True
    assert '"id": "temp-model"' not in data.read_text(encoding="utf-8")


def test_rollback_missing_entry_returns_false(tmp_path):
    data = tmp_path / "_data.py"
    data.write_text(SAMPLE_DATA, encoding="utf-8")
    removed = rollback_catalog_entry(
        data, provider_key="openai", modality="text", model_id="never-existed"
    )
    assert removed is False


def test_add_to_registry_new_provider(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text(SAMPLE_INIT, encoding="utf-8")
    status = add_provider_to_registry(
        init,
        provider_key="newco",
        module_path="loom.providers.newco_provider",
    )
    assert status == "added"
    text = init.read_text(encoding="utf-8")
    assert '"newco": "loom.providers.newco_provider"' in text
    # Still valid Python.
    ns: dict = {}
    exec(text, ns)
    assert ns["_LAZY"]["newco"] == "loom.providers.newco_provider"


def test_add_to_registry_existing_provider_same_module(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text(SAMPLE_INIT, encoding="utf-8")
    status = add_provider_to_registry(
        init,
        provider_key="openai",
        module_path="loom.providers.openai_provider",
    )
    assert status == "exists"


def test_add_to_registry_existing_provider_different_module(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text(SAMPLE_INIT, encoding="utf-8")
    status = add_provider_to_registry(
        init,
        provider_key="openai",
        module_path="loom.providers.openai_v2_provider",
    )
    assert status == "updated"
    text = init.read_text(encoding="utf-8")
    assert "openai_v2_provider" in text


def test_generate_provider_source_renders_template():
    source = generate_provider_source(
        provider_key="newco",
        provider_label="NewCo AI",
        base_url="https://api.newco.ai/v1",
    )
    assert "NewCo AI" in source
    assert "NEWCO_API_KEY" in source
    assert "https://api.newco.ai/v1" in source
    # Code compiles.
    compile(source, "<generated>", "exec")
