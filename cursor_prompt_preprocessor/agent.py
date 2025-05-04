import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools import FunctionTool, ToolContext, LongRunningFunctionTool
from typing import Optional, Generator, Any
import glob
import os
import gitignore_parser
import re
import time
import threading
from collections import deque
from functools import wraps
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
import logging
import logging.handlers
import sys

# Configure logging
def setup_logging():
    """Set up logging to file and console with proper formatting."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'cursor_preprocessor_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')
    
    # File handler for detailed logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    # Console handler for regular output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # Redirect stdout and stderr to the logger
    sys.stdout = LoggerWriter(logger.info)
    sys.stderr = LoggerWriter(logger.error)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger

class LoggerWriter:
    """File-like object to redirect stdout/stderr to logger."""
    
    def __init__(self, writer_func):
        self.writer_func = writer_func
        self.buffer = ''
        
    def write(self, message):
        if message and not message.isspace():
            self.writer_func(message.rstrip())
            
    def flush(self):
        pass

# Set up logging
logger = setup_logging()

# Load environment variables from .env file
load_dotenv()

APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "demo_user"
SESSION_ID = "demo_session"

# Create session service and session
session_service = InMemorySessionService()
_session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

# Rate limiter implementation for LLM calls
class RateLimiter:
    """Rate limiter for API calls that enforces a maximum number of calls per minute.
    
    Thread-safe implementation using a sliding window approach.
    """
    def __init__(self, max_calls_per_minute=10):
        self.max_calls = max_calls_per_minute
        self.window_seconds = 60  # 1 minute
        self.call_history = deque(maxlen=max_calls_per_minute)
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        logger.info(f"Rate limiter initialized: {max_calls_per_minute} calls per minute")
    
    def wait_if_needed(self):
        """Blocks until a call can be made without exceeding the rate limit."""
        with self.lock:
            current_time = time.time()
            
            # If we haven't reached the max calls yet, allow immediately
            if len(self.call_history) < self.max_calls:
                self.call_history.append(current_time)
                return
            
            # Check if the oldest call is outside our window
            oldest_call_time = self.call_history[0]
            time_since_oldest = current_time - oldest_call_time
            
            # If we've used all our quota and need to wait
            if time_since_oldest < self.window_seconds:
                wait_time = self.window_seconds - time_since_oldest + 0.1  # Add a small buffer
                logger.info(f"Rate limit reached. Waiting for {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                # After waiting, current time has changed
                current_time = time.time()
            
            # Update our history
            self.call_history.popleft()
            self.call_history.append(current_time)

# Create a global rate limiter instance
rate_limiter = RateLimiter(max_calls_per_minute=10)

# Callback to handle 429 rate limit errors
def handle_rate_limit(callback_context, llm_response):
    """After-model callback to handle rate limit errors.
    
    Args:
        callback_context: The callback context
        llm_response: The LLM response
        
    Returns:
        Modified response if rate limit was hit, None otherwise
    """
    # Check if there's an error in the response
    error = getattr(llm_response, 'error', None)
    if error and "429" in str(error):
        logger.warning(f"Rate limit error detected: {error}")
        
        # Extract retry delay if provided in the error message
        retry_delay = 5  # Default 5 seconds
        delay_match = re.search(r"'retryDelay': '(\d+)s'", str(error))
        if delay_match:
            retry_delay = int(delay_match.group(1))
            
        # Wait before retrying
        logger.info(f"Rate limit hit, waiting for {retry_delay} seconds before retry...")
        time.sleep(retry_delay + 1)  # Add 1 second buffer
        
        # Create a modified response indicating we'll retry
        from google.genai import types
        return types.Content(
            role="model",
            parts=[types.Part(text="Rate limit hit, retrying after delay...")]
        )
    
    # If no rate limit error, return None to use the original response
    return None

# Pre-model callback to enforce rate limiting before making requests
def pre_model_rate_limit(callback_context, llm_request):
    """Pre-model callback to enforce rate limiting before making API calls.
    
    Args:
        callback_context: The callback context
        llm_request: The LLM request parameters
        
    Returns:
        None to continue with the normal request, or a response to short-circuit
    """
    # Apply rate limiting before making the request
    try:
        logger.info("Pre-model rate limit check")
        rate_limiter.wait_if_needed()
        return None  # Continue with normal request
    except Exception as e:
        logger.error(f"Error in pre-model rate limit check: {e}")
        # If there's an error in rate limiting, create a fallback response
        from google.genai import types
        return types.Content(
            role="model", 
            parts=[types.Part(text="Error in rate limiting, please try again.")]
        )

# Patch all LlmAgent instantiations to include both callbacks
def create_rate_limited_agent(name, model, instruction, tools=None, output_key=None, sub_agents=None):
    """Factory function to create LlmAgents with rate limiting.
    
    Ensures all agents have proper rate limiting applied.
    
    Args:
        name: Agent name
        model: Model name
        instruction: Agent instructions
        tools: List of tools
        output_key: Output state key
        sub_agents: List of sub-agents
    
    Returns:
        LlmAgent with rate limiting applied
    """
    return LlmAgent(
        name=name,
        model=model,
        instruction=instruction,
        tools=tools or [],
        output_key=output_key,
        sub_agents=sub_agents or [],
        before_model_callback=pre_model_rate_limit,
        after_model_callback=handle_rate_limit
    )

def set_global_session(session):
    """Set the global session variable for use in tools."""
    global _session
    _session = session

# --- State Keys ---
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
STATE_TARGET_DIRECTORY = "target_directory"  # New state key for target directory
STATE_NEEDS_ANSWERS = "needs_answers"  # New state key to track if we need answers

APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "dev_user_01"
SESSION_ID = "session_01"
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

# Prompt exact states = "no questions"

NO_QUESTIONS = "no questions ABSOLUTELY"

# --- Tools ---

def get_project_structure(directory) -> dict:
    """Scans the project directory and returns its structure.

    Args:
        directory: The directory to scan. Use "." for current directory.

    Returns:
        dict: A dictionary representation of the project structure.
    """
    # Handle default value internally instead of in the parameter
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
        return {"error": str(e)}

def get_target_directory_from_state() -> str:
    """Utility function to get the target directory from the session state.
    
    Returns:
        str: The target directory path, or "." if not set.
    """
    global _session
    if _session and STATE_TARGET_DIRECTORY in _session.state:
        return _session.state[STATE_TARGET_DIRECTORY]
    return "."

def scan_project_structure() -> dict:
    """Wrapper function to scan the project structure.
    
    Uses the target directory from the session state if available.
    
    Returns:
        dict: A dictionary representation of the project structure.
    """
    target_dir = get_target_directory_from_state()
    return get_project_structure(target_dir)

def get_dependencies() -> dict:
    """Analyzes project dependencies from requirements.txt, package.json, etc.
    
    Uses the target directory from the session state if available.

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
        import json
        with open(pkg_path, "r") as file:
            try:
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

