# Common Modules

This directory contains shared utilities used across multiple agents in the coding-prompt-preprocessor project.

## Rate Limiting (`rate_limiting.py`)

### Features

The rate limiting module provides comprehensive error handling and retry logic for Google ADK agents:

#### **429 Rate Limit Handling**
- Detects Google GenAI API `429 RESOURCE_EXHAUSTED` errors
- Parses `retryDelay` from API error responses (supports multiple formats)
- Implements exponential backoff with jitter for successive retries
- Respects API-specified retry delays

#### **5xx Server Error Handling** 
- Handles 500, 502, 503, 504 server errors
- Implements immediate retry with exponential backoff
- Different backoff strategies for different error types

#### **Intelligent Retry Logic**
- **Exponential Backoff**: `delay = base_delay * (2 ** attempt)`
- **Jitter**: ±50% randomization to avoid thundering herd
- **Max Retries**: Configurable (default: 3 attempts)
- **Max Delay**: Caps to prevent infinite waits

#### **Error Parsing**
- Comprehensive JSON parsing from error responses
- Multiple fallback patterns for extracting `retryDelay`
- Handles both `google.genai.errors.ClientError` and generic exceptions

### Usage

```python
from common.rate_limiting import create_rate_limit_callbacks, RateLimiter

# Create custom rate limiter
rate_limiter = RateLimiter(max_calls=10, window_seconds=60, logger=logger)
pre_callback, post_callback = create_rate_limit_callbacks(
    rate_limiter_instance=rate_limiter,
    logger=logger,
    max_retries=3
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

### Error Types Handled

| Error Type | HTTP Codes | Strategy |
|------------|------------|----------|
| `genai_rate_limit` | 429 + RESOURCE_EXHAUSTED | API delay + exponential backoff |
| `server_error` | 500, 502, 503, 504 | Exponential backoff (2s base) |
| `rate_limit` | 429 (general) | Exponential backoff (5s base) |

### Backoff Calculations

- **GenAI Rate Limits**: `max(api_delay, exponential_backoff(1s base, 30s max))`
- **Server Errors**: `exponential_backoff(2s base, 60s max)`
- **Other Rate Limits**: `exponential_backoff(5s base, 120s max)`

## Enhanced Error Handling

### Runner-Level Error Handling

The rate limiting module now provides `create_enhanced_runner()` which wraps the ADK Runner to catch LLM exceptions that occur **before** the framework's callbacks are invoked.

**Why this is needed:** In ADK 1.0.0, `before_model_callback` and `after_model_callback` are only called around **successful** LLM interactions. When 429 or 500 errors occur during the LLM call itself (in the Google GenAI SDK layers), these exceptions bubble up **before** the ADK framework gets control, so callbacks are never invoked.

**Solution:** The enhanced runner wraps the `Runner.run_async()` method to catch these exceptions at a higher level in the call stack.

```python
from common.rate_limiting import create_enhanced_runner
from project_test_summarizer.agent import root_agent
from project_test_summarizer.session import session_manager

# Instead of using Runner directly:
# runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# Use the enhanced runner:
runner = create_enhanced_runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    max_retries=3,
    logger=logger
)

# Use normally - error handling is transparent
async for event in runner.run_async(user_id, session_id, message):
    # Handle events normally
    pass
```

**Features:**
- Catches `google.genai.errors.ClientError` (429 RESOURCE_EXHAUSTED)
- Catches `google.genai.errors.ServerError` (500 INTERNAL, 502, 503, 504)
- Implements exponential backoff with jitter
- Respects API-specified retry delays from Google GenAI
- Transparent to existing code - just replace Runner creation
- Per-request retry tracking to avoid infinite loops

## Logging Setup (`logging_setup.py`)

Provides configurable logging with file rotation and stdout redirection for consistent logging across all agents.

### Features
- Configurable log file names and rotation
- Thread-safe stdout/stderr redirection
- Multiple log levels and formatters
- Integration with rate limiting for debug logging

## Tools (`tools.py`)

Shared utility functions used by multiple agents for file operations, codebase analysis, and session management. 