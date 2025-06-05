"""Simple retry runner for LLM API errors - handles 429 and configurable backoff for others."""

import asyncio
import random
import re
from typing import Any, Callable, Optional, Tuple


def extract_retry_delay(error_content: str) -> float:
    """Extract retry delay from 429 error message."""
    try:
        # Pattern: "retryDelay":"5s" or 'retryDelay':'5s'
        delay_match = re.search(
            r"['\"]retryDelay['\"]:\s*['\"](\d+(?:\.\d+)?)s?['\"]", error_content
        )
        if delay_match:
            return float(delay_match.group(1))

        # Pattern: retryDelay: 5 (without quotes)
        delay_match = re.search(r"retryDelay:\s*(\d+(?:\.\d+)?)", error_content)
        if delay_match:
            return float(delay_match.group(1))

        # Pattern: Retry-After header
        delay_match = re.search(r"[Rr]etry-[Aa]fter:\s*(\d+)", error_content)
        if delay_match:
            return float(delay_match.group(1))
    except Exception:
        pass
    return 5.0  # Default for 429


def is_429_error(error: Exception) -> Tuple[bool, str]:
    """Check if error is 429 rate limit."""
    error_content = str(error)
    is_429 = "429" in error_content or "RESOURCE_EXHAUSTED" in error_content.upper()
    return is_429, error_content


async def retry_with_simple_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 2.0,
    logger_instance: Optional[Any] = None,
    *args,
    **kwargs,
) -> Any:
    """Execute function with simple retry logic.

    Args:
        func: Async function to execute
        max_retries: Maximum retry attempts
        base_delay: Base delay for non-429 errors (exponential backoff)
        logger_instance: Logger instance
        *args, **kwargs: Arguments to pass to func

    Returns:
        Result of successful function execution

    Raises:
        Exception: Last exception if all retries failed
    """
    log = logger_instance
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0 and log:
                log.info(f"Retry attempt {attempt}/{max_retries}")

            result = await func(*args, **kwargs)

            if attempt > 0 and log:
                log.info(f"Success after {attempt} retries")

            return result

        except Exception as e:
            last_exception = e
            error_content = str(e)

            # Don't retry on last attempt
            if attempt >= max_retries:
                if log:
                    log.error(
                        f"Max retries ({max_retries}) exceeded. Last error: {error_content[:100]}..."
                    )
                break

            # Check if 429 error
            is_429, _ = is_429_error(e)

            if is_429:
                # Use API-specified delay for 429
                delay = extract_retry_delay(error_content)
                if log:
                    log.warning(
                        f"429 rate limit. Retrying in {delay:.1f}s. Error: {error_content[:100]}..."
                    )
            else:
                # Simple exponential backoff for all other errors
                delay = base_delay * (2**attempt)
                # Add small jitter
                delay += random.uniform(0, delay * 0.1)
                if log:
                    log.warning(
                        f"Error on attempt {attempt + 1}. Retrying in {delay:.1f}s. Error: {error_content[:100]}..."
                    )

            await asyncio.sleep(delay)

    # All retries failed
    raise last_exception


def create_enhanced_runner(
    agent,
    app_name: str,
    session_service,
    max_retries: int = 3,
    base_delay: float = 2.0,
    logger_instance: Optional[Any] = None,
):
    """Create an enhanced Runner that handles LLM errors with simple retry logic.

    Args:
        agent: ADK agent instance
        app_name: Application name
        session_service: Session service instance
        max_retries: Maximum number of retries (default: 3)
        base_delay: Base delay for exponential backoff (default: 2.0s)
        logger_instance: Logger instance to use

    Returns:
        Enhanced Runner instance with retry capabilities
    """
    from google.adk.runner import Runner

    # Create the original runner
    original_runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    class EnhancedRunner:
        """Enhanced Runner wrapper with simple retry logic."""

        def __init__(self, original_runner, max_retries, base_delay, logger_instance):
            self._original_runner = original_runner
            self._max_retries = max_retries
            self._base_delay = base_delay
            self._logger = logger_instance

        async def run_async(self, user_id: str, session_id: str, message: str):
            """Run with retry logic for LLM errors."""

            async def _collect_events():
                events = []
                async for event in self._original_runner.run_async(user_id, session_id, message):
                    events.append(event)
                return events

            # Execute with retry logic
            events = await retry_with_simple_backoff(
                _collect_events, self._max_retries, self._base_delay, self._logger
            )

            # Yield collected events
            for event in events:
                yield event

        def __getattr__(self, name):
            """Delegate other attributes to original runner."""
            return getattr(self._original_runner, name)

    return EnhancedRunner(original_runner, max_retries, base_delay, logger_instance)
