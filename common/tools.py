"""Tools for Cursor Prompt Preprocessor - MCP compatible agent tools."""

import datetime
import fnmatch
import glob
import json
import os
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import gitignore_parser
from google.adk.tools import ToolContext

from common.constants import STATE_QUESTIONS, STATE_TARGET_DIRECTORY
from common.logging_setup import logger

# --- Human Input Tools ---


def ask_human_clarification_mcp(
    question_to_ask: str, tool_context: ToolContext | None = None
) -> Dict[str, str]:
    """Get clarification from the user via console input (MCP tool)."""
    logger.info(f"Human clarification requested: {question_to_ask}")
    print("--- CONSOLE INPUT REQUIRED ---")
    reply = input(f"{question_to_ask}: ")
    print("--- CONSOLE INPUT RECEIVED ---")
    return {"reply": reply}


class ClarifierGenerator:
    """Legacy clarification tool for backward compatibility."""

    __name__ = "clarify_questions_tool"

    def __call__(self, tool_context: ToolContext | None = None) -> dict:
        question = "Could you please provide clarification?"
        if tool_context and hasattr(tool_context, "state"):
            question = tool_context.state.get(STATE_QUESTIONS, question)
        return ask_human_clarification_mcp(question, tool_context)


# --- Path Resolution Utilities ---


def _resolve_path(path: str, base_dir: str) -> str:
    """Resolve relative path against base directory."""
    if os.path.isabs(path):
        return os.path.abspath(path)
    if not base_dir or not os.path.isdir(base_dir):
        raise ValueError(f"Invalid base directory: {base_dir}")
    return os.path.abspath(os.path.join(base_dir, path))