def filter_by_gitignore() -> dict:
    """Filters the project structure based on gitignore rules.
    
    Uses the target directory from the session state if available.

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
        return {"error": f"Error filtering by gitignore: {str(e)}"}

def set_target_directory(directory: str) -> dict:
    """Sets the target directory for code analysis.
    
    Args:
        directory: The directory path to analyze.
        
    Returns:
        dict: A confirmation message.
    """
    global _session
    if _session:
        _session.state[STATE_TARGET_DIRECTORY] = directory
        logger.info(f"Target directory set to: {directory}")
    else:
        logger.error("No session found when setting target directory")
    
    return {
        "status": "success", 
        "message": f"Set target directory to: {directory}", 
        "directory": directory
    }

def apply_gitignore_filter() -> dict:
    """Wrapper function to apply gitignore filtering with no parameters.
    
    Returns:
        dict: Filtered project structure.
    """
    return filter_by_gitignore()

def search_code_with_prompt() -> dict:
    """Wrapper function to search code using the prompt from the session state.
    
    This function doesn't take parameters to avoid automatic function calling issues.
    It retrieves the user prompt from the session state and uses it to search for code.
    
    Returns:
        dict: Dictionary of files and matching lines.
    """
    # Since we can't access the session state directly here, we return a message
    # instructing the agent to use the prompt from the state
    return {"message": "NOT IMPLEMENTED; ASK USER TO IMPLEMENT CODE SEARCH IF YOU ENCOUNTER THIS MESSAGE"}

def search_tests_with_prompt() -> dict:
    """Wrapper function to search test files using the prompt from the session state.
    
    This function doesn't take parameters to avoid automatic function calling issues.
    It retrieves the user prompt from the session state and uses it to search for test files.
    
    Returns:
        dict: Dictionary of files and matching lines.
    """
    # Since we can't access the session state directly here, we return a message
    # instructing the agent to use the prompt from the state
    return {"message": "NOT IMPLEMENTED; ASK USER TO IMPLEMENT TEST SEARCH IF YOU ENCOUNTER THIS MESSAGE"}

def determine_relevance_from_prompt() -> dict:
    """Wrapper function to determine relevance of code files based on the session state.
    
    This function doesn't take parameters to avoid automatic function calling issues.
    
    Returns:
        dict: Instructions for determining relevance.
    """
    return {
        "message": "Analyze the code and test files found based on the user's prompt. Rank them by relevance and explain why they might be useful for the task."
    }

def set_state(key: str, value: str) -> dict:
    """Utility function for agents to set values in the session state.
    
    Args:
        key: The state key to set
        value: The value to store
    
    Returns:
        dict: Confirmation of the operation
    """
    return {"status": "success", "message": f"Stored value in state key '{key}'", "key": key}

def read_file_content(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> dict:
    """Read the contents of a file, optionally specifying line ranges.
    
    This function reads a file's contents and can return either the entire file
    or a specific range of lines. It includes safety checks and proper error handling.
    
    Args:
        file_path: Path to the file to read (absolute or relative to workspace)
        start_line: Optional 1-based start line number (inclusive)
        end_line: Optional 1-based end line number (inclusive)
        
    Returns:
        dict: A dictionary containing:
            - content: The file contents as a string
            - line_count: Total number of lines in the file
            - start_line: Actual start line read (1-based)
            - end_line: Actual end line read (1-based)
            - error: Error message if any occurred
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


