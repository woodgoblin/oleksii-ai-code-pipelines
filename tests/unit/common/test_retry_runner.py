"""Tests for retry runner functionality."""

import asyncio
import random
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from common.retry_runner import (
    create_enhanced_runner,
    extract_retry_delay,
    is_429_error,
    retry_with_simple_backoff,
)


class TestRetryDelayExtraction:
    """Test retry delay extraction from error messages."""

    @pytest.mark.parametrize(
        "error_content,expected_delay",
        [
            ('API Error: {"retryDelay":"3.5s","status":"RESOURCE_EXHAUSTED"}', 3.5),  # Quoted JSON
            ("Rate limit exceeded: retryDelay: 7.2", 7.2),  # Unquoted format
            ("HTTP 429: Retry-After: 10", 10.0),  # Retry-After header
            ("HTTP 429: retry-after: 15", 15.0),  # Case insensitive
            ("Error: {'retryDelay':'2.8s'}", 2.8),  # Single quotes
            ("Some generic error message", 5.0),  # No pattern, default
            ('Error: {"retryDelay":"invalid"}', 5.0),  # Malformed delay
        ],
    )
    def test_should_extract_delay_from_various_formats(self, error_content, expected_delay):
        """Should extract delay from various error message formats."""
        # Act
        result = extract_retry_delay(error_content)

        # Assert
        assert result == expected_delay


class TestErrorTypeDetection:
    """Test 429 error detection functionality."""

    @pytest.mark.parametrize(
        "error_message,expected_is_429",
        [
            ("HTTP 429: Too Many Requests", True),
            ("RESOURCE_EXHAUSTED: Rate limit exceeded", True),
            ("gRPC error: resource_exhausted", True),
            ("Network timeout error", False),
        ],
    )
    def test_should_detect_429_errors_correctly(self, error_message, expected_is_429):
        """Should detect 429/rate limit errors correctly."""
        # Arrange
        error = Exception(error_message)

        # Act
        is_429, content = is_429_error(error)

        # Assert
        assert is_429 == expected_is_429
        assert error_message in content


