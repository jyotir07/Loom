"""Key vault: InMemoryVault + AWS/GCP/HCV backends + Loom integration."""

from __future__ import annotations

import json
import time

import pytest

import loom
from loom import (
    AWSSecretsManagerVault,
    GCPSecretManagerVault,
    HashiCorpVaultBackend,
    InMemoryVault,
    Loom,
)
from loom.errors import AuthError
from loom.providers._common import require_env


# ---------- InMemoryVault ----------


def test_in_memory_vault_get_returns_secret():
    v = InMemoryVault({"OPENAI_API_KEY": "sk-test"})
    assert v.get("OPENAI_API_KEY") == "sk-test"


def test_in_memory_vault_get_missing_returns_none():
    v = InMemoryVault()
    assert v.get("MISSING") is None


def test_in_memory_vault_get_blank_returns_none():
    v = InMemoryVault({"X": ""})
    assert v.get("X") is None


def test_in_memory_vault_set():
    v = InMemoryVault()
    v.set("K", "v")
    assert v.get("K") == "v"


# ---------- require_env resolution order ----------


def test_require_env_prefers_api_keys_over_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    client = Loom(api_keys={"OPENAI_API_KEY": "from-api-keys"})
    captured = {}

    def fake_generate(provider, modality, model, params, prompt):
        captured["key"] = require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client.generate(provider="openai", modality="text",
                    model="gpt-4o-mini", prompt="hi")
    assert captured["key"] == "from-api-keys"


