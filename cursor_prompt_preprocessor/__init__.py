"""Cursor Prompt Preprocessor package.

This package provides tools and agents for analyzing codebases and generating helpful context
for code generation.
"""

from cursor_prompt_preprocessor.agent import root_agent
from cursor_prompt_preprocessor.config import APP_NAME, GEMINI_MODEL, SESSION_ID, USER_ID

__all__ = ["root_agent", "APP_NAME", "USER_ID", "SESSION_ID", "GEMINI_MODEL"]
