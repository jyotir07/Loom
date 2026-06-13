"""Retry policy with exponential backoff + jitter.

Sync + async variants. Exceptions are classified into three buckets:

  - retryable      : RateLimitError, transient network errors (timeouts,
                     ConnectionError). Worth a backoff + try again.
  - never_retryable: AuthError, ModelNotFoundError, ProviderError on bad
                     input. Surface immediately — retrying just wastes
                     time and money.
  - unknown        : Anything else. Default policy treats as retryable
                     if it inherits from LoomError, otherwise re-raises.

Tunable on the Loom client:

    Loom(retry=RetryPolicy(max_attempts=5, base_delay=0.5))

or disabled entirely:

    Loom(retry=None)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from loom.errors import AuthError, LoomError, ModelNotFoundError, RateLimitError

_logger = logging.getLogger("loom.retry")

T = TypeVar("T")


def _default_retryable_exceptions() -> tuple[type[BaseException], ...]:
    """Exception types we retry by default.

    `requests` is a hard dep, so we know its exception types are importable.
    `httpx` is included if installed (used by openai / anthropic SDKs).
    `openai`'s own classes (APIConnectionError, APITimeoutError) are matched
    via duck-typed message inspection in `_is_retryable` to avoid pulling
    the SDK in at import time.
    """
    types: list[type[BaseException]] = [
        RateLimitError,
        TimeoutError,
        ConnectionError,
    ]
    try:
        import requests

        types.append(requests.exceptions.ConnectionError)
        types.append(requests.exceptions.Timeout)
    except ImportError:
        pass
    try:
        import httpx  # type: ignore[import-not-found]

        types.append(httpx.TimeoutException)
        types.append(httpx.ConnectError)
    except ImportError:
        pass
    return tuple(types)


@dataclass
class RetryPolicy:
    """How Loom backs off and re-tries a failing generate() call.

    `retry_on` is a tuple of exception types that trigger a retry. Anything
    in `never_retry_on` short-circuits immediately. Anything else falls
    through to a single attempt.
    """

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.25  # fraction of the computed delay
    retry_on: tuple[type[BaseException], ...] = field(
        default_factory=_default_retryable_exceptions
    )
    never_retry_on: tuple[type[BaseException], ...] = (
        AuthError,
        ModelNotFoundError,
    )

    def is_retryable(self, exc: BaseException) -> bool:
        if isinstance(exc, self.never_retry_on):
            return False
        if isinstance(exc, self.retry_on):
            return True
        # Best-effort duck-type for OpenAI/Anthropic SDK network errors —
        # their connection/timeout classes don't always inherit from stdlib.
        name = type(exc).__name__
        if name in {
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError",
            "ServiceUnavailableError",
        }:
            return True
        return False

    def delay_for_attempt(self, attempt: int) -> float:
        """Compute the sleep before `attempt` (1-indexed: attempt=1 is the
        first retry after the original call)."""
        raw = self.base_delay * (2 ** (attempt - 1))
        raw = min(raw, self.max_delay)
        if self.jitter > 0:
            spread = raw * self.jitter
            raw = raw + random.uniform(-spread, spread)
        return max(0.0, raw)


def run_with_retry(policy: RetryPolicy | None, fn: Callable[[], T]) -> T:
    """Invoke `fn()` under `policy`. With policy=None, no retry at all."""
    if policy is None or policy.max_attempts <= 1:
        return fn()

    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            last_exc = exc
            if attempt >= policy.max_attempts or not policy.is_retryable(exc):
                raise
            delay = policy.delay_for_attempt(attempt)
            _logger.info(
                "loom.retry attempt=%d/%d sleeping=%.2fs after %s: %s",
                attempt,
                policy.max_attempts,
                delay,
                type(exc).__name__,
                exc,
            )
            time.sleep(delay)
    # Unreachable, but keeps type-checkers happy.
    assert last_exc is not None
    raise last_exc


async def arun_with_retry(
    policy: RetryPolicy | None, fn: Callable[[], Awaitable[T]]
) -> T:
    if policy is None or policy.max_attempts <= 1:
        return await fn()

    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await fn()
        except BaseException as exc:
            last_exc = exc
            if attempt >= policy.max_attempts or not policy.is_retryable(exc):
                raise
            delay = policy.delay_for_attempt(attempt)
            _logger.info(
                "loom.retry attempt=%d/%d sleeping=%.2fs after %s: %s",
                attempt,
                policy.max_attempts,
                delay,
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
