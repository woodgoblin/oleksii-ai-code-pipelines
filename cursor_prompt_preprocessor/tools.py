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
from cursor_prompt_preprocessor.logging_setup import logger
from cursor_prompt_preprocessor.session import session_manager

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


# --- File System Tools ---

def get_target_directory_from_state() -> str:
    """Get the target directory from the session state.
    
    Returns:
        str: The target directory path, or "." if not set.
    """
    return session_manager.get_state(STATE_TARGET_DIRECTORY, ".")

def get_project_structure(directory: str = None) -> Dict[str, Any]:
    """Scan a directory and return its structure recursively.

    Args:
        directory: The directory to scan. Uses "." if None or empty.

    Returns:
        dict: A dictionary representation of the project structure.
    """
    # Handle default value
    if directory is None or directory == "":
        directory = "."
        
    structure = {"files": [], "directories": {}}
    try:
        items = os.listdir(directory)
        for item in items:
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                structure["files"].append(item)
            elif os.path.isdir(item_path) and not item.startswith("."):
                structure["directories"][item] = get_project_structure(item_path)
        return structure
    except Exception as e:
        logger.error(f"Error getting project structure for {directory}: {str(e)}")
        return {"error": str(e)}

def scan_project_structure() -> Dict[str, Any]:
    """Scan the target directory's structure.
    
    Uses the target directory from the session state.
    
    Returns:
        dict: A dictionary representation of the project structure.
    """
    target_dir = get_target_directory_from_state()
    return get_project_structure(target_dir)

def set_target_directory(directory: str) -> Dict[str, str]:
    """Set the target directory for code analysis.
    
    Args:
        directory: The directory path to analyze.
        
    Returns:
        dict: A confirmation message.
    """
    result = session_manager.set_state(STATE_TARGET_DIRECTORY, directory)
    logger.info(f"Target directory set to: {directory}")
    return {
        "status": "success", 
        "message": f"Set target directory to: {directory}", 
        "key": STATE_TARGET_DIRECTORY,
        "directory": directory
    }

def list_directory_contents(path: str = ".", include_hidden: bool = False) -> Dict[str, Any]:
    """List contents of a directory with detailed information.
    
    This function provides a detailed listing of directory contents, including
    files and subdirectories, with additional metadata like size and type.
    
    Args:
        path: Path to list (relative or absolute). If None, uses target directory
        include_hidden: Whether to include hidden files/directories (default: False)
        
    Returns:
        dict: Directory contents with metadata
    """
    try:
        # Handle default path
        if path is None or path == "":
            path = get_target_directory_from_state()
            
        # Convert relative path to absolute if needed
        if not os.path.isabs(path):
            base_dir = get_target_directory_from_state()
            path = os.path.join(base_dir, path)
            
        # Check if path exists
        if not os.path.exists(path):
            return {"error": f"Path not found: {path}"}
        if not os.path.isdir(path):
            return {"error": f"Path is not a directory: {path}"}
            
        files = []
        directories = []
        
        # List directory contents
        for entry in os.scandir(path):
            # Skip hidden files/directories unless explicitly requested
            if not include_hidden and entry.name.startswith('.'):
                continue
                
            try:
                stats = entry.stat()
                info = {
                    "name": entry.name,
                    "path": entry.path,
                    "size": stats.st_size,
                    "modified": datetime.datetime.fromtimestamp(
                        stats.st_mtime,
                        tz=ZoneInfo("UTC")
                    ).isoformat(),
                    "created": datetime.datetime.fromtimestamp(
                        stats.st_ctime,
                        tz=ZoneInfo("UTC")
                    ).isoformat()
                }
                
                if entry.is_file():
                    info["type"] = "file"
                    files.append(info)
                elif entry.is_dir():
                    info["type"] = "directory"
                    directories.append(info)
                    
            except Exception as e:
                logger.warning(f"Error getting info for {entry.path}: {str(e)}")
                # Continue with next entry if one fails
                continue
        
        return {
            "files": sorted(files, key=lambda x: x["name"]),
            "directories": sorted(directories, key=lambda x: x["name"]),
            "current_path": path,
            "total_files": len(files),
            "total_directories": len(directories)
        }
        
    except Exception as e:
        logger.error(f"Error listing directory {path}: {str(e)}")
        return {"error": f"Failed to list directory: {str(e)}"}

