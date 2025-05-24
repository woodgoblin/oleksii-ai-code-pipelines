"""Rate limiting utility for API calls."""

import time
import re
import asyncio
from collections import deque
from cursor_prompt_preprocessor.config import RATE_LIMIT_MAX_CALLS, RATE_LIMIT_WINDOW
from common.logging_setup import logger

class RateLimiter:
    """Rate limiter for API calls that enforces a maximum number of calls per time window.
    
    Async-safe implementation using a sliding window approach.
    """
    def __init__(self, max_calls=RATE_LIMIT_MAX_CALLS, window_seconds=RATE_LIMIT_WINDOW):
        """Initialize the rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the time window
            window_seconds: The time window in seconds
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.call_history = deque()
        self.lock = asyncio.Lock()
        self._next_allowed_call_time = 0
        logger.info(f"Async Rate limiter initialized: {max_calls} calls per {window_seconds} seconds")
    
    async def wait_if_needed(self):
        """Asynchronously waits until a call can be made without exceeding the rate limit
        or an explicit delay period.
        """
        async with self.lock:
            while True:
                current_time = time.time()

                # Honor explicit delay first
                if current_time < self._next_allowed_call_time:
                    wait_for_explicit_delay = self._next_allowed_call_time - current_time
                    logger.info(f"Honoring explicit API delay. Waiting for {wait_for_explicit_delay:.2f} seconds...")
                    await asyncio.sleep(wait_for_explicit_delay)
                    current_time = time.time()

                # Remove calls older than the window from history
                while self.call_history and self.call_history[0] < current_time - self.window_seconds:
                    self.call_history.popleft()
                
                if len(self.call_history) < self.max_calls:
                    self.call_history.append(current_time)
                    break
                
                # If queue is full, calculate wait time based on the oldest call in the window
                oldest_call_in_window = self.call_history[0]
                wait_duration = (oldest_call_in_window + self.window_seconds) - current_time + 0.01
                
                logger.info(f"Rate limit window full ({len(self.call_history)} calls). Waiting for {wait_duration:.2f} seconds...")
                await asyncio.sleep(wait_duration)
                # Loop will continue, re-checking conditions

    def update_next_allowed_call_time(self, delay_seconds: float):
        """Sets a minimum time for the next call, typically after a 429 error."""
        # This method might be called from a synchronous context (like the end of handle_rate_limit if it's not fully async yet)
        # or an async one. For simplicity, it directly sets the time.
        # If called from async, ensure lock is handled if needed, but _next_allowed_call_time is a simple assignment.
        # Consider acquiring lock if complex logic were here.
        new_allowed_time = time.time() + delay_seconds
        self._next_allowed_call_time = max(self._next_allowed_call_time, new_allowed_time)
        logger.info(f"Explicit next allowed call time updated to: {self._next_allowed_call_time} (in {delay_seconds:.2f}s)")

async def pre_model_rate_limit(callback_context, llm_request):
    """Pre-model callback to enforce rate limiting before making API calls.
    
    Args:
        callback_context: The callback context
        llm_request: The LLM request parameters
        
    Returns:
        None to continue with the normal request, or a response to short-circuit
    """
    try:
        logger.info("Async Pre-model rate limit check")
        await rate_limiter.wait_if_needed()
        return None  # Continue with normal request
    except Exception as e:
        logger.error(f"Error in async pre-model rate limit check: {e}")
        from google.genai import types
        return types.Content(
            role="model", 
            parts=[types.Part(text="Error in rate limiting, please try again.")]
        )

async def handle_rate_limit(callback_context, llm_response):
    """After-model callback to handle rate limit errors.
    
    Args:
        callback_context: The callback context
        llm_response: The LLM response
        
    Returns:
        Modified response if rate limit was hit, None otherwise
    """
    # Check if there's an error in the response
    error_content = None
    if isinstance(llm_response, Exception):
        error_content = str(llm_response)
    elif hasattr(llm_response, 'error'):
        error_content = str(getattr(llm_response, 'error', None))
    elif hasattr(llm_response, '_raw_response') and hasattr(llm_response._raw_response, 'text'):
        error_content = llm_response._raw_response.text

    if error_content and ("429" in error_content or "RESOURCE_EXHAUSTED" in error_content.upper()):
        logger.warning(f"Rate limit error detected: {error_content}")
        
        retry_delay_seconds = 5.0
        
        # Attempt to parse google.genai.errors.ClientError style details
        # Error: 429 RESOURCE_EXHAUSTED. {'error': {..., 'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '24s'}]}}
        try:
            # Look for retryDelay in the string representation
            delay_match = re.search(r"['\"]retryDelay['\"]:\s*['\"](\\d+)(?:\\.\\d+)?s['\"]", error_content)
            if delay_match:
                retry_delay_seconds = float(delay_match.group(1))
                logger.info(f"Extracted retryDelay from error: {retry_delay_seconds}s")
            else:
                logger.info(f"Could not extract retryDelay, using default: {retry_delay_seconds}s")
        except Exception as e_parse:
            logger.error(f"Error parsing retry_delay from error content: {e_parse}. Using default.")

        # Update the global rate limiter's next allowed call time
        rate_limiter.update_next_allowed_call_time(retry_delay_seconds + 0.5)
        
        logger.info(f"Rate limit 429. Signaled rate_limiter to wait for at least {retry_delay_seconds:.2f}s.")
        
        # ADK's after_model_callback cannot directly trigger a retry of the original call.
        # It can only modify the response or signal an error.
        # Returning a specific content to indicate to the user/system that a delay was enforced.
        from google.genai import types
        return types.generate_content_response.GenerateContentResponse(
             done=True,
             iterator=None,
             result=None,
             _raw_response=llm_response._raw_response if hasattr(llm_response, '_raw_response') else None,
             error = types.Content(
                 role="model",
                 parts=[types.Part(text=f"API rate limit hit (429). The system will automatically delay subsequent calls. Last error: {error_content[:200]}")]
             )
        )

    return None

# Create a global rate limiter instance
rate_limiter = RateLimiter() 