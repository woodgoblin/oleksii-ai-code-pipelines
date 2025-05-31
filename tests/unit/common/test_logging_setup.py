"""Tests for logging setup functionality."""

import pytest
import logging
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, call

from common.logging_setup import (
    setup_logging,
    LoggerWriter,
    DEFAULT_LOG_FILENAME_FORMAT,
    DEFAULT_LOG_MAX_BYTES,
    DEFAULT_LOG_BACKUP_COUNT
)


class TestLoggingSetup:
    """Test basic logging setup functionality."""
    
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
            log_dir=temp_dir
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


class TestLoggingFileOperations:
    """Test logging file operations and rotation."""
    
    def test_should_write_log_messages_to_file(self, temp_dir):
        """Should write log messages to file."""
        # Arrange
        logger = setup_logging("test_app", log_dir=temp_dir, redirect_stdout=False)
        
        # Act
        logger.info("Test message")
        logger.warning("Warning message")
        
        # Assert
        # Force flush
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        # Check that log files were created
        log_files = [f for f in os.listdir(temp_dir) if f.endswith('.log')]
        assert len(log_files) > 0
        
        # Check content
        log_file_path = os.path.join(temp_dir, log_files[0])
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "Test message" in content
            assert "Warning message" in content
    
    def test_should_handle_unicode_characters_in_logs(self, temp_dir):
        """Should handle unicode characters in log messages."""
        # Arrange
        logger = setup_logging("unicode_app", log_dir=temp_dir, redirect_stdout=False)
        
        # Act
        unicode_message = "Test with unicode: 测试 🚀 café"
        logger.info(unicode_message)
        
        # Assert
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        log_files = [f for f in os.listdir(temp_dir) if f.endswith('.log')]
        assert len(log_files) > 0
        
        log_file_path = os.path.join(temp_dir, log_files[0])
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert unicode_message in content
    
    def test_should_handle_very_long_log_messages(self, temp_dir):
        """Should handle very long log messages without error."""
        # Arrange
        logger = setup_logging("long_app", log_dir=temp_dir, redirect_stdout=False)
        long_message = "A" * 10000  # 10KB message
        
        # Act
        logger.info(long_message)
        
        # Assert
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        
        log_files = [f for f in os.listdir(temp_dir) if f.endswith('.log')]
        assert len(log_files) > 0


class TestLoggerWriter:
    """Test LoggerWriter functionality for stdout/stderr redirection."""
    
    def test_should_create_logger_writer_with_function(self):
        """Should create LoggerWriter with a writer function."""
        # Arrange
        mock_writer = Mock()
        
        # Act
        writer = LoggerWriter(mock_writer)
        
        # Assert
        assert writer.writer_func == mock_writer
        assert writer.buffer == ''
    
    def test_should_write_non_empty_messages(self):
        """Should write non-empty messages to the writer function."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)
        
        # Act
        writer.write("Test message\n")
        
        # Assert
        mock_writer.assert_called_once_with("Test message")
    
    def test_should_ignore_whitespace_only_messages(self):
        """Should ignore whitespace-only messages."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)
        
        # Act
        writer.write("   \n\t  ")
        
        # Assert
        mock_writer.assert_not_called()
    
    def test_should_handle_empty_messages(self):
        """Should handle empty messages gracefully."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)
        
        # Act
        writer.write("")
        
        # Assert
        mock_writer.assert_not_called()
    
    def test_should_strip_trailing_whitespace(self):
        """Should strip trailing whitespace from messages."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)
        
        # Act
        writer.write("Test message   \n\t")
        
        # Assert
        mock_writer.assert_called_once_with("Test message")
    
    def test_flush_should_not_raise_error(self):
        """Flush method should not raise any errors."""
        # Arrange
        mock_writer = Mock()
        writer = LoggerWriter(mock_writer)
        
        # Act & Assert
        writer.flush()  # Should not raise


class TestLoggingRedirection:
    """Test stdout/stderr redirection functionality."""
    
    def test_should_redirect_stdout_when_enabled(self, temp_dir):
        """Should redirect stdout when redirect_stdout is True."""
        # Arrange
        original_stdout = sys.stdout
        
        # Act
        logger = setup_logging("redirect_app", log_dir=temp_dir, redirect_stdout=True)
        
        # Assert
        assert sys.stdout != original_stdout
        assert isinstance(sys.stdout, LoggerWriter)
        
        # Cleanup - restore original stdout for other tests
        sys.stdout = original_stdout
    
    def test_should_not_redirect_stdout_when_disabled(self, temp_dir):
        """Should not redirect stdout when redirect_stdout is False."""
        # Arrange
        original_stdout = sys.stdout
        
        # Act
        logger = setup_logging("no_redirect_app", log_dir=temp_dir, redirect_stdout=False)
        
        # Assert
        assert sys.stdout == original_stdout
    
    def test_should_preserve_original_stdout_reference(self, temp_dir):
        """Should preserve original stdout reference."""
        # Arrange
        original_stdout = sys.stdout
        
        # Act
        logger = setup_logging("preserve_app", log_dir=temp_dir, redirect_stdout=True)
        
        # Assert
        assert hasattr(sys, '_original_stdout')
        assert sys._original_stdout == original_stdout
        
        # Cleanup
        sys.stdout = original_stdout


class TestLoggingConfiguration:
    """Test logging configuration and defaults."""
    
    def test_should_use_default_constants(self):
        """Should have proper default constants defined."""
        # Arrange & Act & Assert
        assert DEFAULT_LOG_FILENAME_FORMAT == "application_%Y%m%d_%H%M%S.log"
        assert DEFAULT_LOG_MAX_BYTES == 10 * 1024 * 1024  # 10MB
        assert DEFAULT_LOG_BACKUP_COUNT == 5
    
    def test_should_clear_existing_handlers(self, temp_dir):
        """Should clear existing handlers when setting up logger again."""
        # Arrange
        logger_name = "handler_test"
        
        # Act
        logger1 = setup_logging(logger_name, log_dir=temp_dir, redirect_stdout=False)
        initial_handler_count = len(logger1.handlers)
        
        logger2 = setup_logging(logger_name, log_dir=temp_dir, redirect_stdout=False)
        final_handler_count = len(logger2.handlers)
        
        # Assert
        assert logger1.name == logger2.name
        assert final_handler_count == initial_handler_count  # Should not accumulate handlers
    
    @patch('common.logging_setup.datetime')
    def test_should_use_timestamped_log_filename(self, mock_datetime, temp_dir):
        """Should create timestamped log filenames."""
        # Arrange
        mock_now = Mock()
        mock_now.strftime.return_value = "test_20240101_120000.log"
        mock_datetime.datetime.now.return_value = mock_now
        
        # Act
        logger = setup_logging("timestamp_app", log_dir=temp_dir, redirect_stdout=False)
        
        # Assert
        mock_datetime.datetime.now.assert_called_once()
        # The implementation tries to import format from cursor_prompt_preprocessor.config first
        # and falls back to the default if import fails, so we just verify strftime was called
        mock_now.strftime.assert_called_once()
        # Verify the call was made with some timestamp format
        call_args = mock_now.strftime.call_args[0][0]
        assert '%Y' in call_args and '%m' in call_args and '%d' in call_args 