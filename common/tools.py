"""Tools for the Cursor Prompt Preprocessor.

This module contains all the tool functions used by agents to interact with
the codebase, file system, and user.
"""

import datetime
from zoneinfo import ZoneInfo
import glob
import os
import gitignore_parser
import json
from typing import Optional, Dict, Any, List, Union

from cursor_prompt_preprocessor.config import STATE_TARGET_DIRECTORY, STATE_QUESTIONS
from common.logging_setup import logger
from cursor_prompt_preprocessor.session import session_manager

# --- New MCP-friendly Clarification Tool ---
def ask_human_clarification_mcp(question_to_ask: str) -> Dict[str, str]:
    """Get clarification from the user via console input.
    
    This version is intended to be used as an MCP tool, taking the question directly.
    
    Args:
        question_to_ask: The question to ask the user.
        
    Returns:
        dict: The user's reply.
    """
    logger.info(f"Asking for human clarification via MCP tool: {question_to_ask}")
    print("--- CONSOLE INPUT REQUIRED (MCP Tool) ---")
    human_reply = input(f"{question_to_ask}: ")
    print("--- CONSOLE INPUT RECEIVED (MCP Tool) ---")
    return {"reply": human_reply}

# --- Original ClarifierGenerator (for agent-side use if needed, or can be deprecated) ---
class ClarifierGenerator:
    '''Synchronous function to get console input for clarification.'''
    __name__ = "clarify_questions_tool"  # Name for agent instructions

    def __call__(self) -> dict:
        """Get clarification from the user via console input.
        
        Retrieves the question from session state and prompts the user for input.
        
        Returns:
            dict: The user's reply
        """
        # Get the question from the state
        question_to_ask = session_manager.get_state(
            STATE_QUESTIONS, 
            "Could you please provide clarification? (Error: Question not found in state)"
        )
        
        # Prompt the user directly in the console where the agent is running
        print("--- CONSOLE INPUT REQUIRED ---")
        human_reply = input(f"{question_to_ask}: ")
        print("--- CONSOLE INPUT RECEIVED ---")
        
        # Return the received input
        return {"reply": human_reply}


# --- File System Tools (Refactored for MCP) ---

# This function remains for agent-side use to get the state if needed
def get_target_directory_from_state() -> str:
    """Get the target directory from the session state.
    
    Returns:
        str: The target directory path, or "." if not set.
    """
    return session_manager.get_state(STATE_TARGET_DIRECTORY, ".")

def get_project_structure(base_directory: str) -> Dict[str, Any]:
    """Scan a directory and return its structure recursively.

    Args:
        base_directory: The directory to scan.

    Returns:
        dict: A dictionary representation of the project structure.
    """
    # Ensure base_directory is not None or empty, default to "." if so (though MCP tool should always provide it)
    current_scan_directory = base_directory if base_directory else "."
        
    structure = {"files": [], "directories": {}}
    try:
        items = os.listdir(current_scan_directory)
        for item in items:
            item_path = os.path.join(current_scan_directory, item)
            if os.path.isfile(item_path):
                structure["files"].append(item)
            elif os.path.isdir(item_path) and not item.startswith("."): # Exclude .git, .venv etc.
                # Recursive call should also use the absolute/correct path context
                structure["directories"][item] = get_project_structure(item_path)
        return structure
    except Exception as e:
        logger.error(f"Error getting project structure for {current_scan_directory}: {str(e)}")
        return {"error": str(e), "path_scanned": current_scan_directory}

def scan_project_structure(target_directory: str) -> Dict[str, Any]:
    """Scan the target directory's structure. (MCP-friendly)
    
    Args:
        target_directory: The root directory to scan.
    
    Returns:
        dict: A dictionary representation of the project structure.
    """
    if not target_directory or not os.path.isdir(target_directory):
        logger.error(f"Invalid target_directory for scan_project_structure: {target_directory}")
        return {"error": f"Invalid or non-existent directory: {target_directory}"}
    return get_project_structure(target_directory)

