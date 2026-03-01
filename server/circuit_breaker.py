"""
Circuit breaker for LLM API calls.

When the failure count exceeds the threshold, the circuit opens and subsequent
calls fail fast with CircuitOpenError until the recovery window has elapsed
(half-open), then one call is allowed to test recovery.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, TypeVar

from loguru import logger

T = TypeVar("T")


class CircuitOpenError(Exception):
    """Raised when the circuit is open and the call is rejected."""

    def __init__(self, message: str = "Circuit breaker is open; LLM calls temporarily disabled."):
        self.message = message
        super().__init__(self.message)


class CircuitBreaker:
    """In-memory circuit breaker: closed -> open -> half-open -> closed."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_seconds: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = "closed"  # closed | open | half_open
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures; "
                f"recovery in {self.recovery_seconds}s"
            )

    def _maybe_transition_to_half_open(self) -> None:
        if self._state != "open":
            return
        if self._last_failure_time is None:
            self._state = "half_open"
            return
        if time.monotonic() - self._last_failure_time >= self.recovery_seconds:
            self._state = "half_open"
            logger.info("Circuit breaker entering half-open; next call will be attempted.")

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """
        Call fn() and await the result if the circuit allows it; otherwise raise CircuitOpenError.
        Use a callable so the coroutine is only created when the circuit is closed (avoids
        leaving a coroutine unawaited when the call is rejected).
        On success, record success; on failure, record failure.
        """
        async with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == "open":
                raise CircuitOpenError()
            # closed or half_open: allow the call
        try:
            result = await fn()
            async with self._lock:
                self.record_success()
            return result
        except Exception:
            async with self._lock:
                if self._state == "half_open":
                    self._state = "open"
                    self._last_failure_time = time.monotonic()
                self.record_failure()
            raise


# Singleton used by the streaming agent loop (one breaker per process for the default LLM).
_default_breaker: CircuitBreaker | None = None


def get_circuit_breaker(
    failure_threshold: int = 5,
    recovery_seconds: float = 60.0,
) -> CircuitBreaker:
    """Get or create the default circuit breaker (singleton)."""
    global _default_breaker
    if _default_breaker is None:
        _default_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
        )
    return _default_breaker