def _validate_path_exists(path: str, path_type: str = "path") -> None:
    """Validate that path exists and is of expected type."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path_type.title()} not found: {path}")

    if path_type == "file" and not os.path.isfile(path):
        raise ValueError(f"Path is not a file: {path}")
    elif path_type == "directory" and not os.path.isdir(path):
        raise ValueError(f"Path is not a directory: {path}")


def _handle_tool_error(operation: str, path: str, error: Exception) -> Dict[str, str]:
    """Standard error handling for tool operations."""
    error_msg = f"Error {operation} {path}: {str(error)}"
    logger.error(error_msg)
    return {"error": error_msg}


# --- Directory and File Operations ---


def get_project_structure(
    base_directory: str, tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """Recursively scan directory structure."""
    try:
        structure = {"files": [], "directories": {}}
        for item in os.listdir(base_directory):
            if item.startswith("."):  # Skip hidden files/dirs
                continue

            item_path = os.path.join(base_directory, item)
            if os.path.isfile(item_path):
                structure["files"].append(item)
            elif os.path.isdir(item_path):
                structure["directories"][item] = get_project_structure(item_path, tool_context)
        return structure
    except Exception as e:
        return _handle_tool_error("scanning", base_directory, e)


def scan_project_structure(
    target_directory: str, tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """Scan directory structure with validation."""
    try:
        _validate_path_exists(target_directory, "directory")
        return get_project_structure(target_directory, tool_context)
    except Exception as e:
        return _handle_tool_error("scanning", target_directory, e)


def set_target_directory(directory: str, tool_context: ToolContext | None = None) -> Dict[str, str]:
    """Set target directory in session state."""
    if tool_context and hasattr(tool_context, "state"):
        tool_context.state[STATE_TARGET_DIRECTORY] = directory
        logger.info(f"Target directory set: {directory}")
        return {"status": "success", "directory_set": directory}

    logger.warning("Target directory acknowledged without context")
    return {"status": "warning", "directory_set": directory}


def list_directory_contents(
    path_to_list: str,
    base_dir_context: str,
    include_hidden: bool = False,
    tool_context: ToolContext | None = None,
) -> Dict[str, Any]:
    """List directory contents with metadata."""
    try:
        resolved_path = _resolve_path(path_to_list, base_dir_context)
        _validate_path_exists(resolved_path, "directory")

        files, directories = [], []
        for entry in os.scandir(resolved_path):
            if not include_hidden and entry.name.startswith("."):
                continue

            try:
                stats = entry.stat()
                info = {
                    "name": entry.name,
                    "path": entry.path,
                    "size": stats.st_size,
                    "modified": datetime.datetime.fromtimestamp(
                        stats.st_mtime, tz=ZoneInfo("UTC")
                    ).isoformat(),
                    "type": "file" if entry.is_file() else "directory",
                }
                (files if entry.is_file() else directories).append(info)
            except OSError:
                continue

        return {
            "files": sorted(files, key=lambda x: x["name"]),
            "directories": sorted(directories, key=lambda x: x["name"]),
            "current_path_listed": resolved_path,
            "total_files": len(files),
            "total_directories": len(directories),
        }
    except Exception as e:
        return _handle_tool_error("listing", path_to_list, e)


def read_file_content(
    file_path_to_read: str,
    base_dir_context: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    tool_context: ToolContext | None = None,
) -> Dict[str, Any]:
    """Read file content with optional line range."""
    try:
        resolved_path = _resolve_path(file_path_to_read, base_dir_context)
        _validate_path_exists(resolved_path, "file")

        with open(resolved_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start_idx = max(0, (start_line or 1) - 1)
        end_idx = min(total_lines, end_line or total_lines)

        content = "".join(lines[start_idx:end_idx]) if total_lines > 0 else ""

        return {
            "content": content,
            "line_count": total_lines,
            "actual_start_line": start_idx + 1 if total_lines > 0 else 0,
            "actual_end_line": end_idx if total_lines > 0 else 0,
            "file_path_read": resolved_path,
        }
    except Exception as e:
        return _handle_tool_error("reading", file_path_to_read, e)


# --- Project Analysis Tools ---


def get_dependencies(
    target_directory: str, tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """Analyze project dependencies from common manifest files."""
    dependencies = {}
    dependency_files = {
        "requirements.txt": "python_requirements_txt",
        "package.json": "nodejs_package_json",
    }

    for filename, key in dependency_files.items():
        file_path = os.path.join(target_directory, filename)
        try:
            if os.path.exists(file_path):
                if filename == "requirements.txt":
                    with open(file_path, "r") as f:
                        dependencies[key] = [
                            line.strip() for line in f if line.strip() and not line.startswith("#")
                        ]
                elif filename == "package.json":
                    with open(file_path, "r") as f:
                        pkg_data = json.load(f)
                        dependencies[key] = {
                            "dependencies": pkg_data.get("dependencies", {}),
                            "devDependencies": pkg_data.get("devDependencies", {}),
                        }
        except Exception as e:
            dependencies[f"{key}_error"] = str(e)

    return (
        {"dependencies": dependencies, "path_checked": target_directory}
        if dependencies
        else {"message": "No dependency files found", "path_checked": target_directory}
    )


def filter_by_gitignore(
    target_directory: str, tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """Filter project structure using gitignore rules."""
    try:
        gitignore_path = os.path.join(target_directory, ".gitignore")

        if os.path.exists(gitignore_path):
            matches_gitignore = gitignore_parser.parse_gitignore(
                gitignore_path, base_dir=target_directory
            )
        else:
            matches_gitignore = lambda _: False  # Keep all files if no .gitignore

        structure = get_project_structure(target_directory, tool_context)
        if "error" in structure:
            return structure

        def filter_recursive(struct: Dict[str, Any], current_path: str) -> Dict[str, Any]:
            filtered = {"files": [], "directories": {}}

            for file_name in struct.get("files", []):
                file_path = os.path.join(target_directory, current_path, file_name)
                if not matches_gitignore(file_path):
                    filtered["files"].append(file_name)

            for dir_name, dir_content in struct.get("directories", {}).items():
                dir_path = os.path.join(target_directory, current_path, dir_name)
                if not matches_gitignore(dir_path):
                    filtered["directories"][dir_name] = filter_recursive(
                        dir_content, os.path.join(current_path, dir_name)
                    )
            return filtered

        filtered_result = filter_recursive(structure, "")
        return {
            "filtered_structure": filtered_result,
            "gitignore_status": "applied" if os.path.exists(gitignore_path) else "not_found",
            "path_checked": target_directory,
        }
    except Exception as e:
        return _handle_tool_error("filtering by gitignore", target_directory, e)


# Alias for backward compatibility
apply_gitignore_filter = filter_by_gitignore


def search_codebase(
    target_directory: str,
    keywords: str,
    file_pattern: str = "*.*",
    context_lines: int = 15,
    ignore_case: bool = True,
    tool_context: ToolContext | None = None,
) -> Dict[str, Any]:
    """Search codebase for keywords with smart directory filtering."""

    # Directories to skip (consolidated from original verbose lists)
    SKIP_DIRS = {
        "node_modules",
        "target",
        "build",
        "dist",
        "out",
        "venv",
        ".venv",
        "env",
        ".env",
        "migrations",
        "bin",
        "obj",
        "logs",
        "temp",
        "tmp",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".cache",
        ".tox",
        "site-packages",
        "vendor",
    }
    SKIP_PREFIXES = (".", "__")

    try:
        _validate_path_exists(target_directory, "directory")

        keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not keywords_list:
            return {"error": "No keywords provided"}

        matches = []
        for root, dirs, files in os.walk(target_directory, topdown=True):
            # Skip unwanted directories
            dirs[:] = [
                d for d in dirs if not (d.startswith(SKIP_PREFIXES) or d.lower() in SKIP_DIRS)
            ]

            for filename in files:
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue

                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    for i, line in enumerate(lines):
                        for keyword in keywords_list:
                            if (ignore_case and keyword.lower() in line.lower()) or (
                                not ignore_case and keyword in line
                            ):
                                start_idx = max(0, i - context_lines)
                                end_idx = min(len(lines), i + context_lines + 1)

                                matches.append(
                                    {
                                        "file_path": os.path.relpath(file_path, target_directory),
                                        "line_number": i + 1,
                                        "match_line": line.rstrip(),
                                        "context_before": "".join(lines[start_idx:i]).rstrip(),
                                        "context_after": "".join(lines[i + 1 : end_idx]).rstrip(),
                                        "matched_keyword": keyword,
                                    }
                                )
                                break
                except OSError:
                    continue

        matches.sort(key=lambda x: (x["file_path"], x["line_number"]))
        return {
            "matches": matches,
            "total_matches": len(matches),
            "search_terms_used": keywords_list,
            "path_searched": target_directory,
        }
    except Exception as e:
        return _handle_tool_error("searching", target_directory, e)


# --- Prompt-based Search Tools ---


def search_code_with_prompt(
    target_directory: str,
    prompt_text: str,
    file_pattern: str = "*.*",
    tool_context: ToolContext | None = None,
) -> Dict[str, Any]:
    """Search code using natural language prompt as keywords."""
    if not prompt_text.strip():
        return {"error": "Prompt text cannot be empty"}

    return search_codebase(
        target_directory,
        prompt_text,
        file_pattern,
        context_lines=15,
        ignore_case=True,
        tool_context=tool_context,
    )


def search_tests_with_prompt(
    target_directory: str,
    prompt_text: str,
    file_pattern: str,
    tool_context: ToolContext | None = None,
) -> Dict[str, Any]:
    """Search test files using prompt as keywords."""
    if not prompt_text.strip():
        return {"error": "Prompt text cannot be empty"}
    if not file_pattern.strip():
        return {"error": "File pattern required for test search"}

    return search_codebase(
        target_directory,
        prompt_text,
        file_pattern,
        context_lines=15,
        ignore_case=True,
        tool_context=tool_context,
    )


def determine_relevance_from_prompt(
    prompt_text: str,
    found_files_context: List[Dict[str, Any]],
    tool_context: ToolContext | None = None,
) -> Dict[str, Any]:
    """Placeholder for relevance analysis based on prompt."""
    return {
        "status": "placeholder_analysis",
        "prompt_analyzed": prompt_text[:100] + "..." if len(prompt_text) > 100 else prompt_text,
        "items_evaluated": len(found_files_context),
    }


# --- Session State Management ---


def set_session_state(
    key: str, value_json_str: str, tool_context: ToolContext | None = None
) -> Dict[str, str]:
    """Store key-value pair in session state."""
    try:
        value = json.loads(value_json_str)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {str(e)}"}

    if tool_context and hasattr(tool_context, "state"):
        tool_context.state[key] = value
        return {"status": "success", "message": f"State set for key '{key}'"}

    return {"status": "warning", "message": f"No context available for key '{key}'"}


def get_session_state(key: str, default_value=None, tool_context: ToolContext | None = None):
    """Retrieve value from session state."""
    if tool_context and hasattr(tool_context, "state"):
        value = tool_context.state.get(key, default_value)
        # For ADK compatibility, convert complex objects to JSON strings
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value)
            except (TypeError, ValueError):
                return str(value)
        return value
    return default_value


def get_target_directory_from_state(tool_context: ToolContext | None = None) -> str:
    """Get target directory from session state."""
    return get_session_state(STATE_TARGET_DIRECTORY, ".", tool_context)
