"""Pytest tests for retry runner functionality."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from common.retry_runner import extract_retry_delay, is_429_error, retry_with_simple_backoff


class MockLLMError(Exception):
    """Mock LLM error for testing."""

    def __init__(self, message: str):
        super().__init__(message)


class TestRetryDelayExtraction:
    """Test retry delay extraction from error messages."""

    def test_extract_delay_from_quoted_json_format(self):
        """Should extract delay from quoted JSON format like "retryDelay":"5s"."""
        # Arrange
        error_content = '{"error": "rate limit", "retryDelay":"10s"}'

        # Act
        delay = extract_retry_delay(error_content)

        # Assert
        assert delay == 10.0

    def test_extract_delay_from_unquoted_format(self):
        """Should extract delay from unquoted format like retryDelay: 5."""
        # Arrange
        error_content = "Error: rate limit exceeded, retryDelay: 15"

        # Act
        delay = extract_retry_delay(error_content)

        # Assert
        assert delay == 15.0

    def test_extract_delay_from_retry_after_header(self):
        """Should extract delay from Retry-After header format."""
        # Arrange
        error_content = "HTTP 429: Too Many Requests\nRetry-After: 30"

        # Act
        delay = extract_retry_delay(error_content)

        # Assert
        assert delay == 30.0

    def test_returns_default_delay_when_no_pattern_matches(self):
        """Should return default delay when no pattern matches."""
        # Arrange
        error_content = "Some random error message"

        # Act
        delay = extract_retry_delay(error_content)

        # Assert
        assert delay == 5.0


class TestErrorDetection:
    """Test 429 error detection."""

    def test_detects_429_error_with_status_code(self):
        """Should detect 429 error when status code is present."""
        # Arrange
        error = MockLLMError("HTTP 429: Too Many Requests")

        # Act
        is_429, content = is_429_error(error)

        # Assert
        assert is_429 is True
        assert "429" in content

    def test_detects_resource_exhausted_error(self):
        """Should detect RESOURCE_EXHAUSTED error."""
        # Arrange
        error = MockLLMError("RESOURCE_EXHAUSTED: Quota exceeded")

        # Act
        is_429, content = is_429_error(error)

        # Assert
        assert is_429 is True
        assert "RESOURCE_EXHAUSTED" in content

    def test_does_not_detect_non_429_errors(self):
        """Should not detect non-429 errors as rate limits."""
        # Arrange
        error = MockLLMError("HTTP 500: Internal Server Error")

        # Act
        is_429, content = is_429_error(error)

        # Assert
        assert is_429 is False
        assert "500" in content


class TestRetryLogic:
    """Test retry logic with simple backoff."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt_without_retry(self):
        """Should succeed on first attempt without any retries."""
        # Arrange
        mock_func = AsyncMock(return_value="success")

        # Act
        result = await retry_with_simple_backoff(mock_func, max_retries=3, base_delay=0.1)

        # Assert
        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_429_error_with_api_delay(self):
        """Should retry 429 error using API-specified delay."""
        # Arrange
        mock_func = AsyncMock()
        mock_func.side_effect = [
            MockLLMError('429 RESOURCE_EXHAUSTED: {"retryDelay":"1s"}'),
            "success",
        ]

        # Act
        result = await retry_with_simple_backoff(mock_func, max_retries=3, base_delay=0.1)

        # Assert
        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_non_429_error_with_exponential_backoff(self):
        """Should retry non-429 errors with exponential backoff."""
        # Arrange
        mock_func = AsyncMock()
        mock_func.side_effect = [MockLLMError("HTTP 500: Internal Server Error"), "success"]

        # Act
        result = await retry_with_simple_backoff(mock_func, max_retries=3, base_delay=0.1)

        # Assert
        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_fails_after_max_retries_exceeded(self):
        """Should fail after max retries are exceeded."""
        # Arrange
        mock_func = AsyncMock()
        mock_func.side_effect = MockLLMError("Persistent error")

        # Act & Assert
        with pytest.raises(MockLLMError, match="Persistent error"):
            await retry_with_simple_backoff(mock_func, max_retries=2, base_delay=0.1)

        assert mock_func.call_count == 3  # Initial attempt + 2 retries
