"""Configuration module for Cursor Prompt Preprocessor."""

# Import shared constants from common module
from common.constants import (
    NO_QUESTIONS,
    STATE_ANSWERS,
    STATE_CONSOLIDATED_PROMPT,
    STATE_DEPENDENCIES,
    STATE_FILTERED_STRUCTURE,
    STATE_FINAL_CONTEXT,
    STATE_NEEDS_ANSWERS,
    STATE_PROJECT_STRUCTURE,
    STATE_QUESTIONS,
    STATE_RELEVANCE_SCORES,
    STATE_RELEVANT_CODE,
    STATE_RELEVANT_TESTS,
    STATE_TARGET_DIRECTORY,
    STATE_USER_PROMPT,
)

# Application constants
APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "demo_user"
SESSION_ID = "demo_session"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"

# Rate limiting settings
RATE_LIMIT_MAX_CALLS = 10  # maximum calls per minute
RATE_LIMIT_WINDOW = 60  # seconds

# Logging settings
LOG_FILENAME_FORMAT = "cursor_preprocessor_%Y%m%d_%H%M%S.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
