"""Generic logging configuration for multiple applications."""

import datetime
import logging
import logging.handlers
import os
import sys
import threading

# Default configuration values
DEFAULT_LOG_FILENAME_FORMAT = "application_%Y%m%d_%H%M%S.log"
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_LOG_BACKUP_COUNT = 5


class LoggerWriter:
    """File-like object to redirect stdout/stderr to logger.

    This class prevents infinite recursion when logging by using a thread-local guard.
    """

    _recursion_guard = threading.local()

    def __init__(self, writer_func):
        self.writer_func = writer_func
        self.buffer = ""

    def write(self, message):
        # Prevent recursion by checking thread-local guard
        if not hasattr(self._recursion_guard, "in_write"):
            self._recursion_guard.in_write = False

        if self._recursion_guard.in_write:
            # We're already in a write operation, so write directly to original stdout
            # to avoid recursion
            orig_stdout = getattr(sys, "_original_stdout", None)
            if orig_stdout is not None:
                orig_stdout.write(message)
            return

        try:
            self._recursion_guard.in_write = True
            if message and not message.isspace():
                self.writer_func(message.rstrip())
        finally:
            self._recursion_guard.in_write = False

    def flush(self):
        pass

    def isatty(self):
        """Return False since we're not a terminal. Required for Uvicorn compatibility."""
        return False

    def fileno(self):
        """Return a fake file descriptor. Required for some logging libraries."""
        return -1


def setup_logging(
    app_name="application",
    log_filename_format=None,
    log_max_bytes=None,
    log_backup_count=None,
    log_dir=None,
    redirect_stdout=True,
):
    """Set up logging to file and console with proper formatting.

    Args:
        app_name: Name of the application for the logger
        log_filename_format: Format string for log filenames
        log_max_bytes: Maximum size of log files before rotation
        log_backup_count: Number of backup log files to keep
        log_dir: Directory to store log files (defaults to ../logs from this file)
        redirect_stdout: Whether to redirect stdout/stderr to logger

    Returns:
        logging.Logger: Configured logger instance
    """
    # Use provided values or try to import from cursor_prompt_preprocessor, then fall back to defaults
    if log_filename_format is None:
        try:
            from cursor_prompt_preprocessor.config import LOG_FILENAME_FORMAT

            log_filename_format = LOG_FILENAME_FORMAT
        except ImportError:
            log_filename_format = DEFAULT_LOG_FILENAME_FORMAT

    if log_max_bytes is None:
        try:
            from cursor_prompt_preprocessor.config import LOG_MAX_BYTES

            log_max_bytes = LOG_MAX_BYTES
        except ImportError:
            log_max_bytes = DEFAULT_LOG_MAX_BYTES

    if log_backup_count is None:
        try:
            from cursor_prompt_preprocessor.config import LOG_BACKUP_COUNT

            log_backup_count = LOG_BACKUP_COUNT
        except ImportError:
            log_backup_count = DEFAULT_LOG_BACKUP_COUNT

    # Create logs directory if it doesn't exist
    if log_dir is None:
        # Default to ../logs from this file
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Create timestamped log file path
    log_file = os.path.join(log_dir, datetime.datetime.now().strftime(log_filename_format))

    # Create a logger specific to the app
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)

    # Clear any existing handlers (helpful when reloading in development)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # Create formatters
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    console_formatter = logging.Formatter("%(message)s")

    # File handler for detailed logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=log_max_bytes, backupCount=log_backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Console handler for regular output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    if redirect_stdout:
        # Save original stdout/stderr before redirecting
        if not hasattr(sys, "_original_stdout"):
            sys._original_stdout = sys.stdout
        if not hasattr(sys, "_original_stderr"):
            sys._original_stderr = sys.stderr

        # Redirect stdout and stderr to the logger
        sys.stdout = LoggerWriter(logger.info)
        sys.stderr = LoggerWriter(logger.error)

    logger.info(f"Logging initialized for {app_name}. Log file: {log_file}")
    return logger


# For backward compatibility with existing code that expects a global logger
# This uses cursor_prompt_preprocessor configuration if available
logger = setup_logging("cursor_prompt_preprocessor")