class TestRetryWithSimpleBackoff:
    """Test retry logic with simple backoff."""

    @pytest.mark.asyncio
    async def test_should_succeed_on_first_attempt(self):
        """Should succeed on first attempt without retries."""
        # Arrange
        mock_func = AsyncMock(return_value="success")
        mock_logger = Mock()

        # Act
        result = await retry_with_simple_backoff(
            mock_func, max_retries=3, logger_instance=mock_logger, arg1="test"
        )

        # Assert
        assert result == "success"
        mock_func.assert_called_once_with(arg1="test")
        # Should not log retry attempts for first success
        mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_retry_and_succeed_on_second_attempt(self):
        """Should retry and succeed on second attempt."""
        # Arrange
        mock_func = AsyncMock(side_effect=[Exception("temporary error"), "success"])
        mock_logger = Mock()

        # Act
        with patch("asyncio.sleep") as mock_sleep:
            result = await retry_with_simple_backoff(
                mock_func, max_retries=3, base_delay=1.0, logger_instance=mock_logger
            )

        # Assert
        assert result == "success"
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once()
        mock_logger.info.assert_any_call("Retry attempt 1/3")
        mock_logger.info.assert_any_call("Success after 1 retries")

    @pytest.mark.asyncio
    async def test_should_handle_429_error_with_api_delay(self):
        """Should handle 429 error with API-specified delay."""
        # Arrange
        error_with_delay = Exception('HTTP 429: {"retryDelay":"2.5s"}')
        mock_func = AsyncMock(side_effect=[error_with_delay, "success"])
        mock_logger = Mock()

        # Act
        with patch("asyncio.sleep") as mock_sleep:
            result = await retry_with_simple_backoff(
                mock_func, max_retries=3, logger_instance=mock_logger
            )

        # Assert
        assert result == "success"
        # Should use API-specified delay (2.5s) instead of exponential backoff
        mock_sleep.assert_called_with(2.5)
        mock_logger.warning.assert_any_call(
            '429 rate limit. Retrying in 2.5s. Error: HTTP 429: {"retryDelay":"2.5s"}...'
        )

    @pytest.mark.asyncio
    async def test_should_use_exponential_backoff_for_non_429_errors(self):
        """Should use exponential backoff for non-429 errors."""
        # Arrange
        error = Exception("Network error")
        mock_func = AsyncMock(side_effect=[error, "success"])
        mock_logger = Mock()

        # Act
        with (
            patch("asyncio.sleep") as mock_sleep,
            patch("random.uniform", return_value=0.1),
        ):  # Mock jitter
            result = await retry_with_simple_backoff(
                mock_func, max_retries=3, base_delay=1.0, logger_instance=mock_logger
            )

        # Assert
        assert result == "success"
        # For attempt=0: delay = 1.0 * (2 ** 0) = 1.0, jitter = 0.1, total = 1.1
        mock_sleep.assert_called_with(1.1)

    @pytest.mark.asyncio
    async def test_should_raise_exception_after_max_retries(self):
        """Should raise exception after max retries exceeded."""
        # Arrange
        error = Exception("Persistent error")
        mock_func = AsyncMock(side_effect=error)
        mock_logger = Mock()

        # Act & Assert
        with patch("asyncio.sleep"):
            with pytest.raises(Exception, match="Persistent error"):
                await retry_with_simple_backoff(
                    mock_func, max_retries=2, logger_instance=mock_logger
                )

        assert mock_func.call_count == 3  # Initial + 2 retries
        mock_logger.error.assert_called_with(
            "Max retries (2) exceeded. Last error: Persistent error..."
        )

    @pytest.mark.asyncio
    async def test_should_work_without_logger(self):
        """Should work correctly without logger instance."""
        # Arrange
        mock_func = AsyncMock(return_value="success")

        # Act
        result = await retry_with_simple_backoff(mock_func, max_retries=3)

        # Assert
        assert result == "success"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_truncate_long_error_messages(self):
        """Should truncate very long error messages in logs."""
        # Arrange
        long_error = Exception("A" * 300)  # 300 character error message
        mock_func = AsyncMock(side_effect=[long_error, "success"])
        mock_logger = Mock()

        # Act
        with patch("asyncio.sleep"):
            result = await retry_with_simple_backoff(
                mock_func, max_retries=3, logger_instance=mock_logger
            )

        # Assert
        assert result == "success"
        # Check that logged error message was truncated (look for warning calls with "Error on attempt")
        warning_calls = [
            call for call in mock_logger.warning.call_args_list if "Error on attempt" in str(call)
        ]
        assert len(warning_calls) > 0
        logged_message = str(warning_calls[0])
        # Should contain truncated message with "..."
        assert "..." in logged_message


class TestEnhancedRunner:
    """Test enhanced runner creation and functionality."""

    def test_should_create_enhanced_runner(self):
        """Should create enhanced runner with proper configuration."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()

        # Act
        with patch("google.adk.Runner", Mock()) as mock_runner_class:
            runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service,
                max_retries=5,
                base_delay=2.0,
            )

        # Assert
        assert runner is not None
        assert hasattr(runner, "run_async")
        assert runner._max_retries == 5
        assert runner._base_delay == 2.0

    @pytest.mark.asyncio
    async def test_enhanced_runner_should_delegate_to_retry_logic(self):
        """Enhanced runner should delegate to retry logic with proper parameters."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()
        mock_events = ["event1", "event2"]

        mock_original_runner = Mock()

        # Mock the async generator
        async def mock_run_async(*args, **kwargs):
            for event in mock_events:
                yield event

        mock_original_runner.run_async = mock_run_async

        with patch("google.adk.Runner", return_value=mock_original_runner) as mock_runner_class:
            runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service,
                max_retries=3,
                base_delay=1.5,
            )

        # Act
        collected_events = []
        async for event in runner.run_async("user1", "session1", "message"):
            collected_events.append(event)

        # Assert
        assert collected_events == mock_events

    def test_should_use_default_parameters(self):
        """Should use default parameters when none provided."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()

        # Act
        with patch("google.adk.Runner", Mock()) as mock_runner_class:
            runner = create_enhanced_runner(
                agent=mock_agent, app_name="test_app", session_service=mock_session_service
            )  # No optional parameters

        # Assert
        assert runner is not None
        assert runner._max_retries == 3  # Default
        assert runner._base_delay == 2.0  # Default
