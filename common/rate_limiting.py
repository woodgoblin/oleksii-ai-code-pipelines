"""Rate limiting utility for MCP agents - Google ADK compatible."""

import time
import re
import asyncio
from collections import deque
from typing import Optional, Callable, Any, Tuple

from cursor_prompt_preprocessor.config import RATE_LIMIT_MAX_CALLS, RATE_LIMIT_WINDOW
from common.logging_setup import logger

class RateLimiter:
    """Async-safe rate limiter using sliding window approach for MCP agents."""
    
    def __init__(self, max_calls=RATE_LIMIT_MAX_CALLS, window_seconds=RATE_LIMIT_WINDOW, logger_instance=None):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.call_history = deque()
        self.lock = asyncio.Lock()
        self._next_allowed_call_time = 0
        self.logger = logger_instance or logger
        self.logger.info(f"Rate limiter initialized: {max_calls} calls per {window_seconds}s")
    
    async def wait_if_needed(self):
        """Wait until a call can be made without exceeding rate limits."""
        async with self.lock:
            while True:
                current_time = time.time()
                
                # Honor explicit delays first (from 429 errors)
                if current_time < self._next_allowed_call_time:
                    wait_time = self._next_allowed_call_time - current_time
                    self.logger.info(f"Honoring API delay: {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
                
                # Clean old calls from sliding window
                while self.call_history and self.call_history[0] < current_time - self.window_seconds:
                    self.call_history.popleft()
                
                # Allow call if under limit
                if len(self.call_history) < self.max_calls:
                    self.call_history.append(current_time)
                    break
                
                # Wait for oldest call to expire
                wait_time = (self.call_history[0] + self.window_seconds) - current_time + 0.01
                self.logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    def update_next_allowed_call_time(self, delay_seconds: float):
        """Set minimum time for next call after 429 error."""
        new_time = time.time() + delay_seconds
        self._next_allowed_call_time = max(self._next_allowed_call_time, new_time)
        self.logger.info(f"Next call delayed by {delay_seconds:.2f}s")

def _extract_retry_delay(error_content: str) -> float:
    """Extract retry delay from error message."""
    try:
        # Pattern: "retryDelay":"5s" or 'retryDelay':'5s'
        delay_match = re.search(r"['\"]retryDelay['\"]:\s*['\"](\d+(?:\.\d+)?)s?['\"]", error_content)
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
    except Exception as e:
        logger.debug(f"Could not parse retry delay: {e}")
    return 5.0  # Default delay

def create_rate_limit_callbacks(
    rate_limiter_instance: Optional[RateLimiter] = None,
    logger_instance: Optional[Any] = None,
    max_retries: int = 3
) -> Tuple[Callable, Callable]:
    """Create simple rate limit callbacks.
    
    Returns:
        Tuple of (pre_model_callback, after_model_callback)
    """
    limiter = rate_limiter_instance or rate_limiter
    log = logger_instance or logger
    
    async def pre_model_rate_limit(callback_context, llm_request):
        """Pre-model callback for rate limiting."""
        try:
            await limiter.wait_if_needed()
            return None  # Continue with request
        except Exception as e:
            log.error(f"Rate limit error: {e}")
            from google.genai import types
            return types.Content(
                role="model", 
                parts=[types.Part(text="Rate limiting error, please try again.")]
            )

    async def handle_rate_limit_and_server_errors(callback_context, llm_response):
        """After-model callback to handle 429 errors."""
        # Check for rate limit errors
        error_content = ""
        
        if isinstance(llm_response, Exception):
            error_content = str(llm_response)
        elif hasattr(llm_response, 'error'):
            error_content = str(getattr(llm_response, 'error', ''))
        elif hasattr(llm_response, '_raw_response') and hasattr(llm_response._raw_response, 'text'):
            error_content = llm_response._raw_response.text
        
        is_rate_limited = error_content and ("429" in error_content or "RESOURCE_EXHAUSTED" in error_content.upper())
        
        if not is_rate_limited:
            return None
        
        log.warning(f"Rate limit detected: {error_content[:100]}...")
        retry_delay = _extract_retry_delay(error_content)
        limiter.update_next_allowed_call_time(retry_delay + 0.5)
        
        # Return error response
        from google.genai import types
        return types.generate_content_response.GenerateContentResponse(
            done=True,
            iterator=None,
            result=None,
            _raw_response=getattr(llm_response, '_raw_response', None),
            error=types.Content(
                role="model",
                parts=[types.Part(text=f"API rate limit (429). System will delay subsequent calls. Error: {error_content[:150]}...")]
            )
        )
    
    return pre_model_rate_limit, handle_rate_limit_and_server_errors

# Global rate limiter instance
rate_limiter = RateLimiter() 