import sys
import os
import uvicorn.config

# Add the project root to sys.path to allow absolute imports
# __file__ is .../coding-prompt-preprocessor/cursor_prompt_preprocessor/mcp_server.py
# os.path.dirname(__file__) is .../coding-prompt-preprocessor/cursor_prompt_preprocessor
# project_root is .../coding-prompt-preprocessor
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Uvicorn Logging Configuration ---
# Modify Uvicorn's default logging config to prevent 'isatty' error
# by disabling color codes, as MCP's LoggerWriter for stdout/stderr
# does not have an 'isatty' method.
if hasattr(uvicorn.config, "LOGGING_CONFIG"):
    if "formatters" in uvicorn.config.LOGGING_CONFIG:
        if "default" in uvicorn.config.LOGGING_CONFIG["formatters"]:
            if isinstance(uvicorn.config.LOGGING_CONFIG["formatters"]["default"], dict):
                uvicorn.config.LOGGING_CONFIG["formatters"]["default"]["use_colors"] = False
        if "access" in uvicorn.config.LOGGING_CONFIG["formatters"]: # Also for access logs
            if isinstance(uvicorn.config.LOGGING_CONFIG["formatters"]["access"], dict):
                uvicorn.config.LOGGING_CONFIG["formatters"]["access"]["use_colors"] = False
# --- End Uvicorn Logging Configuration ---

"""
MCP Server for Cursor Prompt Preprocessor Tools.

This server exposes the functionalities in tools.py via the Model Context Protocol.
"""
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List, Optional

from cursor_prompt_preprocessor.tools import (
    ask_human_clarification_mcp,
    scan_project_structure,
    set_target_directory,
    list_directory_contents,
    read_file_content,
    get_dependencies,
    apply_gitignore_filter,
    search_codebase,
    search_code_with_prompt,
    search_tests_with_prompt,
    determine_relevance_from_prompt,
)
from cursor_prompt_preprocessor.logging_setup import logger

# Initialize MCP Server
server = FastMCP(
    "CursorPromptPreprocessorTools",
    version="0.1.0",
    description="Provides tools for project analysis and interaction for LLM agents."
)

# --- Tool Definitions ---

@server.tool()
def ask_human_clarification(question_to_ask: str) -> Dict[str, str]:
    """MCP Tool: Get clarification from the user via console input."""
    return ask_human_clarification_mcp(question_to_ask=question_to_ask)

@server.tool()
def scan_project(target_directory: str) -> Dict[str, Any]:
    """MCP Tool: Scan the target directory's structure."""
    return scan_project_structure(target_directory=target_directory)

@server.tool()
def configure_target_directory(directory: str) -> Dict[str, str]:
    """MCP Tool: Acknowledges a target directory. Agent should manage state."""
    return set_target_directory(directory=directory) 

@server.tool()
def list_contents(
    path_to_list: str, 
    base_dir_context: str, 
    include_hidden: bool = False
) -> Dict[str, Any]:
    """MCP Tool: List contents of a directory with detailed information."""
    return list_directory_contents(
        path_to_list=path_to_list,
        base_dir_context=base_dir_context,
        include_hidden=include_hidden
    )

@server.tool()
def read_file(
    file_path_to_read: str, 
    base_dir_context: str,
    start_line: Optional[int] = None, 
    end_line: Optional[int] = None
) -> Dict[str, Any]:
    """MCP Tool: Read the contents of a file."""
    return read_file_content(
        file_path_to_read=file_path_to_read,
        base_dir_context=base_dir_context,
        start_line=start_line,
        end_line=end_line
    )

@server.tool()
def get_project_dependencies(target_directory: str) -> Dict[str, Any]:
    """MCP Tool: Analyze project dependencies from common manifest files."""
    return get_dependencies(target_directory=target_directory)

@server.tool()
def filter_project_by_gitignore(target_directory: str) -> Dict[str, Any]:
    """MCP Tool: Filter a project structure based on .gitignore rules."""
    return apply_gitignore_filter(target_directory=target_directory)

@server.tool()
def search_project_codebase(
    target_directory: str,
    keywords: str,
    file_pattern: str = "*.*",
    context_lines: int = 15,
    ignore_case: bool = True
) -> Dict[str, Any]:
    """MCP Tool: Search the codebase for keywords with surrounding context."""
    return search_codebase(
        target_directory=target_directory,
        keywords=keywords,
        file_pattern=file_pattern,
        context_lines=context_lines,
        ignore_case=ignore_case
    )

# --- Placeholder Tool Definitions (Exposed via MCP) ---

@server.tool()
def search_code_via_prompt(target_directory: str, prompt_text: str, file_pattern: str = "*.*") -> Dict[str, Any]:
    """MCP Tool: Search code using a natural language prompt and an optional file pattern."""
    return search_code_with_prompt(target_directory=target_directory, prompt_text=prompt_text, file_pattern=file_pattern)

@server.tool()
def search_tests_via_prompt(target_directory: str, prompt_text: str, file_pattern: str) -> Dict[str, Any]:
    """MCP Tool: Search test files using a natural language prompt and a specific file pattern."""
    return search_tests_with_prompt(target_directory=target_directory, prompt_text=prompt_text, file_pattern=file_pattern)

@server.tool()
def determine_file_relevance_via_prompt(prompt_text: str, found_files_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """MCP Tool (Placeholder): Determine relevance of found files/matches based on a prompt."""
    return determine_relevance_from_prompt(prompt_text=prompt_text, found_files_context=found_files_context)

# To run this server:
# Ensure you are in the root of the `coding-prompt-preprocessor` directory.
# Execute: mcp dev cursor_prompt_preprocessor/mcp_server.py

if __name__ == "__main__":
    logger.info("MCP Server definition loaded.")
    print("To run this MCP server, navigate to the project root directory and execute:")
    print("mcp dev cursor_prompt_preprocessor/mcp_server.py")
    print("Ensure your Python environment with 'mcp[cli]' is active.") 

    server.run(transport="streamable-http")