def list_directory_contents(path: str = ".", include_hidden: bool = False) -> dict:
    """List contents of a directory with detailed information.
    
    This function provides a detailed listing of directory contents, including
    files and subdirectories, with additional metadata like size and type.
    
    Args:
        path: Path to list (relative or absolute). If None, uses target directory
        include_hidden: Whether to include hidden files/directories (default: False)
        
    Returns:
        dict: A dictionary containing:
            - files: List of file information dictionaries
            - directories: List of directory information dictionaries
            - current_path: Absolute path that was listed
            - error: Error message if any occurred
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

def search_codebase(
    keywords: str,
    file_pattern: str = "*.*",
    context_lines: int = 15,
    ignore_case: bool = True
) -> dict:
    """Search the codebase for keywords and return matches with context.
    
    Performs a grep-like search across files in the target directory,
    returning matches with surrounding context lines.
    
    Args:
        keywords: Search terms (comma-separated) or single keyword/regex pattern
        file_pattern: Glob pattern for files to search (default: all files)
        context_lines: Number of lines before/after match to include (default: 15)
        ignore_case: Whether to ignore case in search (default: True)
        
    Returns:
        dict: A dictionary containing:
            - matches: List of match information dictionaries
            - total_matches: Total number of matches found
            - error: Error message if any occurred
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
                                    "matched_keyword": keyword  # Add which keyword matched
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
            "search_terms": keyword_list,  # Return the list of keywords used
            "file_pattern": file_pattern,
            "context_lines": context_lines
        }
        
    except Exception as e:
        logger.error(f"Error during codebase search: {str(e)}")
        return {"error": f"Failed to search codebase: {str(e)}"}
    
class ClarifierGenerator:
    '''Synchronous function to get console input for clarification.'''
    __name__ = "clarify_questions_tool" # Name remains the same for agent instructions

    def __call__(self) -> dict:
        # Get the question from the state
        question_to_ask = _session.state.get(STATE_QUESTIONS, "Could you please provide clarification? (Error: Question not found in state)")
        
        # Prompt the user directly in the console where the agent is running
        print("--- CONSOLE INPUT REQUIRED ---")
        human_reply = input(f"{question_to_ask}: ")
        print("--- CONSOLE INPUT RECEIVED ---")
        
        # Return the received input
        return {"reply": human_reply}

# Change to standard FunctionTool wrapping the console-input function
clarify_questions_tool = FunctionTool(func=ClarifierGenerator())

# --- LLM Agents ---

