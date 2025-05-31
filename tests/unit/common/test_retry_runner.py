"""Tests for retry runner functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, call
from typing import Any

from common.retry_runner import (
    extract_retry_delay,
    is_429_error,
    retry_with_simple_backoff,
    create_enhanced_runner
)


class TestRetryDelayExtraction:
    """Test retry delay extraction from error messages."""
    
    def test_should_extract_delay_from_quoted_json_format(self):
        """Should extract delay from quoted JSON format."""
        # Arrange
        error_content = 'API Error: {"retryDelay":"3.5s","status":"RESOURCE_EXHAUSTED"}'
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 3.5
    
    def test_should_extract_delay_from_unquoted_format(self):
        """Should extract delay from unquoted format."""
        # Arrange
        error_content = "Rate limit exceeded: retryDelay: 7.2"
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 7.2
    
    def test_should_extract_delay_from_retry_after_header(self):
        """Should extract delay from Retry-After header format."""
        # Arrange
        error_content = "HTTP 429: Retry-After: 10"
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 10.0
    
    def test_should_handle_case_insensitive_retry_after(self):
        """Should handle case-insensitive Retry-After header."""
        # Arrange
        error_content = "HTTP 429: retry-after: 15"
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 15.0
    
    def test_should_return_default_delay_when_no_pattern_matches(self):
        """Should return default delay when no pattern matches."""
        # Arrange
        error_content = "Some generic error message"
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 5.0  # Default delay
    
    def test_should_handle_single_quoted_format(self):
        """Should handle single-quoted JSON format."""
        # Arrange
        error_content = "Error: {'retryDelay':'2.8s'}"
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 2.8
    
    def test_should_handle_malformed_delay_gracefully(self):
        """Should handle malformed delay values gracefully."""
        # Arrange
        error_content = 'Error: {"retryDelay":"invalid"}'
        
        # Act
        result = extract_retry_delay(error_content)
        
        # Assert
        assert result == 5.0  # Should return default


class TestErrorTypeDetection:
    """Test 429 error detection functionality."""
    
    def test_should_detect_429_error_code(self):
        """Should detect 429 error code."""
        # Arrange
        error = Exception("HTTP 429: Too Many Requests")
        
        # Act
        is_429, content = is_429_error(error)
        
        # Assert
        assert is_429 is True
        assert "429" in content
    
    def test_should_detect_resource_exhausted_error(self):
        """Should detect RESOURCE_EXHAUSTED error."""
        # Arrange
        error = Exception("RESOURCE_EXHAUSTED: Rate limit exceeded")
        
        # Act
        is_429, content = is_429_error(error)
        
        # Assert
        assert is_429 is True
        assert "RESOURCE_EXHAUSTED" in content
    
    def test_should_detect_lowercase_resource_exhausted(self):
        """Should detect lowercase resource_exhausted error."""
        # Arrange
        error = Exception("gRPC error: resource_exhausted")
        
        # Act
        is_429, content = is_429_error(error)
        
        # Assert
        assert is_429 is True
        assert "resource_exhausted" in content
    
    def test_should_not_detect_non_429_error(self):
        """Should not detect non-429 errors."""
        # Arrange
        error = Exception("Network timeout error")
        
        # Act
        is_429, content = is_429_error(error)
        
        # Assert
        assert is_429 is False
        assert "Network timeout error" in content
    
    def test_should_return_error_content(self):
        """Should return the error content string."""
        # Arrange
        error_message = "Detailed error information"
        error = ValueError(error_message)
        
        # Act
        is_429, content = is_429_error(error)
        
        # Assert
        assert content == error_message


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
        with patch('asyncio.sleep') as mock_sleep:
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
        error_429 = Exception('Rate limit: 429 {"retryDelay":"3.0s"}')  # Make sure 429 is detected
        mock_func = AsyncMock(side_effect=[error_429, "success"])
        mock_logger = Mock()
        
        # Act
        with patch('asyncio.sleep') as mock_sleep:
            result = await retry_with_simple_backoff(
                mock_func, max_retries=2, logger_instance=mock_logger
            )
        
        # Assert
        assert result == "success"
        mock_sleep.assert_called_with(3.0)  # API-specified delay, no jitter for 429
        mock_logger.warning.assert_any_call(
            "429 rate limit. Retrying in 3.0s. Error: Rate limit: 429 {\"retryDelay\":\"3.0s\"}..."
        )
    
    @pytest.mark.asyncio
    async def test_should_use_exponential_backoff_for_non_429_errors(self):
        """Should use exponential backoff for non-429 errors."""
        # Arrange
        error = Exception("Network error")
        mock_func = AsyncMock(side_effect=[error, error, "success"])
        mock_logger = Mock()
        
        # Act
        with patch('asyncio.sleep') as mock_sleep, \
             patch('random.uniform', return_value=0.1):  # Mock jitter
            result = await retry_with_simple_backoff(
                mock_func, max_retries=3, base_delay=2.0, logger_instance=mock_logger
            )
        
        # Assert
        assert result == "success"
        # First retry: 2.0 * 2^0 + jitter = 2.1
        # Second retry: 2.0 * 2^1 + jitter = 4.1
        expected_calls = [call(2.1), call(4.1)]
        mock_sleep.assert_has_calls(expected_calls)
    
    @pytest.mark.asyncio
    async def test_should_raise_exception_after_max_retries(self):
        """Should raise the last exception after max retries."""
        # Arrange
        error = Exception("Persistent error")
        mock_func = AsyncMock(side_effect=error)
        mock_logger = Mock()
        
        # Act & Assert
        with patch('asyncio.sleep'), \
             pytest.raises(Exception, match="Persistent error"):
            await retry_with_simple_backoff(
                mock_func, max_retries=2, logger_instance=mock_logger
            )
        
        assert mock_func.call_count == 3  # Initial + 2 retries
        mock_logger.error.assert_called_with(
            "Max retries (2) exceeded. Last error: Persistent error..."
        )
    
    @pytest.mark.asyncio
    async def test_should_work_without_logger(self):
        """Should work without logger instance."""
        # Arrange
        mock_func = AsyncMock(side_effect=[Exception("error"), "success"])
        
        # Act
        with patch('asyncio.sleep'):
            result = await retry_with_simple_backoff(mock_func, max_retries=2)
        
        # Assert
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_should_truncate_long_error_messages(self):
        """Should truncate very long error messages in logs."""
        # Arrange
        long_error = "x" * 200  # Error longer than 100 chars
        error = Exception(long_error)
        mock_func = AsyncMock(side_effect=error)
        mock_logger = Mock()
        
        # Act & Assert
        with patch('asyncio.sleep'), \
             pytest.raises(Exception):
            await retry_with_simple_backoff(
                mock_func, max_retries=1, logger_instance=mock_logger
            )
        
        # Should truncate error message to 100 chars + "..."
        logged_message = mock_logger.warning.call_args[0][0]
        assert "..." in logged_message
        assert len(logged_message.split("Error: ")[1]) <= 103  # 100 + "..."
    
    @pytest.mark.asyncio
    async def test_should_pass_function_arguments_correctly(self):
        """Should pass function arguments and kwargs correctly."""
        # Arrange
        mock_func = AsyncMock(return_value="success")
        
        # Act
        result = await retry_with_simple_backoff(
            mock_func, 1, 2.0, None, "arg1", "arg2", kwarg1="value1", kwarg2="value2"
        )
        
        # Assert
        assert result == "success"
        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1", kwarg2="value2")


class TestEnhancedRunner:
    """Test enhanced runner creation and functionality."""
    
    def test_should_create_enhanced_runner(self):
        """Should create enhanced runner with proper configuration."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()
        mock_logger = Mock()
        
        # Mock the google.adk.runner.Runner import
        with patch('builtins.__import__') as mock_import:
            mock_runner_module = Mock()
            mock_runner_class = Mock()
            mock_original_runner = Mock()
            
            mock_runner_module.Runner = mock_runner_class
            mock_runner_class.return_value = mock_original_runner
            
            def import_side_effect(name, *args, **kwargs):
                if name == 'google.adk.runner':
                    return mock_runner_module
                # Call the real import for other modules
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Act
            enhanced_runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service,
                max_retries=5,
                base_delay=3.0,
                logger_instance=mock_logger
            )
        
        # Assert
        mock_runner_class.assert_called_once_with(
            agent=mock_agent,
            app_name="test_app", 
            session_service=mock_session_service
        )
        assert enhanced_runner._original_runner == mock_original_runner
        assert enhanced_runner._max_retries == 5
        assert enhanced_runner._base_delay == 3.0
        assert enhanced_runner._logger == mock_logger
    
    @pytest.mark.asyncio
    async def test_enhanced_runner_should_run_with_retry_logic(self):
        """Enhanced runner should execute with retry logic."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()
        mock_logger = Mock()
        
        # Mock the events that would be yielded
        mock_events = ["event1", "event2", "event3"]
        
        # Mock the google.adk.runner.Runner import
        with patch('builtins.__import__') as mock_import:
            mock_runner_module = Mock()
            mock_runner_class = Mock()
            mock_original_runner = Mock()
            
            mock_runner_module.Runner = mock_runner_class
            mock_runner_class.return_value = mock_original_runner
            
            def import_side_effect(name, *args, **kwargs):
                if name == 'google.adk.runner':
                    return mock_runner_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Mock the async generator
            async def mock_run_async(*args, **kwargs):
                for event in mock_events:
                    yield event
            
            mock_original_runner.run_async = mock_run_async
            
            enhanced_runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service,
                max_retries=3,
                logger_instance=mock_logger
            )
            
            # Act
            collected_events = []
            async for event in enhanced_runner.run_async("user123", "session456", "test message"):
                collected_events.append(event)
        
        # Assert
        assert collected_events == mock_events
    
    def test_enhanced_runner_should_delegate_other_attributes(self):
        """Enhanced runner should delegate other attributes to original runner."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()
        
        # Mock the google.adk.runner.Runner import
        with patch('builtins.__import__') as mock_import:
            mock_runner_module = Mock()
            mock_runner_class = Mock()
            mock_original_runner = Mock()
            
            mock_runner_module.Runner = mock_runner_class
            mock_runner_class.return_value = mock_original_runner
            
            def import_side_effect(name, *args, **kwargs):
                if name == 'google.adk.runner':
                    return mock_runner_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            mock_original_runner.some_attribute = "test_value"
            mock_original_runner.some_method.return_value = "method_result"
            
            enhanced_runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service
            )
            
            # Act & Assert
            assert enhanced_runner.some_attribute == "test_value"
            assert enhanced_runner.some_method() == "method_result"
            mock_original_runner.some_method.assert_called_once()
    
    def test_should_use_default_parameters(self):
        """Should use default parameters when not specified."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()
        
        # Mock the google.adk.runner.Runner import
        with patch('builtins.__import__') as mock_import:
            mock_runner_module = Mock()
            mock_runner_class = Mock()
            mock_original_runner = Mock()
            
            mock_runner_module.Runner = mock_runner_class
            mock_runner_class.return_value = mock_original_runner
            
            def import_side_effect(name, *args, **kwargs):
                if name == 'google.adk.runner':
                    return mock_runner_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Act
            enhanced_runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service
            )
        
        # Assert
        assert enhanced_runner._max_retries == 3  # Default
        assert enhanced_runner._base_delay == 2.0  # Default
        assert enhanced_runner._logger is None  # Default
    
    @patch('common.retry_runner.retry_with_simple_backoff')
    @pytest.mark.asyncio
    async def test_enhanced_runner_should_handle_retries_on_failure(self, mock_retry_func):
        """Enhanced runner should handle retries when original runner fails."""
        # Arrange
        mock_agent = Mock()
        mock_session_service = Mock()
        mock_logger = Mock()
        
        # Mock events for successful retry
        mock_events = ["event1", "event2"]
        
        # Mock the google.adk.runner.Runner import
        with patch('builtins.__import__') as mock_import:
            mock_runner_module = Mock()
            mock_runner_class = Mock() 
            mock_original_runner = Mock()
            
            mock_runner_module.Runner = mock_runner_class
            mock_runner_class.return_value = mock_original_runner
            
            def import_side_effect(name, *args, **kwargs):
                if name == 'google.adk.runner':
                    return mock_runner_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Mock retry function to return events
            mock_retry_func.return_value = mock_events
            
            enhanced_runner = create_enhanced_runner(
                agent=mock_agent,
                app_name="test_app",
                session_service=mock_session_service,
                max_retries=2,
                logger_instance=mock_logger
            )
            
            # Act
            collected_events = []
            async for event in enhanced_runner.run_async("user123", "session456", "test message"):
                collected_events.append(event)
        
        # Assert
        assert collected_events == mock_events
        mock_retry_func.assert_called_once()
        # Verify the retry function was called with correct parameters
        call_args = mock_retry_func.call_args
        assert call_args[0][1] == 2  # max_retries
        assert call_args[0][2] == 2.0  # base_delay (default)
        assert call_args[0][3] == mock_logger  # logger 