def set_target_directory(directory: str) -> Dict[str, str]:
    """Set the target directory for code analysis (MCP version).
    
    This MCP tool primarily validates and returns the directory. 
    The calling agent is responsible for managing this state in its session.
    
    Args:
        directory: The directory path to analyze.
        
    Returns:
        dict: A confirmation message with the directory.
    """
    # Basic validation (can be expanded)
    # For MCP tool, it might just acknowledge the path.
    # If it needs to be stored server-side for a specific MCP session, that's more complex.
    # For now, it just returns it, and the agent handles session state.
    logger.info(f"MCP tool 'set_target_directory' called with: {directory}")
    return {
        "status": "acknowledged", 
        "message": f"Target directory acknowledged by MCP tool: {directory}",
        "directory_set": directory # The agent can use this to update its state
    }

def list_directory_contents(
    path_to_list: str, 
    base_dir_context: str, 
    include_hidden: bool = False
) -> Dict[str, Any]:
    """List contents of a directory with detailed information (MCP-friendly).
    
    Args:
        path_to_list: Path to list (can be relative to base_dir_context).
        base_dir_context: The base directory context for resolving relative paths.
        include_hidden: Whether to include hidden files/directories (default: False)
        
    Returns:
        dict: Directory contents with metadata
    """
    try:
        # Resolve path_to_list
        if not os.path.isabs(path_to_list):
            if not base_dir_context or not os.path.isdir(base_dir_context):
                return {"error": f"Invalid base_dir_context: {base_dir_context} for relative path: {path_to_list}"}
            resolved_path = os.path.abspath(os.path.join(base_dir_context, path_to_list))
        else:
            resolved_path = os.path.abspath(path_to_list)
            
        if not os.path.exists(resolved_path):
            return {"error": f"Path not found: {resolved_path}"}
        if not os.path.isdir(resolved_path):
            return {"error": f"Path is not a directory: {resolved_path}"}
            
        files = []
        directories = []
        
        for entry in os.scandir(resolved_path):
            if not include_hidden and entry.name.startswith('.'):
                continue
            try:
                stats = entry.stat()
                info = {
                    "name": entry.name,
                    "path": entry.path, # This will be absolute path from scandir
                    "size": stats.st_size,
                    "modified": datetime.datetime.fromtimestamp(
                        stats.st_mtime, tz=ZoneInfo("UTC")).isoformat(),
                    "created": datetime.datetime.fromtimestamp(
                        stats.st_ctime, tz=ZoneInfo("UTC")).isoformat()
                }
                if entry.is_file():
                    info["type"] = "file"
                    files.append(info)
                elif entry.is_dir():
                    info["type"] = "directory"
                    directories.append(info)
            except Exception as e:
                logger.warning(f"Error getting info for {entry.path}: {str(e)}")
                continue
        
        return {
            "files": sorted(files, key=lambda x: x["name"]),
            "directories": sorted(directories, key=lambda x: x["name"]),
            "current_path_listed": resolved_path,
            "total_files": len(files),
            "total_directories": len(directories)
        }
    except Exception as e:
        logger.error(f"Error listing directory {path_to_list} (context: {base_dir_context}): {str(e)}")
        return {"error": f"Failed to list directory: {str(e)}"}

