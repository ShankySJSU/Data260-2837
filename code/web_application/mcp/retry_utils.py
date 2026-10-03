from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass
import random
import time
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar("T")


class TransientOperationError(Exception):
    """
    Error that may succeed if the operation is retried.
    """
    pass


@dataclass(frozen=True)
class RetryPolicy:
    timeout_seconds: float = 1.0
    max_attempts: int = 3
    base_delay_seconds: float = 0.01
    max_delay_seconds: float = 0.05


@dataclass
class RetryResult(Generic[T]):
    success: bool
    value: Optional[T]
    error: Optional[str]
    attempts: int
    latency_ms: float


class SeededFaultInjector:
    """
    Reproducible failure injector.

    The same seed and failure rate produce the same
    failure sequence each time.
    """

    def __init__(
        self,
        seed: int,
        failure_rate: float,
    ):
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError(
                "failure_rate must be between 0.0 and 1.0"
            )

        self.random = random.Random(seed)
        self.failure_rate = failure_rate

    def should_fail(self) -> bool:
        return (
            self.random.random()
            < self.failure_rate
        )


def run_with_timeout(
    operation: Callable[[], T],
    timeout_seconds: float,
) -> T:
    executor = ThreadPoolExecutor(
        max_workers=1
    )

    future = executor.submit(operation)

    try:
        return future.result(
            timeout=timeout_seconds
        )

    except FutureTimeoutError as exc:
        future.cancel()

        raise TransientOperationError(
            "operation timed out"
        ) from exc

    finally:
        executor.shutdown(
            wait=False,
            cancel_futures=True,
        )


def call_with_retry(
    operation: Callable[[], T],
    injector: SeededFaultInjector,
    policy: RetryPolicy,
) -> RetryResult[T]:
    start = time.perf_counter()
    last_error = None

    for attempt in range(
        1,
        policy.max_attempts + 1,
    ):
        try:
            if injector.should_fail():
                raise TransientOperationError(
                    "injected transient failure"
                )

            value = run_with_timeout(
                operation,
                policy.timeout_seconds,
            )

            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            return RetryResult(
                success=True,
                value=value,
                error=None,
                attempts=attempt,
                latency_ms=latency_ms,
            )

        except TransientOperationError as exc:
            last_error = str(exc)

            if attempt >= policy.max_attempts:
                break

            delay = min(
                policy.base_delay_seconds
                * (2 ** (attempt - 1)),
                policy.max_delay_seconds,
            )

            time.sleep(delay)

        except Exception as exc:
            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            return RetryResult(
                success=False,
                value=None,
                error=f"non-retryable error: {exc}",
                attempts=attempt,
                latency_ms=latency_ms,
            )

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    return RetryResult(
        success=False,
        value=None,
        error=last_error or "operation failed",
        attempts=policy.max_attempts,
        latency_ms=latency_ms,
    )