def read_file_content(
    file_path: str, 
    start_line: Optional[int] = None, 
    end_line: Optional[int] = None
) -> Dict[str, Any]:
    """Read the contents of a file, optionally specifying line ranges.
    
    This function reads a file's contents and can return either the entire file
    or a specific range of lines. It includes safety checks and proper error handling.
    
    Args:
        file_path: Path to the file to read (absolute or relative to workspace)
        start_line: Optional 1-based start line number (inclusive)
        end_line: Optional 1-based end line number (inclusive)
        
    Returns:
        dict: File content and metadata
    """
    try:
        # Convert relative path to absolute if needed
        if not os.path.isabs(file_path):
            target_dir = get_target_directory_from_state()
            file_path = os.path.join(target_dir, file_path)
            
        # Basic security checks
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        if not os.path.isfile(file_path):
            return {"error": f"Path is not a file: {file_path}"}
            
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        
        # Handle line range parameters
        if start_line is None:
            start_line = 1
        if end_line is None:
            end_line = total_lines
            
        # Validate line numbers
        start_line = max(1, min(start_line, total_lines))
        end_line = max(start_line, min(end_line, total_lines))
        
        # Extract the requested lines (convert to 0-based indexing)
        content = ''.join(lines[start_line - 1:end_line])
        
        return {
            "content": content,
            "line_count": total_lines,
            "start_line": start_line,
            "end_line": end_line,
            "file_path": file_path
        }
        
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return {"error": f"Failed to read file: {str(e)}"}


# --- Project Analysis Tools ---