def read_file_content(
    file_path_to_read: str, 
    base_dir_context: str,
    start_line: Optional[int] = None, 
    end_line: Optional[int] = None
) -> Dict[str, Any]:
    """Read the contents of a file (MCP-friendly).
    
    Args:
        file_path_to_read: Path to the file (can be relative to base_dir_context).
        base_dir_context: The base directory context for resolving relative file paths.
        start_line: Optional 1-based start line number (inclusive).
        end_line: Optional 1-based end line number (inclusive).
        
    Returns:
        dict: File content and metadata.
    """
    try:
        if not os.path.isabs(file_path_to_read):
            if not base_dir_context or not os.path.isdir(base_dir_context):
                return {"error": f"Invalid base_dir_context: {base_dir_context} for relative file: {file_path_to_read}"}
            resolved_file_path = os.path.abspath(os.path.join(base_dir_context, file_path_to_read))
        else:
            resolved_file_path = os.path.abspath(file_path_to_read)
            
        if not os.path.exists(resolved_file_path):
            return {"error": f"File not found: {resolved_file_path}"}
        if not os.path.isfile(resolved_file_path):
            return {"error": f"Path is not a file: {resolved_file_path}"}
            
        with open(resolved_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        actual_start_line = start_line if start_line is not None else 1
        actual_end_line = end_line if end_line is not None else total_lines
        
        actual_start_line = max(1, min(actual_start_line, total_lines if total_lines > 0 else 1))
        actual_end_line = max(actual_start_line, min(actual_end_line, total_lines))
        
        # Adjust for empty files or out-of-bounds requests on empty files
        if total_lines == 0:
            content_slice = []
        else:
            content_slice = lines[actual_start_line - 1:actual_end_line]

        content = ''.join(content_slice)
        
        return {
            "content": content,
            "line_count": total_lines,
            "requested_start_line": start_line, # what was asked
            "requested_end_line": end_line,     # what was asked
            "actual_start_line": actual_start_line if total_lines > 0 else 0, # what was delivered
            "actual_end_line": actual_end_line if total_lines > 0 else 0,     # what was delivered
            "file_path_read": resolved_file_path
        }
    except Exception as e:
        logger.error(f"Error reading file {file_path_to_read} (context: {base_dir_context}): {str(e)}")
        return {"error": f"Failed to read file: {str(e)}"}

# --- Project Analysis Tools (Refactored for MCP) ---

def get_dependencies(target_directory: str) -> Dict[str, Any]:
    """Analyze project dependencies (MCP-friendly).

    Args:
        target_directory: The root project directory.

    Returns:
        dict: A dictionary of project dependencies.
    """
    if not target_directory or not os.path.isdir(target_directory):
        return {"error": f"Invalid target_directory: {target_directory}"}
    
    dependencies = {}
    req_path = os.path.join(target_directory, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, "r", encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Improved parsing for various specifiers
                    name = line.split(">=")[0].split("==")[0].split("<=")[0].split("!=")[0].split("~=")[0].split("<")[0].split(">")[0].strip()
                    version_spec = line[len(name):].strip()
                    dependencies[name] = version_spec if version_spec else "any"
    
    pkg_path = os.path.join(target_directory, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r", encoding='utf-8') as file:
                package_data = json.load(file)
            if "dependencies" in package_data:
                dependencies.update(package_data["dependencies"])
            if "devDependencies" in package_data: # Often good to know these too
                dependencies.update({f"dev_{k}": v for k, v in package_data["devDependencies"].items()})
        except json.JSONDecodeError:
            logger.warning(f"Invalid package.json format in {target_directory}")
            dependencies["package_json_error"] = "Invalid package.json format"
    
    if not dependencies and "package_json_error" not in dependencies:
        logger.info(f"No common dependency files found in {target_directory}")
        return {"message": "No common dependency files (requirements.txt, package.json) found or parsed.", "path_checked": target_directory}

    return {"dependencies": dependencies, "path_checked": target_directory}


def filter_by_gitignore(target_directory: str) -> Dict[str, Any]:
    """Filter a project structure based on gitignore rules (MCP-friendly).
    
    Args:
        target_directory: The root project directory containing .gitignore.

    Returns:
        dict: Filtered project structure or error.
    """
    try:
        if not target_directory or not os.path.isdir(target_directory):
            return {"error": f"Invalid target_directory: {target_directory}"}
            
        # Get the full structure first
        # IMPORTANT: get_project_structure needs to work relative to the actual files,
        # so we pass target_directory to it.
        initial_structure = get_project_structure(target_directory)
        if "error" in initial_structure:
             return {"error": f"Could not get project structure for gitignore filtering: {initial_structure['error']}", "path_checked": target_directory}

        gitignore_path = os.path.join(target_directory, ".gitignore")
        if not os.path.exists(gitignore_path):
            logger.info(f".gitignore not found in {target_directory}, returning full structure.")
            return {"filtered_structure": initial_structure, "gitignore_status": "not_found", "path_checked": target_directory}
        
        # Base path for gitignore_parser should be the directory containing .gitignore
        matches = gitignore_parser.parse_gitignore(gitignore_path, base_dir=os.path.abspath(target_directory))
        
        # Helper function to filter structure. Paths passed to 'matches' must be relative to target_directory
        # or absolute, matching how parse_gitignore was initialized if base_dir was used correctly.
        # Using os.path.relpath for consistency if paths in structure are absolute.
        # Or, ensure paths constructed are relative to target_directory from the start.
        
        # Let's ensure paths used for matching are relative to the gitignore file's location (target_directory)
        def filter_recursive(current_struct: Dict[str, Any], current_path_relative_to_target: str) -> Dict[str, Any]:
            filtered_sub_structure = {"files": [], "directories": {}}
            
            for file_name in current_struct.get("files", []):
                # Construct path relative to target_directory for matching
                path_to_check = os.path.join(current_path_relative_to_target, file_name)
                # gitignore_parser expects paths relative to the .gitignore location
                # or absolute if base_dir was used correctly.
                # For paths from os.walk or similar, they might be absolute already.
                # If using base_dir with parse_gitignore, it handles this.
                # Let's make path_to_check absolute then let 'matches' handle it.
                abs_path_to_check = os.path.abspath(os.path.join(target_directory, path_to_check))

                if not matches(abs_path_to_check):
                    filtered_sub_structure["files"].append(file_name)
            
            for dir_name, dir_sub_struct in current_struct.get("directories", {}).items():
                path_to_check = os.path.join(current_path_relative_to_target, dir_name)
                abs_path_to_check = os.path.abspath(os.path.join(target_directory, path_to_check))
                
                if not matches(abs_path_to_check):
                    filtered_sub_structure["directories"][dir_name] = filter_recursive(dir_sub_struct, path_to_check)
            
            return filtered_sub_structure
        
        # Start filtering from the root of the structure, with an empty relative path initially
        filtered_result = filter_recursive(initial_structure, "") 
        return {"filtered_structure": filtered_result, "gitignore_status": "applied", "path_checked": target_directory}

    except Exception as e:
        logger.error(f"Error filtering by gitignore for {target_directory}: {str(e)}")
        return {"error": f"Error filtering by gitignore: {str(e)}", "path_checked": target_directory}

def apply_gitignore_filter(target_directory: str) -> Dict[str, Any]:
    """Apply gitignore filtering to the project structure (MCP-friendly wrapper).
    
    Args:
        target_directory: The root project directory.
        
    Returns:
        dict: Filtered project structure.
    """
    return filter_by_gitignore(target_directory)

def search_codebase(
    target_directory: str,
    keywords: str, # comma-separated
    file_pattern: str = "*.*", # Glob pattern
    context_lines: int = 15,
    ignore_case: bool = True
) -> Dict[str, Any]:
    """Search the codebase for keywords (MCP-friendly).
    
    Args:
        target_directory: The root directory to search within.
        keywords: Search terms (comma-separated).
        file_pattern: Glob pattern for files to search.
        context_lines: Number of lines before/after match.
        ignore_case: Whether to ignore case.
        
    Returns:
        dict: Search results.
    """
    # Define skip patterns for directory names and prefixes
    # These are checked case-insensitively for names, and case-sensitively for prefixes.
    _SKIPPED_DIR_PREFIXES = ('.', '__') 
    _SKIPPED_DIR_NAMES = frozenset([
        'node_modules', 'target', 'build', 'dist', 'out',
        'venv', '.venv', 'env', '.env', 'nbproject', '.idea',
        'migrations', 'bin', 'obj', 'logs', 'temp', 'tmp',
        '.git', '.hg', '.svn', '.bzr', # version control
        '__pycache__', '.pytest_cache', '.mypy_cache', '.cache', '.tox',
        'site-packages', # python specific
        'bower_components', 'jspm_packages', # js specific
        'vendor', # common for many languages (PHP, Ruby, Go)
        'buildsrc', # gradle
        'cmake-build-debug', 'cmake-build-release', # CMake
        'xcuserdata', # Xcode
        '.ds_store' # macOS specific file/folder often found
    ])

    try:
        if not target_directory or not os.path.isdir(target_directory):
            return {"error": f"Invalid target_directory: {target_directory}"}

        matches_found = []
        total_matches_count = 0
        
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        if not keyword_list:
             return {"error": "No keywords provided for search.", "path_checked": target_directory}

        logger.info(f"Searching in {target_directory} for keywords: {keyword_list} (pattern: {file_pattern})")
        
        norm_target_dir_path = os.path.normpath(target_directory)

        # Walk through the target_directory, topdown=True allows modifying `dirs` to prune traversal
        for root, dirs, files_in_dir in os.walk(target_directory, topdown=True):
            norm_root_path = os.path.normpath(root)

            # Part 1: Check if the current 'root' directory itself (relative to target_dir)
            # is part of a path that should be skipped.
            skip_current_root_processing = False
            if norm_root_path != norm_target_dir_path:
                relative_path_from_target = os.path.relpath(norm_root_path, norm_target_dir_path)
                # Path components of the current root relative to the target directory
                path_components = relative_path_from_target.split(os.sep)
                
                for component in path_components:
                    if not component or component == '.': # Skip empty or current dir components
                        continue
                    if component.startswith(_SKIPPED_DIR_PREFIXES) or \
                       component.lower() in _SKIPPED_DIR_NAMES:
                        skip_current_root_processing = True
                        break
            
            if skip_current_root_processing:
                logger.debug(f"Skipping directory and its contents: {norm_root_path} due to matching a skip pattern in its path.")
                dirs[:] = []  # Don't descend into subdirectories of this skipped root.
                continue      # Skip processing files in this root and this iteration of os.walk.

            # Part 2: Prune subdirectories from 'dirs' based on their names.
            # This filters out dirs like '.git', '__pycache__', 'node_modules' directly under the current 'root'.
            original_dirs_len = len(dirs)
            dirs[:] = [d_name for d_name in dirs if not (
                            d_name.startswith(_SKIPPED_DIR_PREFIXES) or \
                            d_name.lower() in _SKIPPED_DIR_NAMES
                        )]
            
            if len(dirs) != original_dirs_len:
                pruned_count = original_dirs_len - len(dirs)
                logger.debug(f"Pruned {pruned_count} subdirectories from further traversal under {norm_root_path}")

            # Process files in the current, non-skipped directory
            for file_name in files_in_dir:
                if not glob.fnmatch.fnmatch(file_name, file_pattern):
                    continue
                    
                current_file_path = os.path.join(root, file_name)
                try:
                    with open(current_file_path, 'r', encoding='utf-8', errors='ignore') as f_handle:
                        lines_content = f_handle.readlines()
                        
                    for i, line_text in enumerate(lines_content):
                        for keyword_item in keyword_list:
                            line_matches_keyword = (ignore_case and keyword_item.lower() in line_text.lower()) or \
                                                 (not ignore_case and keyword_item in line_text)
                            if line_matches_keyword:
                                start_idx = max(0, i - context_lines)
                                end_idx = min(len(lines_content), i + context_lines + 1)
                                
                                context_before_match = ''.join(lines_content[start_idx:i]).rstrip()
                                matched_line_content = lines_content[i].rstrip()
                                context_after_match = ''.join(lines_content[i+1:end_idx]).rstrip()
                                
                                match_detail = {
                                    "file_path": os.path.relpath(current_file_path, target_directory), # Relative path
                                    "absolute_file_path": current_file_path,
                                    "line_number": i + 1,
                                    "context_before": context_before_match,
                                    "match_line": matched_line_content,
                                    "context_after": context_after_match,
                                    "context_window_start": start_idx + 1,
                                    "context_window_end": end_idx,
                                    "matched_keyword": keyword_item
                                }
                                matches_found.append(match_detail)
                                total_matches_count += 1
                                break # Found a keyword on this line, move to next line
                                
                except Exception as e_file:
                    logger.warning(f"Error searching file {current_file_path}: {str(e_file)}")
                    continue # Skip this file
        
        matches_found.sort(key=lambda x: (x["file_path"], x["line_number"]))
        
        return {
            "matches": matches_found,
            "total_matches": total_matches_count,
            "search_terms_used": keyword_list,
            "file_pattern_used": file_pattern,
            "context_lines_set": context_lines,
            "path_searched": target_directory
        }
        
    except Exception as e_main:
        logger.error(f"Error during codebase search in {target_directory}: {str(e_main)}")
        return {"error": f"Failed to search codebase: {str(e_main)}", "path_searched": target_directory}

# --- Agent Assistance Tools (Placeholders - Refactored for MCP if they were to be implemented) ---

def search_code_with_prompt(target_directory: str, prompt_text: str, file_pattern: str = "*.*") -> Dict[str, Any]:
    """Search code using a prompt (MCP-friendly).
    Args:
        target_directory: The directory to search within.
        prompt_text: The user prompt to guide the search.
        file_pattern: Glob pattern for files to search (e.g., "*.py", "*.*" ).
    Returns:
        dict: Search results or error message.
    """
    logger.info(f"MCP tool 'search_code_with_prompt' called for dir: {target_directory} with prompt: '{prompt_text[:50]}...' and pattern: {file_pattern}")
    # Use the prompt_text as keywords for the search_codebase function.
    # This is a basic implementation. More sophisticated prompt processing could be added.
    if not prompt_text or not prompt_text.strip():
        return {"error": "Prompt text cannot be empty."}
    
    # Treat the entire prompt as a comma-separated list of keywords.
    # For more nuanced search, the prompt could be parsed to extract entities or key phrases.
    keywords = prompt_text # Or a processed version of prompt_text
    
    return search_codebase(
        target_directory=target_directory,
        keywords=keywords, # Using the prompt directly as keywords
        file_pattern=file_pattern, # Use provided file_pattern
        context_lines=15, # Default context lines
        ignore_case=True    # Default to ignore case
    )

def search_tests_with_prompt(target_directory: str, prompt_text: str, file_pattern: str) -> Dict[str, Any]:
    """Search test files using a prompt (MCP-friendly).
    Args:
        target_directory: The directory to search tests within.
        prompt_text: The user prompt to guide the test search.
        file_pattern: Glob pattern for test files to search (e.g., "*test*.py", "*.spec.js").
    Returns:
        dict: Search results or error message.
    """
    logger.info(f"MCP tool 'search_tests_with_prompt' called for dir: {target_directory} with prompt: '{prompt_text[:50]}...' and pattern: {file_pattern}")
    
    if not prompt_text or not prompt_text.strip():
        return {"error": "Prompt text cannot be empty."}
    if not file_pattern or not file_pattern.strip():
        return {"error": "File pattern cannot be empty for searching tests."}
        
    keywords = prompt_text # Using the prompt directly as keywords
    
    return search_codebase(
        target_directory=target_directory,
        keywords=keywords,
        file_pattern=file_pattern, # Use the agent-provided file pattern
        context_lines=15,
        ignore_case=True
    )

def determine_relevance_from_prompt(prompt_text: str, found_files_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """MCP Tool (Placeholder): Determine relevance of found files/matches based on a prompt.
    
    Args:
        prompt_text: The user's prompt.
        found_files_context: Contextual information about files/matches.
        
    Returns:
        dict: Relevance scores or analysis.
    """
    # This is a placeholder. In a real implementation, this would likely involve
    # more sophisticated logic, possibly another LLM call or embedding comparisons.
    logger.info(f"Determining relevance for prompt: '{prompt_text[:50]}...' based on {len(found_files_context)} items.")
    return {
        "status": "placeholder_relevance_determined",
        "prompt_analyzed": prompt_text,
        "items_evaluated": len(found_files_context),
        "relevance_output": "Placeholder: Detailed relevance analysis would go here."
    }

# --- Session State Tools (Refactored for MCP) ---

def set_session_state(key: str, value_json_str: str) -> Dict[str, str]:
    """Store a key-value pair in the session state. (MCP-friendly wrapper)
    
    Args:
        key: The key to store.
        value_json_str: The value to store, as a JSON-encoded string.
                        If the original value is a simple string, it can be passed directly
                        (it will be valid JSON if not containing special characters, or pass as a JSON string e.g. "mystring").
                        For dicts or lists, serialize to JSON first before calling this tool.
        
    Returns:
        dict: A status message.
    """
    actual_value: Any
    try:
        # Attempt to parse as JSON. This allows storing complex types.
        actual_value = json.loads(value_json_str)
    except json.JSONDecodeError:
        # If it's not valid JSON, store it as a plain string.
        # This handles cases where a simple string (not JSON-encoded) is passed.
        actual_value = value_json_str

    session_manager.set_state(key, actual_value)
    logger.info(f"State set via MCP tool: Key='{key}', Type='{type(actual_value).__name__}' was set. Original string: '{value_json_str[:100]}...'")
    return {"status": "success", "key_set": key, "value_type": type(actual_value).__name__}


def get_session_state(key: str, default: Optional[Any] = None) -> Any:
    """Get a value from the session state.
    
    Args:
        key: The state key to retrieve.
        default: The default value to return if the key is not found.
    
    Returns:
        Any: The retrieved value or the default if the key is not found.
    """
    return session_manager.get_state(key, default) 