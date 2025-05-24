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

from google.adk.tools import ToolContext

from cursor_prompt_preprocessor.config import STATE_TARGET_DIRECTORY, STATE_QUESTIONS
from common.logging_setup import logger

# --- New MCP-friendly Clarification Tool ---
def ask_human_clarification_mcp(question_to_ask: str, tool_context: ToolContext | None = None) -> Dict[str, str]:
    """Get clarification from the user via console input.
    
    This version is intended to be used as an MCP tool, taking the question directly.
    
    Args:
        question_to_ask: The question to ask the user.
        tool_context: The ADK tool context.
        
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

    def __call__(self, tool_context: ToolContext | None = None) -> dict:
        """Get clarification from the user via console input.
        
        Retrieves the question from session state and prompts the user for input.
        
        Args:
            tool_context: The ADK tool context.
            
        Returns:
            dict: The user's reply
        """
        question_to_ask = "Could you please provide clarification? (Error: Question not found in state)"
        if tool_context and hasattr(tool_context, 'state'):
            question_to_ask = tool_context.state.get(
                STATE_QUESTIONS, 
                "Could you please provide clarification? (Error: Question not found in state from context)"
            )
        else:
            logger.warning("ClarifierGenerator: ToolContext or tool_context.state not available, using default question.")
        
        # Prompt the user directly in the console where the agent is running
        print("--- CONSOLE INPUT REQUIRED ---")
        human_reply = input(f"{question_to_ask}: ")
        print("--- CONSOLE INPUT RECEIVED ---")
        
        # Return the received input
        return {"reply": human_reply}


# --- File System Tools (Refactored for MCP) ---

# This function remains for agent-side use to get the state if needed
def get_target_directory_from_state(tool_context: ToolContext | None = None) -> str:
    """Get the target directory from the session state.
    
    Args:
        tool_context: The ADK tool context.

    Returns:
        str: The target directory path, or "." if not set.
    """
    if tool_context and hasattr(tool_context, 'state'):
        return tool_context.state.get(STATE_TARGET_DIRECTORY, ".")
    logger.warning("get_target_directory_from_state: ToolContext or tool_context.state not available, returning default '.'")
    return "."

def get_project_structure(base_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Scan a directory and return its structure recursively.

    Args:
        base_directory: The directory to scan.
        tool_context: The ADK tool context.

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
                structure["directories"][item] = get_project_structure(item_path, tool_context)
        return structure
    except Exception as e:
        logger.error(f"Error getting project structure for {current_scan_directory}: {str(e)}")
        return {"error": str(e), "path_scanned": current_scan_directory}

def scan_project_structure(target_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Scan the target directory's structure. (MCP-friendly)
    
    Args:
        target_directory: The root directory to scan.
        tool_context: The ADK tool context.
    
    Returns:
        dict: A dictionary representation of the project structure.
    """
    if not target_directory or not os.path.isdir(target_directory):
        logger.error(f"Invalid target_directory for scan_project_structure: {target_directory}")
        return {"error": f"Invalid or non-existent directory: {target_directory}"}
    return get_project_structure(target_directory, tool_context)

def set_target_directory(directory: str, tool_context: ToolContext | None = None) -> Dict[str, str]:
    """Set the target directory for code analysis (MCP version).
    
    This MCP tool primarily validates and returns the directory. 
    The calling agent is responsible for managing this state in its session using the tool_context.
    
    Args:
        directory: The directory path to analyze.
        tool_context: The ADK tool context.
        
    Returns:
        dict: A confirmation message with the directory.
    """
    logger.info(f"MCP tool 'set_target_directory' called with: {directory}")
    if tool_context and hasattr(tool_context, 'state'):
        tool_context.state[STATE_TARGET_DIRECTORY] = directory
        logger.info(f"Target directory set in session state: {directory}")
        return {
            "status": "success", 
            "message": f"Target directory set in session state: {directory}",
            "directory_set": directory
        }
    else:
        logger.warning("set_target_directory: ToolContext or tool_context.state not available. Directory not set in session state.")
        return {
            "status": "warning", 
            "message": f"Target directory acknowledged by MCP tool: {directory}. State not updated (no context).",
            "directory_set": directory
        }

