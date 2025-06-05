"""Tests for cursor_prompt_preprocessor.config module.

This module tests the configuration constants and settings used by the
cursor prompt preprocessor agents.
"""

import pytest

from cursor_prompt_preprocessor.config import (
    APP_NAME,
    GEMINI_MODEL,
    LOG_BACKUP_COUNT,
    LOG_FILENAME_FORMAT,
    LOG_MAX_BYTES,
    RATE_LIMIT_MAX_CALLS,
    RATE_LIMIT_WINDOW,
    SESSION_ID,
    USER_ID,
)


class TestApplicationConfiguration:
    """Test critical application configuration values."""

    def test_given_app_configuration_when_checking_identifiers_then_all_required_values_are_present(
        self,
    ):
        """Given application configuration, when checking identifiers, then app name, user ID, and session ID are all non-empty strings."""
        # Arrange & Act & Assert
        assert isinstance(APP_NAME, str) and len(APP_NAME) > 0
        assert isinstance(USER_ID, str) and len(USER_ID) > 0
        assert isinstance(SESSION_ID, str) and len(SESSION_ID) > 0

    def test_given_gemini_model_config_when_validating_model_name_then_it_contains_gemini_identifier(
        self,
    ):
        """Given Gemini model configuration, when validating model name, then it contains 'gemini' and follows expected naming pattern."""
        # Arrange & Act & Assert
        assert isinstance(GEMINI_MODEL, str)
        assert "gemini" in GEMINI_MODEL.lower()
        assert len(GEMINI_MODEL) > 10  # Reasonable length for model identifier


class TestRateLimitingConfiguration:
    """Test rate limiting configuration for API safety."""

    def test_given_rate_limit_settings_when_validating_constraints_then_they_prevent_api_abuse(
        self,
    ):
        """Given rate limit settings, when validating constraints, then max calls and window are positive integers that prevent API abuse."""
        # Arrange & Act & Assert
        assert isinstance(RATE_LIMIT_MAX_CALLS, int) and RATE_LIMIT_MAX_CALLS > 0
        assert isinstance(RATE_LIMIT_WINDOW, int) and RATE_LIMIT_WINDOW > 0
        # Ensure reasonable limits (not too permissive)
        assert RATE_LIMIT_MAX_CALLS <= 100  # Prevent abuse
        assert RATE_LIMIT_WINDOW >= 10  # Reasonable window


class TestLoggingConfiguration:
    """Test logging configuration for operational monitoring."""

    def test_given_log_filename_format_when_creating_log_files_then_format_includes_all_required_timestamp_components(
        self,
    ):
        """Given log filename format, when creating log files, then format includes year, month, day, hour, minute, second, and .log extension."""
        # Arrange
        required_components = ["%Y", "%m", "%d", "%H", "%M", "%S", ".log"]

        # Act & Assert
        assert isinstance(LOG_FILENAME_FORMAT, str)
        for component in required_components:
            assert (
                component in LOG_FILENAME_FORMAT
            ), f"Missing required timestamp component: {component}"

    def test_given_log_rotation_settings_when_managing_log_files_then_size_and_backup_limits_are_reasonable(
        self,
    ):
        """Given log rotation settings, when managing log files, then size limit prevents disk overflow and backup count maintains history."""
        # Arrange & Act & Assert
        assert isinstance(LOG_MAX_BYTES, int) and LOG_MAX_BYTES > 0
        assert isinstance(LOG_BACKUP_COUNT, int) and LOG_BACKUP_COUNT > 0
        # Ensure reasonable limits
        assert LOG_MAX_BYTES >= 1024 * 1024  # At least 1MB
        assert LOG_MAX_BYTES <= 100 * 1024 * 1024  # Not more than 100MB
        assert LOG_BACKUP_COUNT <= 50  # Reasonable backup count
