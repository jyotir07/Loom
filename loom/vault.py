"""Key vault integration.

Sometimes API keys can't live in `.env` or process environment —
compliance teams want them in AWS Secrets Manager, GCP Secret Manager,
or HashiCorp Vault. Loom treats a key vault as a third resolution
source for `require_env`:

    1. programmatic `api_keys` passed into Loom(api_keys={...})
    2. process environment variable of the same name
    3. the configured `KeyVault` (if any)

That order is deliberate: local overrides (api_keys, env) still win,
so a dev can shadow a vault value without touching infra. The vault
is the *fallback*, consulted only when the first two miss.

Wiring:

    from loom import Loom, AWSSecretsManagerVault

    vault = AWSSecretsManagerVault(
        region_name="us-east-1",
        prefix="prod/loom/",
    )
    client = Loom.from_env(vault=vault)

    # In env or api_keys: nothing. require_env("OPENAI_API_KEY") will
    # resolve to AWS Secrets Manager's "prod/loom/OPENAI_API_KEY".

Backends here have lazy imports — none of them are hard dependencies.
You only pay the SDK cost if you actually use the backend.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Protocol


class KeyVault(Protocol):
    """Minimal vault interface — return a secret by env-var name, or None."""

    def get(self, name: str) -> str | None: ...


class InMemoryVault:
    """Trivial backend for tests and programmatic use.

    Useful when you've already pulled secrets from some other source
    (a bootstrap script, a config service) and just want a vault-shaped
    object to hand to Loom.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets: dict[str, str] = dict(secrets or {})

    def set(self, name: str, value: str) -> None:
        self._secrets[name] = value

    def get(self, name: str) -> str | None:
        v = self._secrets.get(name)
        return v if v else None


class _CachingVault:
    """Shared cache + prefix logic for the external backends.

    Subclasses implement `_fetch(resource_name) -> str | None`. The base
    class handles prefix-mangling, an in-process TTL cache, and thread
    safety.

    `cache_ttl_seconds` defaults to 5 minutes. Pass 0 to disable caching
    entirely (useful when you want every `require_env` to round-trip
    to the vendor — e.g. for key rotation tests).
    """

    def __init__(
        self,
        *,
        prefix: str = "",
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self.prefix = prefix
        self.cache_ttl_seconds = float(cache_ttl_seconds)
        self._cache: dict[str, tuple[float, str | None]] = {}
        self._lock = threading.Lock()

    def _resource_name(self, name: str) -> str:
        return f"{self.prefix}{name}"

    def _fetch(self, resource_name: str) -> str | None:
        raise NotImplementedError

    def get(self, name: str) -> str | None:
        if self.cache_ttl_seconds > 0:
            now = time.time()
            with self._lock:
                cached = self._cache.get(name)
                if cached is not None and (now - cached[0]) < self.cache_ttl_seconds:
                    return cached[1]
        try:
            value = self._fetch(self._resource_name(name))
        except Exception:
            # Fail soft — if the vault is down we want the env-var fallback
            # to still surface a useful AuthError, not a vendor SDK trace.
            return None
        if self.cache_ttl_seconds > 0:
            with self._lock:
                self._cache[name] = (time.time(), value)
        return value


# ---------------- AWS Secrets Manager ----------------


class AWSSecretsManagerVault(_CachingVault):
    """Fetches secrets from AWS Secrets Manager.

    Resource name = `prefix + env_var_name`. So `prefix="prod/loom/"`
    plus a require_env("OPENAI_API_KEY") looks up the secret
    `prod/loom/OPENAI_API_KEY`.

    `client` lets you inject a pre-built boto3 client (useful for tests
    or when you need session-specific config). Otherwise we lazily
    construct `boto3.client("secretsmanager", region_name=...)`.

    Secret values can be plain strings (preferred) or JSON objects
    with a single key. JSON keyed by env-var name lets one secret hold
    many keys: `{"OPENAI_API_KEY": "sk-...", "ANTHROPIC_API_KEY": "..."}`.
    """

    def __init__(
        self,
        *,
        region_name: str | None = None,
        prefix: str = "",
        cache_ttl_seconds: float = 300.0,
        client: Any | None = None,
        json_keyed: bool = False,
        json_secret_name: str | None = None,
    ) -> None:
        super().__init__(prefix=prefix, cache_ttl_seconds=cache_ttl_seconds)
        self.region_name = region_name
        self._client = client
        self.json_keyed = json_keyed
        # When `json_keyed=True` and `json_secret_name` is set, the entire
        # vault reads from one JSON secret and uses env-var names as JSON
        # keys. Otherwise each env-var gets its own secret.
        self.json_secret_name = json_secret_name

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "AWSSecretsManagerVault requires boto3 — install with "
                "`pip install boto3`"
            ) from e
        self._client = boto3.client(
            "secretsmanager", region_name=self.region_name
        )
        return self._client

    def _fetch(self, resource_name: str) -> str | None:
        client = self._ensure_client()
        if self.json_keyed and self.json_secret_name:
            resp = client.get_secret_value(SecretId=self.json_secret_name)
            payload = resp.get("SecretString") or ""
            if not payload:
                return None
            import json

            data = json.loads(payload)
            # resource_name still has prefix applied; strip it back to env-var.
            key = resource_name[len(self.prefix):] if self.prefix else resource_name
            value = data.get(key)
            return str(value) if value else None

        resp = client.get_secret_value(SecretId=resource_name)
        payload = resp.get("SecretString")
        if payload is None:
            return None
        if self.json_keyed:
            import json

            data = json.loads(payload)
            # Single-secret-per-key but JSON-wrapped — assume one entry.
            if isinstance(data, dict) and len(data) == 1:
                return str(next(iter(data.values())))
            return None
        return str(payload)


