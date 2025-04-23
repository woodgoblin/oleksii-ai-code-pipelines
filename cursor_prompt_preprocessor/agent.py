import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools import FunctionTool
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
    return {"message": "Please extract keywords from the user prompt in the session state and use them to search the codebase. You can also pass the raw prompt to help with keyword extraction."}

def search_tests_with_prompt() -> dict:
    """Wrapper function to search test files using the prompt from the session state.
    
    This function doesn't take parameters to avoid automatic function calling issues.
    It retrieves the user prompt from the session state and uses it to search for test files.
    
    Returns:
        dict: Dictionary of test files and matching lines.
    """
    # Since we can't access the session state directly here, we return a message
    # instructing the agent to use the prompt from the state
    return {"message": "Please extract keywords from the user prompt in the session state and use them to search the test files. You can also pass the raw prompt to help with keyword extraction."}

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

def collect_user_answers(answers: str) -> dict:
    """Collect answers from the user to the clarifying questions.
    
    Args:
        answers: The user's answers to the clarifying questions
        
    Returns:
        dict: Confirmation of the operation
    """
    return {
        "status": "success",
        "message": "Collected user's answers to clarifying questions",
        "answers": answers
    }

def check_questions_exist() -> dict:
    """Check if there are any questions that need answers.
    
    Returns:
        dict: Information about whether questions exist and need answers
    """
    global _session
    if _session and STATE_QUESTIONS in _session.state:
        questions = _session.state[STATE_QUESTIONS]
        logger.info(f"Found questions in session state: {questions}")
        
        # Handle different types of question formats
        if isinstance(questions, str):
            # For string type questions
            if questions and "no questions" not in questions.lower():
                logger.info("Detected string type questions")
                return {"has_questions": True, "questions": questions}
        elif isinstance(questions, list):
            # For list/array type questions
            if questions and len(questions) > 0:
                logger.info(f"Detected list type questions with {len(questions)} items")
                return {"has_questions": True, "questions": questions}
        elif isinstance(questions, dict):
            # For dictionary type questions
            if "questions" in questions and questions["questions"]:
                logger.info("Detected dictionary type questions")
                return {"has_questions": True, "questions": questions["questions"]}
    
    logger.info("No questions found or needed")
    return {"has_questions": False}

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
    tools=[FunctionTool(func=get_dependencies)],
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
    tools=[FunctionTool(func=apply_gitignore_filter)],
    output_key=STATE_FILTERED_STRUCTURE
)

# Code Search Agent
code_search_agent = create_rate_limited_agent(
    name="CodeSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}'
    and use them to find relevant code files in the project.
    
    1. First, call search_code_with_prompt() to get instructions for searching
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant code files
    
    Format your response as a clear summary of the most relevant code locations.
    """,
    tools=[FunctionTool(func=search_code_with_prompt)],
    output_key=STATE_RELEVANT_CODE
)

# Test Search Agent
test_search_agent = create_rate_limited_agent(
    name="TestSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}'
    and use them to find relevant test files in the project.
    
    1. First, call search_tests_with_prompt() to get instructions for searching
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant test files
    
    Format your response as a clear summary of the most relevant test files that could
    help understand how the components in question are tested.
    """,
    tools=[FunctionTool(func=search_tests_with_prompt)],
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
    
    1. Identify unclear aspects or missing information in the prompt
    2. Formulate 1-3 specific, targeted questions to clarify these aspects
    3. If the prompt is completely clear and has sufficient information, state that no questions are needed
    
    The questions should help pinpoint exactly what the user needs in terms of code implementation.
    Format your response as a list of questions only, or "No questions needed." if appropriate.
    """,
    tools=[FunctionTool(func=check_questions_exist)],
    output_key=STATE_QUESTIONS
)

# User Answer Collection Agent
user_answer_collection_agent = create_rate_limited_agent(
    name="UserAnswerCollectionAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a User Answer Collector.
    Your task is to:
    
    1. Check if there are any clarifying questions in the state key '{STATE_QUESTIONS}'
    2. If questions exist, STOP THE PIPELINE and display them DIRECTLY to the user
    3. Wait for the user's responses and collect them
    4. Store the user's answers in the state key '{STATE_ANSWERS}'
    
    IMPORTANT: The user MUST see the questions directly in your response. Do not hide them
    behind function calls or additional messages. Display them clearly and directly.
    
    First, call check_questions_exist() to determine if there are questions that need answers.
    
    If questions exist:
    - You MUST display the exact questions to the user in a clear, readable format as your MAIN response
    - Present the questions one by one, numbered or bulleted
    - Do not add any introduction before the questions - start immediately with the questions
    - Wait for the user's response before proceeding
    - When the user provides answers, use collect_user_answers() to store them
    
    If no questions exist, simply state that no clarification is needed and continue.
    """,
    tools=[
        FunctionTool(func=check_questions_exist),
        FunctionTool(func=collect_user_answers),
        FunctionTool(func=set_state)
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

# Create the sequential pipeline with question-answer capability
context_former = SequentialAgent(
    name="ContextFormer",
    sub_agents=[
        project_structure_agent,
        dependency_analysis_agent,
        gitignore_filter_agent,
        parallel_search_agent,
        relevance_determination_agent,
        question_asking_agent,
        user_answer_collection_agent,  # Add the user answer collection agent
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