def test_require_env_prefers_env_over_vault(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    vault = InMemoryVault({"OPENAI_API_KEY": "from-vault"})
    client = Loom(vault=vault)
    captured = {}

    def fake_generate(provider, modality, model, params, prompt):
        captured["key"] = require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client.generate(provider="openai", modality="text",
                    model="gpt-4o-mini", prompt="hi")
    assert captured["key"] == "from-env"


def test_require_env_falls_back_to_vault(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    vault = InMemoryVault({"OPENAI_API_KEY": "from-vault"})
    client = Loom(vault=vault)
    captured = {}

    def fake_generate(provider, modality, model, params, prompt):
        captured["key"] = require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    client.generate(provider="openai", modality="text",
                    model="gpt-4o-mini", prompt="hi")
    assert captured["key"] == "from-vault"


def test_require_env_raises_when_all_sources_empty(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    vault = InMemoryVault()  # empty
    client = Loom(vault=vault)

    def fake_generate(provider, modality, model, params, prompt):
        require_env("OPENAI_API_KEY")
        return {"kind": "text", "text": "ok"}

    monkeypatch.setattr("loom._loom._providers.generate", fake_generate)
    with pytest.raises(AuthError, match="OPENAI_API_KEY"):
        client.generate(provider="openai", modality="text",
                        model="gpt-4o-mini", prompt="hi")


# ---------- Loom.from_env passthrough ----------


def test_loom_from_env_accepts_vault():
    vault = InMemoryVault()
    client = Loom.from_env(vault=vault)
    assert client.vault is vault


# ---------- AWSSecretsManagerVault (fake boto3 client) ----------


class _FakeAWSClient:
    def __init__(self, secrets):
        self.secrets = secrets
        self.calls = []

    def get_secret_value(self, *, SecretId):
        self.calls.append(SecretId)
        if SecretId not in self.secrets:
            from botocore.exceptions import ClientError  # would be real in prod
            raise KeyError(SecretId)
        return {"SecretString": self.secrets[SecretId]}


def test_aws_vault_plain_secret_string():
    client = _FakeAWSClient({"prod/loom/OPENAI_API_KEY": "sk-from-aws"})
    v = AWSSecretsManagerVault(prefix="prod/loom/", client=client)
    assert v.get("OPENAI_API_KEY") == "sk-from-aws"
    assert client.calls == ["prod/loom/OPENAI_API_KEY"]


def test_aws_vault_uses_cache_within_ttl():
    client = _FakeAWSClient({"OPENAI_API_KEY": "first"})
    v = AWSSecretsManagerVault(client=client, cache_ttl_seconds=300)
    assert v.get("OPENAI_API_KEY") == "first"
    # Change underlying value; cached call shouldn't see it.
    client.secrets["OPENAI_API_KEY"] = "second"
    assert v.get("OPENAI_API_KEY") == "first"
    assert client.calls == ["OPENAI_API_KEY"]


def test_aws_vault_cache_disabled():
    client = _FakeAWSClient({"K": "a"})
    v = AWSSecretsManagerVault(client=client, cache_ttl_seconds=0)
    assert v.get("K") == "a"
    client.secrets["K"] = "b"
    assert v.get("K") == "b"
    assert client.calls == ["K", "K"]


def test_aws_vault_json_keyed_single_secret():
    payload = json.dumps({
        "OPENAI_API_KEY": "sk-openai",
        "ANTHROPIC_API_KEY": "sk-ant",
    })
    client = _FakeAWSClient({"prod/loom/bundle": payload})
    v = AWSSecretsManagerVault(
        client=client,
        json_keyed=True,
        json_secret_name="prod/loom/bundle",
    )
    assert v.get("OPENAI_API_KEY") == "sk-openai"
    assert v.get("ANTHROPIC_API_KEY") == "sk-ant"
    # Only one upstream call thanks to caching (same secret name).
    assert client.calls == ["prod/loom/bundle", "prod/loom/bundle"]


def test_aws_vault_fail_soft_returns_none_on_error():
    class _BrokenClient:
        def get_secret_value(self, **_):
            raise RuntimeError("AWS is down")
    v = AWSSecretsManagerVault(client=_BrokenClient())
    assert v.get("ANY") is None


# ---------- GCPSecretManagerVault (fake client) ----------


class _FakeGCPPayload:
    def __init__(self, data):
        self.data = data.encode("utf-8") if isinstance(data, str) else data


class _FakeGCPResponse:
    def __init__(self, data):
        self.payload = _FakeGCPPayload(data)


class _FakeGCPClient:
    def __init__(self, secrets):
        self.secrets = secrets
        self.calls = []

    def access_secret_version(self, *, request):
        name = request["name"]
        self.calls.append(name)
        # name like projects/p/secrets/<resource>/versions/latest
        bits = name.split("/")
        resource = bits[bits.index("secrets") + 1]
        return _FakeGCPResponse(self.secrets[resource])


def test_gcp_vault_returns_secret_string():
    client = _FakeGCPClient({"OPENAI_API_KEY": "sk-from-gcp"})
    v = GCPSecretManagerVault(project_id="proj-1", client=client)
    assert v.get("OPENAI_API_KEY") == "sk-from-gcp"
    assert client.calls == [
        "projects/proj-1/secrets/OPENAI_API_KEY/versions/latest"
    ]


def test_gcp_vault_applies_prefix():
    client = _FakeGCPClient({"loom-OPENAI_API_KEY": "x"})
    v = GCPSecretManagerVault(project_id="p", prefix="loom-", client=client)
    assert v.get("OPENAI_API_KEY") == "x"


# ---------- HashiCorpVaultBackend (fake client) ----------


class _FakeHCVKvV2:
    def __init__(self, secrets):
        self.secrets = secrets
        self.calls = []

    def read_secret_version(self, *, path, mount_point):
        self.calls.append((mount_point, path))
        return {"data": {"data": self.secrets.get(path, {})}}


class _FakeHCVClient:
    def __init__(self, secrets):
        kv2 = _FakeHCVKvV2(secrets)
        self.secrets = type("S", (), {"kv": type("KV", (), {"v2": kv2})()})()
        self._kv2 = kv2


def test_hcv_backend_reads_value_key():
    client = _FakeHCVClient({"OPENAI_API_KEY": {"value": "sk-hcv"}})
    v = HashiCorpVaultBackend(client=client)
    assert v.get("OPENAI_API_KEY") == "sk-hcv"
    assert client._kv2.calls == [("secret", "OPENAI_API_KEY")]


def test_hcv_backend_custom_secret_key():
    client = _FakeHCVClient({"K": {"api_key": "xyz"}})
    v = HashiCorpVaultBackend(client=client, secret_key="api_key")
    assert v.get("K") == "xyz"


def test_hcv_backend_missing_value_returns_none():
    client = _FakeHCVClient({"K": {"value": ""}})
    v = HashiCorpVaultBackend(client=client)
    assert v.get("K") is None


# ---------- exports ----------


def test_vault_classes_exported_from_loom():
    assert loom.KeyVault is not None
    assert loom.InMemoryVault is not None
    assert loom.AWSSecretsManagerVault is not None
    assert loom.GCPSecretManagerVault is not None
    assert loom.HashiCorpVaultBackend is not None
