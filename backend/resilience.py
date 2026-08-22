"""Resilience helpers for external API calls: retries + circuit breaker."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, TypeVar

from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 30


class CircuitBreakerOpenError(RuntimeError):
    """Raised when the circuit breaker is open and calls are blocked."""


class AsyncCircuitBreaker:
    """Small async circuit breaker implementation for provider calls."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_ts: float = 0.0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            self._assert_call_allowed()

        try:
            result = await func()
        except Exception:
            await self._record_failure()
            raise

        await self._record_success()
        return result

    def _assert_call_allowed(self) -> None:
        if self.state != CircuitState.OPEN:
            return

        elapsed = time.monotonic() - self.last_failure_ts
        if elapsed >= self.config.recovery_timeout_seconds:
            self.state = CircuitState.HALF_OPEN
            return

        raise CircuitBreakerOpenError("Circuit breaker open: provider temporarily unavailable")

    async def _record_failure(self) -> None:
        async with self._lock:
            self.failure_count += 1
            self.last_failure_ts = time.monotonic()
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

    async def _record_success(self) -> None:
        async with self._lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED


def is_transient_llm_error(exc: Exception) -> bool:
    """Retry on common transient issues: 429/rate limit, timeout, 5xx class errors."""
    message = str(exc).lower()
    transient_markers = (
        "429",
        "rate limit",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "service unavailable",
        "502",
        "503",
        "504",
    )
    return any(marker in message for marker in transient_markers)


async def with_retry_and_circuit_breaker(
    operation: Callable[[], Awaitable[T]],
    circuit_breaker: AsyncCircuitBreaker,
    max_attempts: int = 4,
) -> T:
    """Execute operation with exponential-backoff retry and circuit breaker protection."""

    async def _guarded() -> T:
        return await circuit_breaker.call(operation)

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(is_transient_llm_error),
        reraise=True,
    ):
        with attempt:
            return await _guarded()

    raise RuntimeError("Retry loop exhausted")
