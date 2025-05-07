"""Logging configuration for Cursor Prompt Preprocessor."""

import os
import sys
import logging
import logging.handlers
import datetime
import threading
from cursor_prompt_preprocessor.config import LOG_FILENAME_FORMAT, LOG_MAX_BYTES, LOG_BACKUP_COUNT

class LoggerWriter:
    """File-like object to redirect stdout/stderr to logger.
    
    This class prevents infinite recursion when logging by using a thread-local guard.
    """
    _recursion_guard = threading.local()
    
    def __init__(self, writer_func):
        self.writer_func = writer_func
        self.buffer = ''
        
    def write(self, message):
        # Prevent recursion by checking thread-local guard
        if not hasattr(self._recursion_guard, 'in_write'):
            self._recursion_guard.in_write = False
        
        if self._recursion_guard.in_write:
            # We're already in a write operation, so write directly to original stdout
            # to avoid recursion
            orig_stdout = getattr(sys, '_original_stdout', None)
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

def setup_logging():
    """Set up logging to file and console with proper formatting.
    
    Creates a logger that writes to both a rotating file and the console.
    Redirects stdout and stderr to the logger to capture all output.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Create timestamped log file path
    log_file = os.path.join(log_dir, datetime.datetime.now().strftime(LOG_FILENAME_FORMAT))
    
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers (helpful when reloading in development)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')
    
    # File handler for detailed logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    # Console handler for regular output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # Save original stdout/stderr before redirecting
    if not hasattr(sys, '_original_stdout'):
        sys._original_stdout = sys.stdout
    if not hasattr(sys, '_original_stderr'):
        sys._original_stderr = sys.stderr
    
    # Redirect stdout and stderr to the logger
    sys.stdout = LoggerWriter(logger.info)
    sys.stderr = LoggerWriter(logger.error)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger

# Create and export the logger instance for use throughout the application
logger = setup_logging() 