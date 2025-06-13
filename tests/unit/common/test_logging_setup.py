"""Tests for logging setup functionality."""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from common.logging_setup import (
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_FILENAME_FORMAT,
    DEFAULT_LOG_MAX_BYTES,
    LoggerWriter,
    setup_logging,
)


class TestLoggingSetup:
    """Test logging setup functionality and file operations."""

    def test_should_setup_logging_with_default_values(self, temp_dir):
        """Should setup logging with default values."""
        # Arrange & Act
        logger = setup_logging("test_app", log_dir=temp_dir)

        # Assert
        assert logger.level == logging.INFO
        assert logger.name == "test_app"
        assert len(logger.handlers) >= 2  # File and console handlers

    def test_should_setup_logging_with_custom_values(self, temp_dir):
        """Should setup logging with custom values."""
        # Arrange
        custom_format = "test_%Y%m%d.log"
        custom_max_bytes = 5 * 1024 * 1024  # 5MB
        custom_backup_count = 3

        # Act
        logger = setup_logging(
            app_name="custom_app",
            log_filename_format=custom_format,
            log_max_bytes=custom_max_bytes,
            log_backup_count=custom_backup_count,
            log_dir=temp_dir,
        )

        # Assert
        assert logger.name == "custom_app"
        assert len(logger.handlers) >= 2

    def test_should_create_log_directory_if_not_exists(self, temp_dir):
        """Should create log directory if it doesn't exist."""
        # Arrange
        log_dir = os.path.join(temp_dir, "logs", "subdir")

        # Act
        logger = setup_logging("test_app", log_dir=log_dir)

        # Assert
        assert os.path.exists(log_dir)
        assert logger is not None

    def test_should_handle_existing_log_directory(self, temp_dir):
        """Should handle existing log directory without error."""
        # Arrange
        log_dir = os.path.join(temp_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        # Act
        logger = setup_logging("test_app", log_dir=log_dir)

        # Assert
        assert logger is not None
        assert os.path.exists(log_dir)

    @pytest.mark.parametrize(
        "message_content,should_have_content",
        [
            ("Test message", True),
            ("测试 unicode content 🚀 café", True),  # Unicode
            ("A" * 10000, True),  # Very long message
        ],
    )
    def test_should_write_various_log_messages_to_file(
        self, temp_dir, message_content, should_have_content
    ):
        """Should write various types of log messages to file."""
        # Arrange
        logger = setup_logging("test_app", log_dir=temp_dir, redirect_stdout=False)

        # Act
        logger.info(message_content)
        logger.warning("Warning: " + message_content[:50])  # Truncate for very long messages

        # Assert
        # Force flush
        for handler in logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        # Check that log files were created
        log_files = [f for f in os.listdir(temp_dir) if f.endswith(".log")]
        assert len(log_files) > 0

        # Check content
        log_file_path = os.path.join(temp_dir, log_files[0])
        with open(log_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if should_have_content:
                assert message_content[:100] in content  # Check first 100 chars for long messages


class TestLoggerWriter:
    """Test LoggerWriter functionality for stdout/stderr redirection."""

    @pytest.mark.parametrize(
        "input_message,expected_calls",
        [
            ("Test message\n", 1),  # Normal message
            ("   \n\t  ", 0),  # Whitespace only
            ("", 0),  # Empty message
            ("  Message with spaces  \n", 1),  # Message with trailing spaces
        ],
    )
    def test_should_handle_various_write_scenarios(self, input_message, expected_calls):
        """Should handle various write scenarios correctly."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)

        # Act
        writer.write(input_message)

        # Assert
        assert mock_writer.call_count == expected_calls
        if expected_calls > 0:
            # Verify the message was stripped
            called_message = mock_writer.call_args[0][0]
            assert not called_message.endswith("\n")
            assert not called_message.endswith(" ")

    def test_should_create_logger_writer_with_function(self):
        """Should create LoggerWriter with a writer function."""
        # Arrange
        mock_writer = Mock()

        # Act
        writer = LoggerWriter(mock_writer)

        # Assert
        assert writer.writer_func == mock_writer
        assert writer.buffer == ""

    def test_flush_should_not_raise_error(self):
        """Should handle flush gracefully without raising errors."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)

        # Act & Assert
        writer.flush()  # Should not raise


class TestLoggingConfiguration:
    """Test logging configuration and advanced features."""

    def test_should_use_default_constants(self):
        """Should use correct default constants."""
        # Assert
        assert DEFAULT_LOG_FILENAME_FORMAT == "application_%Y%m%d_%H%M%S.log"
        assert DEFAULT_LOG_MAX_BYTES == 10 * 1024 * 1024  # 10MB
        assert DEFAULT_LOG_BACKUP_COUNT == 5

    def test_should_clear_existing_handlers(self, temp_dir):
        """Should clear existing handlers when setting up new logger."""
        # Arrange
        # First setup
        logger1 = setup_logging("test_app", log_dir=temp_dir)
        initial_handler_count = len(logger1.handlers)

        # Act - Second setup with same name
        logger2 = setup_logging("test_app", log_dir=temp_dir)

        # Assert
        assert logger1 is logger2  # Same logger instance
        # Should not have accumulated handlers
        assert len(logger2.handlers) == initial_handler_count

    @patch("common.logging_setup.datetime")
    def test_should_use_timestamped_log_filename(self, mock_datetime, temp_dir):
        """Should use timestamped log filename."""
        # Arrange
        mock_now = Mock()
        mock_now.strftime.return_value = "test_20240101_120000.log"
        mock_datetime.datetime.now.return_value = mock_now

        # Act
        logger = setup_logging("test_app", log_dir=temp_dir)

        # Assert
        mock_datetime.datetime.now.assert_called()
        # Verify that strftime was called with some format containing timestamp patterns
        mock_now.strftime.assert_called_once()
        call_args = mock_now.strftime.call_args[0][0]
        assert "%Y" in call_args and "%m" in call_args and "%d" in call_args

    @pytest.mark.parametrize(
        "redirect_stdout,should_redirect",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_should_handle_stdout_redirection_options(
        self, temp_dir, redirect_stdout, should_redirect
    ):
        """Should handle stdout redirection options correctly."""
        # Arrange
        original_stdout = sys.stdout

        # Act
        logger = setup_logging("test_app", log_dir=temp_dir, redirect_stdout=redirect_stdout)

        # Assert
        if should_redirect:
            assert sys.stdout != original_stdout
            assert isinstance(sys.stdout, LoggerWriter)
        else:
            assert sys.stdout == original_stdout

        # Cleanup - restore original stdout
        sys.stdout = original_stdout
