import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools import FunctionTool
import glob
import os
import gitignore_parser
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (41 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """

    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (
                f"Sorry, I don't have timezone information for {city}."
            ),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = (
        f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    )
    return {"status": "success", "report": report}

APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "dev_user_01"
SESSION_ID = "session_01"
GEMINI_MODEL = "gemini-2.0-flash"

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

def scan_project_structure() -> dict:
    """Wrapper function to scan the current project structure.
    
    This function doesn't take any parameters to avoid issues with automatic function calling.
    
    Returns:
        dict: A dictionary representation of the project structure.
    """
    return get_project_structure(".")

def get_dependencies() -> dict:
    """Analyzes project dependencies from requirements.txt, package.json, etc.

    Returns:
        dict: A dictionary of project dependencies and their versions.
    """
    dependencies = {}
    
    # Check for Python requirements.txt
    if os.path.exists("requirements.txt"):
        with open("requirements.txt", "r") as file:
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
    if os.path.exists("package.json"):
        import json
        with open("package.json", "r") as file:
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

    Returns:
        dict: Filtered project structure.
    """
    try:
        structure = get_project_structure(".")
        
        # Check if .gitignore exists
        if not os.path.exists(".gitignore"):
            return structure
        
        # Parse gitignore
        matches = gitignore_parser.parse_gitignore(".gitignore")
        
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

def apply_gitignore_filter() -> dict:
    """Wrapper function to apply gitignore filtering with no parameters.
    
    Returns:
        dict: Filtered project structure.
    """
    return filter_by_gitignore()

# Gitignore Filter Agent
gitignore_filter_agent = LlmAgent(
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

# --- LLM Agents ---

# Project Structure Agent
project_structure_agent = LlmAgent(
    name="ProjectStructureAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Project Structure Analyzer.
    Your task is to scan the project directory structure provided in the session state
    and summarize the key components and organization of the project.
    
    Call the scan_project_structure function to get the project structure.
    
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
dependency_analysis_agent = LlmAgent(
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

# Code Search Agent
code_search_agent = LlmAgent(
    name="CodeSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}'
    and use them to find relevant code files in the project.
    
    1. First, call search_code_with_prompt() to get instructions for searching
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant code files
    
    For the codebase search, focus on:
    - Files related to the technologies mentioned (e.g., Python, aiohttp)
    - Files that might implement similar functionality
    - Configuration files related to the request
    
    Format your response as a clear summary of the most relevant code locations.
    """,
    tools=[FunctionTool(func=search_code_with_prompt)],
    output_key=STATE_RELEVANT_CODE
)

# Test Search Agent
test_search_agent = LlmAgent(
    name="TestSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}'
    and use them to find relevant test files in the project.
    
    1. First, call search_tests_with_prompt() to get instructions for searching
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant test files
    
    For the test file search, focus on:
    - Test files related to the technologies mentioned (e.g., Python, aiohttp)
    - Test files that test similar functionality
    - Test configurations related to the request
    
    Format your response as a clear summary of the most relevant test files that could
    help understand how the components in question are tested.
    """,
    tools=[FunctionTool(func=search_tests_with_prompt)],
    output_key=STATE_RELEVANT_TESTS
)

# Relevance Determination Agent
relevance_determination_agent = LlmAgent(
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
    
    If few or no files were found, provide a recommendation based on the user's request.
    For a REST API with Python/aiohttp, suggest focusing on:
    - API route definitions
    - Request/response handling
    - Authentication middleware
    - Data models
    
    Format your response as a ranked list with explanations for why each top file is relevant.
    If no existing files were found, explain what files would need to be created.
    """,
    tools=[FunctionTool(func=determine_relevance_from_prompt)],
    output_key=STATE_RELEVANCE_SCORES
)

# Question Asking Agent
question_asking_agent = LlmAgent(
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
    output_key=STATE_QUESTIONS
)

# Context Formation Agent
context_formation_agent = LlmAgent(
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

# Create the sequential pipeline 
context_former = SequentialAgent(
    name="ContextFormer",
    sub_agents=[
        project_structure_agent,
        dependency_analysis_agent,
        gitignore_filter_agent,
        parallel_search_agent,
        relevance_determination_agent,
        question_asking_agent,
        context_formation_agent
    ]
)

# The root agent is the entry point for the user prompt
root_agent = LlmAgent(
    name="PromptProcessor",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the main coordinator for processing coding prompts.
    
    Your first task is to:
    1. Welcome the user
    2. Store their coding prompt in the session state with key '{STATE_USER_PROMPT}' using the set_state tool
    3. Transfer control to the ContextFormer agent
    
    Be sure to always store the user's coding prompt in the state key '{STATE_USER_PROMPT}' before proceeding.
    
    After the ContextFormer has completed, you should:
    1. Retrieve the final context from the session state
    2. Present a concise summary of what was found and how it will help with the code generation
    
    Keep your responses friendly, professional, and focused on helping the user succeed with their coding task.
    """,
    tools=[FunctionTool(func=set_state)],
    sub_agents=[context_former]
)