def get_dependencies() -> Dict[str, Any]:
    """Analyze project dependencies from requirements.txt, package.json, etc.
    
    Uses the target directory from the session state.

    Returns:
        dict: A dictionary of project dependencies and their versions.
    """
    target_dir = get_target_directory_from_state()
    dependencies = {}
    
    # Check for Python requirements.txt
    req_path = os.path.join(target_dir, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, "r") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(">=")
                    if len(parts) > 1:
                        dependencies[parts[0]] = parts[1]
                    else:
                        parts = line.split("==")
                        if len(parts) > 1:
                            dependencies[parts[0]] = parts[1]
                        else:
                            dependencies[line] = "latest"
    
    # Check for package.json (Node.js)
    pkg_path = os.path.join(target_dir, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r") as file:
                package_data = json.load(file)
                if "dependencies" in package_data:
                    for dep, version in package_data["dependencies"].items():
                        dependencies[dep] = version
                if "devDependencies" in package_data:
                    for dep, version in package_data["devDependencies"].items():
                        dependencies[dep] = version
        except json.JSONDecodeError:
            dependencies["error"] = "Invalid package.json format"
    
    return dependencies

def filter_by_gitignore() -> Dict[str, Any]:
    """Filter the project structure based on gitignore rules.
    
    Uses the target directory from the session state.

    Returns:
        dict: Filtered project structure.
    """
    try:
        target_dir = get_target_directory_from_state()
        structure = get_project_structure(target_dir)
        
        # Check if .gitignore exists in the target directory
        gitignore_path = os.path.join(target_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            return structure
        
        # Parse gitignore
        matches = gitignore_parser.parse_gitignore(gitignore_path)
        
        # Helper function to filter structure
        def filter_structure(struct, path=""):
            filtered = {"files": [], "directories": {}}
            
            for file in struct["files"]:
                file_path = os.path.join(path, file)
                if not matches(file_path):
                    filtered["files"].append(file)
            
            for dir_name, dir_struct in struct["directories"].items():
                dir_path = os.path.join(path, dir_name)
                if not matches(dir_path):
                    filtered["directories"][dir_name] = filter_structure(dir_struct, dir_path)
            
            return filtered
        
        return filter_structure(structure)
    except Exception as e:
        # If there's an error, return an error message
        logger.error(f"Error filtering by gitignore: {str(e)}")
        return {"error": f"Error filtering by gitignore: {str(e)}"}

def apply_gitignore_filter() -> Dict[str, Any]:
    """Apply gitignore filtering to the project structure.
    
    Returns:
        dict: Filtered project structure.
    """
    return filter_by_gitignore()

def search_codebase(
    keywords: str,
    file_pattern: str = "*.*",
    context_lines: int = 15,
    ignore_case: bool = True
) -> Dict[str, Any]:
    """Search the codebase for keywords with surrounding context.
    
    Args:
        keywords: Search terms (comma-separated) or single keyword/regex pattern
        file_pattern: Glob pattern for files to search (default: all files)
        context_lines: Number of lines before/after match to include (default: 15)
        ignore_case: Whether to ignore case in search (default: True)
        
    Returns:
        dict: Search results with matches and context
    """
    try:
        target_dir = get_target_directory_from_state()
        matches = []
        total_matches = 0
        
        # Process keywords
        if ',' in keywords:
            # Split on commas and clean up whitespace
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
        else:
            keyword_list = [keywords.strip()]
            
        logger.info(f"Searching for keywords: {keyword_list}")
        
        # Get all files matching the pattern
        for root, _, files in os.walk(target_dir):
            for file in files:
                if not glob.fnmatch.fnmatch(file, file_pattern):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    # Search through lines
                    for i, line in enumerate(lines):
                        # Check each keyword
                        for keyword in keyword_list:
                            if (ignore_case and keyword.lower() in line.lower()) or \
                               (not ignore_case and keyword in line):
                                # Calculate context range
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                
                                # Get context lines
                                context_before = ''.join(lines[start:i]).rstrip()
                                match_line = lines[i].rstrip()
                                context_after = ''.join(lines[i+1:end]).rstrip()
                                
                                # Create match entry
                                match = {
                                    "file_path": file_path,
                                    "line_number": i + 1,  # 1-based line numbering
                                    "context_before": context_before,
                                    "match_line": match_line,
                                    "context_after": context_after,
                                    "context_start": start + 1,  # 1-based line numbers
                                    "context_end": end,
                                    "matched_keyword": keyword
                                }
                                matches.append(match)
                                total_matches += 1
                                # Break inner loop as we already found a match for this line
                                break
                                
                except Exception as e:
                    logger.warning(f"Error searching file {file_path}: {str(e)}")
                    continue
        
        # Sort matches by file path and line number
        matches.sort(key=lambda x: (x["file_path"], x["line_number"]))
        
        return {
            "matches": matches,
            "total_matches": total_matches,
            "search_terms": keyword_list,
            "file_pattern": file_pattern,
            "context_lines": context_lines
        }
        
    except Exception as e:
        logger.error(f"Error during codebase search: {str(e)}")
        return {"error": f"Failed to search codebase: {str(e)}"}

# --- Agent Assistance Tools ---

def search_code_with_prompt() -> Dict[str, Any]:
    """Search code using the prompt from the session state.
    
    This is a placeholder that would ideally be implemented with more specific logic.
    
    Returns:
        dict: Dictionary of files and matching lines.
    """
    return {"message": "NOT IMPLEMENTED; ASK USER TO IMPLEMENT CODE SEARCH IF YOU ENCOUNTER THIS MESSAGE"}

def search_tests_with_prompt() -> Dict[str, Any]:
    """Search test files using the prompt from the session state.
    
    This is a placeholder that would ideally be implemented with more specific logic.
    
    Returns:
        dict: Dictionary of files and matching lines.
    """
    return {"message": "NOT IMPLEMENTED; ASK USER TO IMPLEMENT TEST SEARCH IF YOU ENCOUNTER THIS MESSAGE"}

def determine_relevance_from_prompt() -> Dict[str, Any]:
    """Determine relevance of code files based on the session state.
    
    Returns:
        dict: Instructions for determining relevance.
    """
    return {
        "message": "Analyze the code and test files found based on the user's prompt. "
                  "Rank them by relevance and explain why they might be useful for the task."
    }

def set_state(key: str, value: str) -> Dict[str, str]:
    """Set a value in the session state.
    
    Args:
        key: The state key to set
        value: The value to store
    
    Returns:
        dict: Result information about the operation
    """
    result = session_manager.set_state(key, value)
    return {
        "status": result["status"], 
        "message": result["message"],
        "key": result["key"]
    } 