# Common Modules

This directory contains shared utilities used across multiple agents in the coding-prompt-preprocessor project.

## Rate Limiting (`rate_limiting.py`)

Simple rate limiting for Google ADK agents with sliding window approach.

### Features
- **Sliding Window Rate Limiting**: Configurable calls per time window
- **429 Error Handling**: Extracts and respects API-specified retry delays
- **Async-Safe**: Thread-safe with proper locking

### Usage

```python
from common.rate_limiting import create_rate_limit_callbacks, RateLimiter

# Create rate limiter and callbacks
rate_limiter = RateLimiter(max_calls=10, window_seconds=60, logger_instance=logger)
pre_callback, post_callback = create_rate_limit_callbacks(
    rate_limiter_instance=rate_limiter,
    logger_instance=logger
)

# Use in LlmAgent
agent = LlmAgent(
    name="MyAgent",
    model="gemini-2.5-flash-preview-04-17",
    instruction="...",
    before_model_callback=pre_callback,
    after_model_callback=post_callback
)
```

## Retry Runner (`retry_runner.py`)

Simple retry logic for LLM API errors - handles 429 with API delays and all other errors with configurable exponential backoff.

### Features
- **429 Handling**: Uses API-specified retry delays from error messages
- **Simple Backoff**: Exponential backoff for all other errors
- **Enhanced Runner**: Wraps ADK Runner for transparent retry handling

### Usage

#### Enhanced Runner (Recommended)

```python
from common.retry_runner import create_enhanced_runner

runner = create_enhanced_runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    max_retries=3,
    base_delay=2.0,  # Base delay for exponential backoff
    logger_instance=logger
)

# Use normally - retry handling is transparent
async for event in runner.run_async(user_id, session_id, message):
    # Handle events normally
    pass
```

#### Standalone Retry Function

```python
from common.retry_runner import retry_with_simple_backoff

async def my_llm_function():
    # Your LLM API call here
    pass

result = await retry_with_simple_backoff(
    my_llm_function,
    max_retries=3,
    base_delay=2.0,
    logger_instance=logger
)
```

### Error Handling

| Error Type | Strategy |
|------------|----------|
| 429 Rate Limit | Uses API-specified delay from error message |
| All Other Errors | Exponential backoff: `base_delay * (2 ** attempt)` |

## Logging Setup (`logging_setup.py`)

Provides configurable logging with file rotation and stdout redirection for consistent logging across all agents.

## Tools (`tools.py`)

Shared utility functions used by multiple agents for file operations, codebase analysis, and session management. 