# ---------------- GCP Secret Manager ----------------


class GCPSecretManagerVault(_CachingVault):
    """Fetches secrets from GCP Secret Manager.

    Resource path = `projects/{project_id}/secrets/{prefix+env_var_name}/versions/{version}`.
    `version` defaults to `"latest"`.

    Application Default Credentials are picked up automatically by the
    underlying client. Pass `client` to inject your own.
    """

    def __init__(
        self,
        *,
        project_id: str,
        prefix: str = "",
        version: str = "latest",
        cache_ttl_seconds: float = 300.0,
        client: Any | None = None,
    ) -> None:
        super().__init__(prefix=prefix, cache_ttl_seconds=cache_ttl_seconds)
        self.project_id = project_id
        self.version = version
        self._client = client

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from google.cloud import secretmanager  # type: ignore
        except ImportError as e:
            raise ImportError(
                "GCPSecretManagerVault requires google-cloud-secret-manager — "
                "install with `pip install google-cloud-secret-manager`"
            ) from e
        self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def _fetch(self, resource_name: str) -> str | None:
        client = self._ensure_client()
        path = (
            f"projects/{self.project_id}/secrets/{resource_name}/"
            f"versions/{self.version}"
        )
        resp = client.access_secret_version(request={"name": path})
        payload = getattr(getattr(resp, "payload", None), "data", None)
        if payload is None:
            return None
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return str(payload)


# ---------------- HashiCorp Vault ----------------


class HashiCorpVaultBackend(_CachingVault):
    """Fetches secrets from HashiCorp Vault (KV v2 engine).

    Each env-var name is treated as a key inside one Vault secret path
    (`mount_path/data/{prefix}{env_var_name}` for KV v2).

    Authentication: pass `token` directly, or a pre-built `hvac.Client`
    via `client`. We don't try to be smart about auth methods (k8s,
    AppRole, etc.) — wire them up in your boot script and hand the
    authenticated client in.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        mount_path: str = "secret",
        prefix: str = "",
        cache_ttl_seconds: float = 300.0,
        client: Any | None = None,
        secret_key: str = "value",
    ) -> None:
        super().__init__(prefix=prefix, cache_ttl_seconds=cache_ttl_seconds)
        self.url = url
        self.token = token
        self.mount_path = mount_path
        self.secret_key = secret_key
        self._client = client

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import hvac  # type: ignore
        except ImportError as e:
            raise ImportError(
                "HashiCorpVaultBackend requires hvac — install with "
                "`pip install hvac`"
            ) from e
        self._client = hvac.Client(url=self.url, token=self.token)
        return self._client

    def _fetch(self, resource_name: str) -> str | None:
        client = self._ensure_client()
        resp = client.secrets.kv.v2.read_secret_version(
            path=resource_name,
            mount_point=self.mount_path,
        )
        data = (((resp or {}).get("data") or {}).get("data") or {})
        value = data.get(self.secret_key)
        return str(value) if value else None


__all__ = [
    "KeyVault",
    "InMemoryVault",
    "AWSSecretsManagerVault",
    "GCPSecretManagerVault",
    "HashiCorpVaultBackend",
]