def list_directory_contents(
    path_to_list: str, 
    base_dir_context: str, 
    include_hidden: bool = False,
    tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """List contents of a directory with detailed information (MCP-friendly).
    
    Args:
        path_to_list: Path to list (can be relative to base_dir_context).
        base_dir_context: The base directory context for resolving relative paths.
        include_hidden: Whether to include hidden files/directories (default: False)
        tool_context: The ADK tool context.
        
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
    end_line: Optional[int] = None,
    tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """Read the contents of a file (MCP-friendly).
    
    Args:
        file_path_to_read: Path to the file (can be relative to base_dir_context).
        base_dir_context: The base directory context for resolving relative file paths.
        start_line: Optional 1-based start line number (inclusive).
        end_line: Optional 1-based end line number (inclusive).
        tool_context: The ADK tool context.
        
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

def get_dependencies(target_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Analyze project dependencies (MCP-friendly).

    Args:
        target_directory: The root project directory.
        tool_context: The ADK tool context.

    Returns:
        dict: Analysis of dependencies or error message.
    """
    logger.info(f"Getting dependencies for directory: {target_directory}")
    dependencies = {}
    found_any = False

    # Python: requirements.txt
    try:
        req_path = os.path.join(target_directory, "requirements.txt")
        if os.path.exists(req_path):
            with open(req_path, 'r') as f:
                dependencies["python_requirements_txt"] = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            found_any = True
            logger.info(f"Found and parsed {req_path}")
    except Exception as e:
        logger.error(f"Error parsing requirements.txt in {target_directory}: {str(e)}")
        dependencies["python_requirements_txt_error"] = str(e)

    # Node.js: package.json
    try:
        pkg_path = os.path.join(target_directory, "package.json")
        if os.path.exists(pkg_path):
            with open(pkg_path, 'r') as f:
                pkg_data = json.load(f)
                dependencies["nodejs_package_json"] = {
                    "dependencies": pkg_data.get("dependencies", {}),
                    "devDependencies": pkg_data.get("devDependencies", {})
                }
            found_any = True
            logger.info(f"Found and parsed {pkg_path}")
    except Exception as e:
        logger.error(f"Error parsing package.json in {target_directory}: {str(e)}")
        dependencies["nodejs_package_json_error"] = str(e)

    # TODO: Add support for other common dependency files (pom.xml, build.gradle, Gemfile, etc.)

    if not found_any:
        return {"message": "No common dependency files (requirements.txt, package.json) found.", "path_checked": target_directory}
    
    return {"dependencies": dependencies, "path_checked": target_directory}


def filter_by_gitignore(target_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Filter a project structure based on gitignore rules (MCP-friendly).
    
    Args:
        target_directory: The root project directory containing .gitignore.
        tool_context: The ADK tool context.

    Returns:
        dict: Filtered project structure or error message.
    """
    logger.info(f"Filtering project structure by .gitignore in: {target_directory}")
    
    gitignore_path = os.path.join(target_directory, ".gitignore")
    matches_gitignore = None
    
    if os.path.exists(gitignore_path):
        try:
            # base_dir should be the directory containing the .gitignore file
            matches_gitignore = gitignore_parser.parse_gitignore(gitignore_path, base_dir=target_directory)
            logger.info(f"Successfully parsed .gitignore: {gitignore_path}")
        except Exception as e:
            logger.error(f"Error parsing .gitignore file at {gitignore_path}: {str(e)}")
            return {"error": f"Error parsing .gitignore: {str(e)}", "path_checked": target_directory}
    else:
        logger.info(f"No .gitignore file found in {target_directory}. No filtering will be applied based on it.")
        # If no .gitignore, create a dummy matcher that matches nothing, effectively keeping all files
        def no_match(_):
            return False
        matches_gitignore = no_match

    try:
        # IMPORTANT: get_project_structure needs to work relative to the actual files,
        # so we pass target_directory to it.
        initial_structure = get_project_structure(target_directory, tool_context) # Pass tool_context
        if "error" in initial_structure:
             return {"error": f"Could not get project structure for gitignore filtering: {initial_structure['error']}", "path_checked": target_directory}

        # Let's ensure paths used for matching are relative to the gitignore file's location (target_directory)
        def filter_recursive(current_struct: Dict[str, Any], current_path_from_target_root: str) -> Dict[str, Any]:
            filtered_struct = {"files": [], "directories": {}}
            
            # Filter files
            for file_name in current_struct.get("files", []):
                # Path relative to target_directory (where .gitignore is)
                relative_file_path = os.path.join(current_path_from_target_root, file_name)
                # gitignore_parser needs paths to be absolute if base_dir was used, or relative to CWD if not.
                # Since we used base_dir=target_directory, we should provide absolute paths for matching.
                absolute_file_path = os.path.join(target_directory, relative_file_path)
                if not matches_gitignore(absolute_file_path):
                    filtered_struct["files"].append(file_name)
            
            # Filter directories
            for dir_name, dir_content in current_struct.get("directories", {}).items():
                relative_dir_path = os.path.join(current_path_from_target_root, dir_name)
                absolute_dir_path = os.path.join(target_directory, relative_dir_path)

                if not matches_gitignore(absolute_dir_path):
                    # Recursively filter subdirectory content
                    filtered_struct["directories"][dir_name] = filter_recursive(
                        dir_content, 
                        relative_dir_path # Pass the updated relative path for the next level
                    )
            return filtered_struct

        # Start filtering from the root of the structure, with an empty relative path initially
        filtered_result = filter_recursive(initial_structure, "") 
        return {"filtered_structure": filtered_result, "gitignore_status": "applied" if os.path.exists(gitignore_path) else "not_found", "path_checked": target_directory}

    except Exception as e:
        logger.error(f"Error filtering by gitignore for {target_directory}: {str(e)}")
        return {"error": f"Error filtering by gitignore: {str(e)}", "path_checked": target_directory}

def apply_gitignore_filter(target_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Apply gitignore filtering to the project structure (MCP-friendly wrapper).
    
    Args:
        target_directory: The root project directory.
        tool_context: The ADK tool context.
        
    Returns:
        dict: Filtered project structure.
    """
    return filter_by_gitignore(target_directory, tool_context)

def search_codebase(
    target_directory: str,
    keywords: str, # comma-separated
    file_pattern: str = "*.*", # Glob pattern
    context_lines: int = 15,
    ignore_case: bool = True,
    tool_context: ToolContext | None = None
) -> Dict[str, Any]:
    """Search the codebase for keywords (MCP-friendly).
    
    Args:
        target_directory: The root directory to search within.
        keywords: Search terms (comma-separated).
        file_pattern: Glob pattern for files to search.
        context_lines: Number of lines before/after match.
        ignore_case: Whether to ignore case.
        tool_context: The ADK tool context.
        
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

def search_code_with_prompt(target_directory: str, prompt_text: str, file_pattern: str = "*.*", tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Search code using a prompt (MCP-friendly).
    Args:
        target_directory: The directory to search within.
        prompt_text: The user prompt to guide the search.
        file_pattern: Glob pattern for files to search (e.g., "*.py", "*.*" ).
        tool_context: The ADK tool context.
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
        ignore_case=True,    # Default to ignore case
        tool_context=tool_context # Pass tool_context
    )

def search_tests_with_prompt(target_directory: str, prompt_text: str, file_pattern: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Search test files using a prompt (MCP-friendly).
    Args:
        target_directory: The directory to search tests within.
        prompt_text: The user prompt to guide the test search.
        file_pattern: Glob pattern for test files to search (e.g., "*test*.py", "*.spec.js").
        tool_context: The ADK tool context.
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
        ignore_case=True,
        tool_context=tool_context # Pass tool_context
    )

def determine_relevance_from_prompt(prompt_text: str, found_files_context: List[Dict[str, Any]], tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """MCP Tool (Placeholder): Determine relevance of found files/matches based on a prompt.
    
    Args:
        prompt_text: The user's prompt.
        found_files_context: Contextual information about files/matches.
        tool_context: The ADK tool context.
        
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

def set_session_state(key: str, value_json_str: str, tool_context: ToolContext | None = None) -> Dict[str, str]:
    """Store a key-value pair in the session state. (MCP-friendly wrapper)
    
    Args:
        key: The key to store.
        value_json_str: The value to store, as a JSON-encoded string.
                        If the original value is a simple string, it can be passed directly
                        (it will be valid JSON if not containing special characters, or pass as a JSON string e.g. "mystring").
                        For dicts or lists, serialize to JSON first before calling this tool.
        tool_context: The ADK tool context.
        
    Returns:
        dict: A status message.
    """
    logger.info(f"MCP tool 'set_session_state' called for key: '{key}'")
    try:
        actual_value = json.loads(value_json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON for set_session_state key '{key}': {str(e)}")
        return {"status": "error", "message": f"Invalid JSON format for value: {str(e)}"}

    if tool_context and hasattr(tool_context, 'state'):
        try:
            tool_context.state[key] = actual_value
            logger.info(f"State set for key '{key}' via ToolContext.")
            return {"status": "success", "message": f"State successfully set for key '{key}'"}
        except Exception as e:
            logger.error(f"Error setting state via ToolContext for key '{key}': {str(e)}")
            return {"status": "error", "message": f"Failed to set state via ToolContext: {str(e)}"}
    else:
        logger.warning(f"ToolContext or tool_context.state not available for set_session_state key '{key}'. State not set.")
        # In a pure MCP scenario without agent state, this might just acknowledge.
        # However, ADK agents rely on this for their state.
        return {"status": "warning", "message": f"ToolContext or state not available. State for key '{key}' not set in ADK session."}


def get_session_state(key: str, default: Optional[Any] = None, tool_context: ToolContext | None = None) -> Any:
    """Get a value from the session state.
    
    Args:
        key: The state key to retrieve.
        default: The default value to return if the key is not found.
        tool_context: The ADK tool context.
    
    Returns:
        Any: The retrieved value or the default if the key is not found.
    """
    logger.info(f"MCP tool 'get_session_state' called for key: '{key}'")
    if tool_context and hasattr(tool_context, 'state'):
        value = tool_context.state.get(key, default)
        logger.info(f"Retrieved state for key '{key}' via ToolContext.")
        return value
    else:
        logger.warning(f"ToolContext or tool_context.state not available for get_session_state key '{key}'. Returning default.")
        return default 