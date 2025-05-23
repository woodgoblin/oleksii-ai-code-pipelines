"""Rate limiting utility for API calls."""

import time
import re
import threading
from collections import deque
from cursor_prompt_preprocessor.config import RATE_LIMIT_MAX_CALLS, RATE_LIMIT_WINDOW
from common.logging_setup import logger

class RateLimiter:
    """Rate limiter for API calls that enforces a maximum number of calls per time window.
    
    Thread-safe implementation using a sliding window approach.
    """
    def __init__(self, max_calls=RATE_LIMIT_MAX_CALLS, window_seconds=RATE_LIMIT_WINDOW):
        """Initialize the rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the time window
            window_seconds: The time window in seconds
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.call_history = deque(maxlen=max_calls)
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        logger.info(f"Rate limiter initialized: {max_calls} calls per {window_seconds} seconds")
    
    def wait_if_needed(self):
        """Blocks until a call can be made without exceeding the rate limit.
        
        This method will either return immediately if the rate limit permits,
        or block until enough time has passed to allow another call.
        """
        with self.lock:
            current_time = time.time()
            
            # If we haven't reached the max calls yet, allow immediately
            if len(self.call_history) < self.max_calls:
                self.call_history.append(current_time)
                return
            
            # Check if the oldest call is outside our window
            oldest_call_time = self.call_history[0]
            time_since_oldest = current_time - oldest_call_time
            
            # If we've used all our quota and need to wait
            if time_since_oldest < self.window_seconds:
                wait_time = self.window_seconds - time_since_oldest + 0.1  # Add a small buffer
                logger.info(f"Rate limit reached. Waiting for {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                # After waiting, current time has changed
                current_time = time.time()
            
            # Update our history
            self.call_history.popleft()
            self.call_history.append(current_time)

def pre_model_rate_limit(callback_context, llm_request):
    """Pre-model callback to enforce rate limiting before making API calls.
    
    Args:
        callback_context: The callback context
        llm_request: The LLM request parameters
        
    Returns:
        None to continue with the normal request, or a response to short-circuit
    """
    try:
        logger.info("Pre-model rate limit check")
        rate_limiter.wait_if_needed()
        return None  # Continue with normal request
    except Exception as e:
        logger.error(f"Error in pre-model rate limit check: {e}")
        # If there's an error in rate limiting, create a fallback response
        from google.genai import types
        return types.Content(
            role="model", 
            parts=[types.Part(text="Error in rate limiting, please try again.")]
        )

def handle_rate_limit(callback_context, llm_response):
    """After-model callback to handle rate limit errors.
    
    Args:
        callback_context: The callback context
        llm_response: The LLM response
        
    Returns:
        Modified response if rate limit was hit, None otherwise
    """
    # Check if there's an error in the response
    error = getattr(llm_response, 'error', None)
    if error and "429" in str(error):
        logger.warning(f"Rate limit error detected: {error}")
        
        # Extract retry delay if provided in the error message
        retry_delay = 5  # Default 5 seconds
        delay_match = re.search(r"'retryDelay': '(\d+)s'", str(error))
        if delay_match:
            retry_delay = int(delay_match.group(1))
            
        # Wait before retrying
        logger.info(f"Rate limit hit, waiting for {retry_delay} seconds before retry...")
        time.sleep(retry_delay + 1)  # Add 1 second buffer
        
        # Create a modified response indicating we'll retry
        from google.genai import types
        return types.Content(
            role="model",
            parts=[types.Part(text="Rate limit hit, retrying after delay...")]
        )
    
    # If no rate limit error, return None to use the original response
    return None

# Create a global rate limiter instance
rate_limiter = RateLimiter() 