# Project Structure Agent
project_structure_agent = create_rate_limited_agent(
    name="ProjectStructureAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Project Structure Analyzer.
    Your task is to scan the project directory structure provided in the session state
    and summarize the key components and organization of the project.
    
    Focus on identifying:
    1. Main source code directories
    2. Test directories
    3. Configuration files
    4. Documentation
    5. Resource files
    
    Format your response as a structured summary that would help a developer understand
    the project's organization. Focus only on important aspects of the structure that would
    help with understanding the codebase.
    """,
    tools=[FunctionTool(func=scan_project_structure)],
    output_key=STATE_PROJECT_STRUCTURE
)

# Dependency Analysis Agent
dependency_analysis_agent = create_rate_limited_agent(
    name="DependencyAnalysisAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Dependency Analyzer.
    Your task is to analyze the project dependencies from the session state and provide insights
    about the technologies and frameworks used in the project.
    
    Focus on:
    1. Identifying the main frameworks/libraries
    2. Noting any version constraints
    3. Recognizing patterns in the dependencies that indicate the project type
    4. Flagging any potential issues (outdated dependencies, etc.)
    
    Format your response as a concise analysis that would help a developer understand
    the technological stack of the project.
    """,
    tools=[FunctionTool(func=list_directory_contents),
           FunctionTool(func=read_file_content)],
    output_key=STATE_DEPENDENCIES
)

# Gitignore Filter Agent
gitignore_filter_agent = create_rate_limited_agent(
    name="GitignoreFilterAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Gitignore Filter.
    Your task is to filter the project structure based on the project's gitignore rules.
    This helps focus on relevant code files and exclude build artifacts, caches, etc.
    
    Call the apply_gitignore_filter function to get the filtered project structure.
    
    Return the filtered project structure showing only the files and directories that
    would typically be relevant for understanding the codebase.
    """,
    tools=[FunctionTool(func=apply_gitignore_filter),
           FunctionTool(func=read_file_content)],
    output_key=STATE_FILTERED_STRUCTURE
)

# Code Search Agent
code_search_agent = create_rate_limited_agent(
    name="CodeSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}'n the state key '{STATE_FILTERED_STRUCTURE}'

    and use them to find relevant code files in the project, given the code structure in the state key {STATE_FILTERED_STRUCTURE}.
    
    1. Please extract keywords from the user prompt in the session state and use them to search the codebase. You can also pass the raw prompt to help with keyword extraction.
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant code files using tool search_code_with_prompt()
    
    Format your response as a clear summary of the most relevant code locations.
    """,
    tools=[FunctionTool(func=search_code_with_prompt)
           ,FunctionTool(func=read_file_content),
           FunctionTool(func=list_directory_contents)], # todo: add search tool impl
    output_key=STATE_RELEVANT_CODE
)

# Test Search Agent
test_search_agent = create_rate_limited_agent(
    name="TestSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}' and use them to find relevant test files in the project, given the code structure in the state key {STATE_FILTERED_STRUCTURE}.
    
    1. Please extract keywords from the user prompt in the session state and use them to search the test files. You can also pass the raw prompt to help with keyword extraction.
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant test files using tool search_tests_with_prompt()
    
    Format your response as a clear summary of the most relevant test file locations.
    """,
    tools=[FunctionTool(func=search_code_with_prompt)
           ,FunctionTool(func=read_file_content),
           FunctionTool(func=list_directory_contents)], # todo: add search tool impl
    output_key=STATE_RELEVANT_TESTS
)

# Relevance Determination Agent
relevance_determination_agent = create_rate_limited_agent(
    name="RelevanceDeterminationAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Relevance Analyst.
    Your task is to analyze the code and test files found from the session state
    ('{STATE_RELEVANT_CODE}' and '{STATE_RELEVANT_TESTS}') and determine their
    relevance to the user's prompt ('{STATE_USER_PROMPT}').
    
    First, call determine_relevance_from_prompt() to get instructions.
    
    Then:
    1. Analyze the found code and test files in relation to the user's prompt
    2. Assign relevance scores or rankings
    3. Explain the rationale for the most relevant files
    
    Format your response as a ranked list with explanations for why each top file is relevant.
    """,
    tools=[FunctionTool(func=determine_relevance_from_prompt)],
    output_key=STATE_RELEVANCE_SCORES
)

