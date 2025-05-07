"""Configuration module for Cursor Prompt Preprocessor."""

# Application constants
APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "demo_user"
SESSION_ID = "demo_session"
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

# State keys for session state
STATE_USER_PROMPT = "user_prompt"
STATE_PROJECT_STRUCTURE = "project_structure"
STATE_DEPENDENCIES = "dependencies"
STATE_FILTERED_STRUCTURE = "gitignore_filtered_structure"
STATE_RELEVANT_CODE = "relevant_code"
STATE_RELEVANT_TESTS = "relevant_tests"
STATE_RELEVANCE_SCORES = "relevance_scores"
STATE_QUESTIONS = "clarifying_questions"
STATE_ANSWERS = "clarifying_answers"
STATE_FINAL_CONTEXT = "final_context"
STATE_TARGET_DIRECTORY = "target_directory"
STATE_NEEDS_ANSWERS = "needs_answers"

# Special constants
NO_QUESTIONS = "no questions ABSOLUTELY"

# Rate limiting settings
RATE_LIMIT_MAX_CALLS = 10  # maximum calls per minute
RATE_LIMIT_WINDOW = 60  # seconds

# Logging settings
LOG_FILENAME_FORMAT = "cursor_preprocessor_%Y%m%d_%H%M%S.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5 