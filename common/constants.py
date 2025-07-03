"""Shared constants for the project modules."""

# State keys for session state - these are used across multiple modules
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