# Question Asking Agent
question_asking_agent = create_rate_limited_agent(
    name="QuestionAskingAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Clarifying Question Generator.
    Your task is to analyze the user's prompt from the state key '{STATE_USER_PROMPT}'
    along with the project information gathered so far, and generate clarifying questions
    when the prompt is ambiguous or lacks necessary details.
    
    The questions should help pinpoint exactly what the user needs in terms of code implementation.


    1. Identify unclear aspects or missing information in the prompt. Use the structure of the project to help you understand the user's prompt.
    Use read_file_content() tool to clarify your doubts about the existing code before aszking the user.
    2. Formulate 1-3 specific, targeted questions to clarify these aspects
    3. If you have questions to ask, respond with the questions you have.
    4. If the prompt is completely clear and has sufficient information, respond EXACTLY with the string "{NO_QUESTIONS}"

    """,
    tools=[FunctionTool(func=read_file_content)],
    output_key=STATE_QUESTIONS
)

# User Answer Collection Agent
user_answer_collection_agent = create_rate_limited_agent(
    name="UserAnswerCollectionAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a User Answer Collector.
    Your task is based on the content of the state key '{STATE_QUESTIONS}':
    
    1. Check if the value in '{STATE_QUESTIONS}' is EXACTLY the string "{NO_QUESTIONS}".
    2. Report clearly: State whether questions were found or not.
    3. If questions exist (i.e., the state is NOT "{NO_QUESTIONS}"):
        a. Announce that you will now ask for clarification via the console tool, showing the question stored in the state.
        b. Use the `clarify_questions_tool` to get console input.
        c. Retrieve the current list of answers from the state key '{STATE_ANSWERS}' 
        d. Append the new 'reply' received from the tool to this list.
        e. Call `set_state` to store the updated list back into the '{STATE_ANSWERS}' state key.
    4. If no questions exist (i.e., the state IS "{NO_QUESTIONS}"):
        a. Announce that no clarification is needed and the loop should terminate.
        b. Respond EXACTLY with the string "NO_CLARIFICATION_NEEDED_EXIT_LOOP"
        
    Ensure you handle the state correctly, especially creating the list for '{STATE_ANSWERS}' if it's the first answer.
    """,
    tools=[
        clarify_questions_tool, # This is now a FunctionTool
        FunctionTool(func=set_state) # Added get_state to retrieve current answers
    ],
    output_key=STATE_ANSWERS
)

# Context Formation Agent
context_formation_agent = create_rate_limited_agent(
    name="ContextFormationAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Context Formation Specialist.
    Your task is to synthesize all the information gathered in the previous steps into
    a comprehensive context object that will be used for code generation.
    
    Compile a structured context that includes:
    1. The user's prompt (from '{STATE_USER_PROMPT}')
    2. Relevant project structure information (from '{STATE_PROJECT_STRUCTURE}')
    3. Key dependencies (from '{STATE_DEPENDENCIES}')
    4. The most relevant code files and snippets (from '{STATE_RELEVANT_CODE}')
    5. The most relevant test files (from '{STATE_RELEVANT_TESTS}')
    6. Any clarifying questions and their answers (from '{STATE_QUESTIONS}' and '{STATE_ANSWERS}')
    
    Format your response as a well-structured context object with clear sections that a code
    generation system would find helpful for understanding what needs to be implemented.
    """,
    output_key=STATE_FINAL_CONTEXT
)

# --- Main Agent Pipeline ---

# Parallel agent for search operations
parallel_search_agent = ParallelAgent(
    name="ParallelSearchAgent",
    sub_agents=[code_search_agent, test_search_agent]
)

structure_and_dependencies_agent = SequentialAgent(
    name="StructureAndDependencies",
    sub_agents=[
        project_structure_agent, 
        dependency_analysis_agent,
        gitignore_filter_agent
    ]
)

clarification_and_decision_loop = LoopAgent(
    name="ClarificationAndDecisionLoop",
    sub_agents=[
        parallel_search_agent,
        relevance_determination_agent,
        question_asking_agent,
        user_answer_collection_agent
    ], 
    max_iterations=3
)

# Create the sequential pipeline with question-answer capability
context_former = SequentialAgent(
    name="ContextFormer",
    sub_agents=[
        structure_and_dependencies_agent,
        clarification_and_decision_loop,
        context_formation_agent
    ]
)

# The root agent is the entry point for the user prompt
root_agent = create_rate_limited_agent(
    name="PromptProcessor",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the main coordinator for processing coding prompts.
    
    Your first task is to:
    1. Welcome the user
    2. Store their coding prompt in the session state with key '{STATE_USER_PROMPT}' using the set_state tool
    3. If a target directory was provided, acknowledge it
    4. Transfer control to the ContextFormer agent
    
    Be sure to always store the user's coding prompt in the state key '{STATE_USER_PROMPT}' before proceeding.
    
    After the ContextFormer has completed, you should:
    1. Retrieve the final context from the session state
    2. Present a concise summary of what was found and how it will help with the code generation
    
    Keep your responses friendly, professional, and focused on helping the user succeed with their coding task.
    """,
    tools=[FunctionTool(func=set_state), FunctionTool(func=set_target_directory)],
    sub_agents=[context_former]
)