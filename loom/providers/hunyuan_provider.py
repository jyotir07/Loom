"""Tencent Hunyuan — Tencent Cloud SDK with async polling.

The hunyuan image API is a "submit -> poll -> fetch" pattern. We
submit, then call QueryHunyuanImageJob until JobStatusCode reports
finished, then read the result URLs and download them.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from loom.errors import AuthError, ProviderError
from loom.providers._common import fetch_image_b64, image_response, require_env

_REGION = "ap-guangzhou"
_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 300.0


def _client():
    try:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.hunyuan.v20230901 import hunyuan_client
    except ImportError as exc:
        raise ImportError(
            "loom hunyuan provider requires tencentcloud-sdk-python. "
            "Install with `pip install loom-router[tencent]`."
        ) from exc

    secret_id = require_env("TENCENT_SECRET_ID")
    secret_key = require_env("TENCENT_SECRET_KEY")
    cred = credential.Credential(secret_id, secret_key)
    http_profile = HttpProfile()
    http_profile.endpoint = "hunyuan.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return hunyuan_client.HunyuanClient(cred, _REGION, client_profile)


def _submit(client: Any, model: str, prompt: str, params: dict[str, Any]) -> str:
    from tencentcloud.hunyuan.v20230901 import models as hy_models

    req = hy_models.SubmitHunyuanImageJobRequest()
    body: dict[str, Any] = {"Prompt": prompt}
    if model:
        body["Model"] = model
    body.update(params or {})
    req.from_json_string(json.dumps(body))
    resp = client.SubmitHunyuanImageJob(req)
    job_id = getattr(resp, "JobId", None)
    if not job_id:
        raise ProviderError(f"hunyuan submit returned no JobId: {resp.to_json_string()}")
    return job_id


def _await_job(client: Any, job_id: str) -> Any:
    from tencentcloud.hunyuan.v20230901 import models as hy_models

    deadline = time.time() + _POLL_TIMEOUT
    while True:
        if time.time() > deadline:
            raise ProviderError(f"hunyuan polling timed out after {_POLL_TIMEOUT}s")
        q = hy_models.QueryHunyuanImageJobRequest()
        q.from_json_string(json.dumps({"JobId": job_id}))
        result = client.QueryHunyuanImageJob(q)
        status = int(getattr(result, "JobStatusCode", 0) or 0)
        # Tencent: 1/3 in progress, 4 success, 5 failed (codes vary slightly by API).
        if status in {4}:
            return result
        if status in {5}:
            raise ProviderError(
                f"hunyuan job failed: {result.to_json_string()}"
            )
        time.sleep(_POLL_INTERVAL)


def generate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    if modality != "image":
        raise ProviderError(
            f"hunyuan provider only supports image — got modality '{modality}'"
        )
    client = _client()
    job_id = _submit(client, model, prompt, params)
    result = _await_job(client, job_id)
    urls: list[str] = list(getattr(result, "ResultImage", None) or [])
    images = [fetch_image_b64(u) for u in urls if u]
    return image_response(images)


async def agenerate(
    modality: str, model: str, params: dict[str, Any], prompt: str
) -> dict[str, Any]:
    return await asyncio.to_thread(generate, modality, model, params, prompt)
