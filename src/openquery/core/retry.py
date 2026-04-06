"""Retry with exponential backoff."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


def retry[T](
    fn: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Execute fn with exponential backoff retry.

    Args:
        fn: Callable to execute.
        max_attempts: Maximum number of attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries.
        exceptions: Tuple of exception types to catch and retry.
        on_retry: Optional callback(attempt, error) called before each retry.

    Returns:
        Result of fn().

    Raises:
        The last exception if all attempts fail.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except exceptions as e:
            last_error = e
            if attempt == max_attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "Attempt %d/%d failed: %s. Retrying in %.1fs",
                attempt,
                max_attempts,
                e,
                delay,
            )
            if on_retry:
                on_retry(attempt, e)
            time.sleep(delay)

    raise last_error  # type: ignore[misc]
