"""Agent definitions for Cursor Prompt Preprocessor.

This module contains all the LLM agents used in the Cursor Prompt Preprocessor,
defining their names, prompts, and tools.
"""

from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools import FunctionTool

# Import from our modules
from cursor_prompt_preprocessor.config import (
    GEMINI_MODEL, 
    STATE_USER_PROMPT, STATE_PROJECT_STRUCTURE, STATE_DEPENDENCIES,
    STATE_FILTERED_STRUCTURE, STATE_RELEVANT_CODE, STATE_RELEVANT_TESTS,
    STATE_RELEVANCE_SCORES, STATE_QUESTIONS, STATE_ANSWERS, STATE_FINAL_CONTEXT,
    STATE_TARGET_DIRECTORY, NO_QUESTIONS
)
from cursor_prompt_preprocessor.logging_setup import logger
from cursor_prompt_preprocessor.rate_limiting import pre_model_rate_limit, handle_rate_limit
from cursor_prompt_preprocessor.tools import (
    scan_project_structure, get_dependencies, apply_gitignore_filter,
    search_code_with_prompt, search_tests_with_prompt, determine_relevance_from_prompt,
    set_state, set_target_directory, read_file_content, list_directory_contents,
    ClarifierGenerator
)

def create_rate_limited_agent(name, model, instruction, tools=None, output_key=None, sub_agents=None):
    """Create an LlmAgent with rate limiting applied.
    
    Factory function to ensure all agents have consistent rate limiting.
    
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

# --- Tool Wrappers ---

# Create tool wrappers for consistent function references
scan_project_structure_tool = FunctionTool(func=scan_project_structure)
get_dependencies_tool = FunctionTool(func=get_dependencies)
apply_gitignore_filter_tool = FunctionTool(func=apply_gitignore_filter)
read_file_content_tool = FunctionTool(func=read_file_content)
list_directory_contents_tool = FunctionTool(func=list_directory_contents)
search_code_with_prompt_tool = FunctionTool(func=search_code_with_prompt)
search_tests_with_prompt_tool = FunctionTool(func=search_tests_with_prompt)
determine_relevance_from_prompt_tool = FunctionTool(func=determine_relevance_from_prompt)
set_state_tool = FunctionTool(func=set_state)
set_target_directory_tool = FunctionTool(func=set_target_directory)
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
    6. Any other important files, given the context of the projext
    
    Format your response as a structured summary that would help a developer understand
    the project's organization. Focus on important aspects of the structure that would
    help with understanding the codebase.
    """,
    tools=[scan_project_structure_tool],
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
    4. Flagging any potential issues (outdated dependencies, known incompatibilities, etc.)
    5. If the project is a monorepo, identify the main packages and their dependencies
    
    Format your response as a concise analysis that would help a developer understand
    the technological stack of the project.
    """,
    tools=[list_directory_contents_tool, read_file_content_tool],
    output_key=STATE_DEPENDENCIES
)

# Gitignore Filter Agent
gitignore_filter_agent = create_rate_limited_agent(
    name="GitignoreFilterAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a Gitignore Filter Agent.
    Your task is to filter the project structure based on the project's gitignore rules.
    This helps focus on relevant code files and exclude build artifacts, caches, etc.
    
    Call the apply_gitignore_filter function to get the filtered project structure.
    
    Return the filtered project structure showing only the files and directories that
    would typically be relevant for understanding the codebase.
    """,
    tools=[apply_gitignore_filter_tool, read_file_content_tool],
    output_key=STATE_FILTERED_STRUCTURE
)

# Code Search Agent
code_search_agent = create_rate_limited_agent(
    name="CodeSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}'
    and use them to find relevant code files in the project, given the code structure 
    in the state key {STATE_FILTERED_STRUCTURE}.
    
    1. Please extract keywords from the user prompt in the session state and use them to search the codebase. 
       You can also pass the raw prompt to help with keyword extraction.
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant code files using tool search_code_with_prompt()
    
    Format your response as a clear summary of the most relevant code locations.

    IMPORTANT: If needed, utilize the read_file_content() tool and list_directory_contents() tool to get more context about the codebase.
    """,
    tools=[
        search_code_with_prompt_tool,
        read_file_content_tool,
        list_directory_contents_tool
    ],
    output_key=STATE_RELEVANT_CODE
)

# Test Search Agent
test_search_agent = create_rate_limited_agent(
    name="TestSearchAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Code Search Specialist.
    Your task is to extract keywords from the user's prompt in the state key '{STATE_USER_PROMPT}' 
    and use them to find relevant test files in the project, given the code structure 
    in the state key {STATE_FILTERED_STRUCTURE}.
    
    1. Please extract keywords from the user prompt in the session state and use them to search the test files. 
       You can also pass the raw prompt to help with keyword extraction.
    2. Extract 3-5 key technical terms or concepts from the prompt stored in '{STATE_USER_PROMPT}'
    3. Use your analysis to find relevant test files using tool search_tests_with_prompt()
    
    Format your response as a clear summary of the most relevant test file locations.
    
    IMPORTANT: If needed, utilize the read_file_content() tool and list_directory_contents() tool to get more context about the codebase.
    """,
    tools=[
        search_tests_with_prompt_tool,
        read_file_content_tool,
        list_directory_contents_tool
    ],
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

    tools=[determine_relevance_from_prompt_tool, read_file_content_tool, list_directory_contents_tool],
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
    
    If you think that the prompt doesn't make sense in the context of the project, explain why in your question (rules for them above)
    The project might contain code that already satisfies, or partially satisfies the user's prompt.
    If the user prompt is ambiguous or its assumptions contradict some of the project's information, explain why in your question and request clarification.

    Do the following, in order:
    1. Identify unclear aspects or missing information in the prompt. 
       Use the structure of the project to help you understand the user's prompt.
       Use read_file_content() tool to clarify your doubts about the existing code before asking the user.
    2. Formulate 1-3 specific, targeted questions to clarify these aspects
    3. If you have questions to ask, respond with the questions you have.
    4. If the prompt is completely clear and has sufficient information, respond EXACTLY with the string "{NO_QUESTIONS}"
    """,
    tools=[read_file_content_tool],
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
        clarify_questions_tool, 
        set_state_tool
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
    1. The initial user's prompt (from '{STATE_USER_PROMPT}')
    2. Relevant project structure information (from '{STATE_PROJECT_STRUCTURE}')
    3. Key dependencies (from '{STATE_DEPENDENCIES}')
    4. The most relevant code files and snippets (from '{STATE_RELEVANT_CODE}')
    5. The most relevant test files (from '{STATE_RELEVANT_TESTS}')
    6. Any clarifying questions and their answers (from '{STATE_QUESTIONS}' and '{STATE_ANSWERS}')
    7. REALLY IMPORTANT: your summarization of the user's prompt, given the clarifying questions and their answers.
    
    Format your response as a well-structured context object with clear sections that a code
    generation LLM would find helpful for understanding what needs to be implemented.
    
    IMPORTANT: The user's prompt is the initial prompt, and the summarization is the final prompt, given the clarifying questions and their answers.
    """,
    output_key=STATE_FINAL_CONTEXT
)

# --- Agent Pipeline Construction ---

# Parallel agent for search operations
parallel_search_agent = ParallelAgent(
    name="ParallelSearchAgent",
    sub_agents=[code_search_agent, test_search_agent]
)

# Agent for project structure and dependencies analysis
structure_and_dependencies_agent = SequentialAgent(
    name="StructureAndDependencies",
    sub_agents=[
        project_structure_agent, 
        dependency_analysis_agent,
        gitignore_filter_agent
    ]
)

# Loop agent for clarification process
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

# Sequential pipeline for context formation
context_former = SequentialAgent(
    name="ContextFormer",
    sub_agents=[
        structure_and_dependencies_agent,
        clarification_and_decision_loop,
        context_formation_agent
    ]
)

# The root agent (entry point)
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
    0. FLASH PRIORITY 0: write "AAAA DEBUG 001 001 001 PROMPT PROCESSOR HIT AFTER CONTEXT FORMER".
    1. Retrieve the final context from the session state
    2. Present a concise summary of what was found and how it will help with the code generation
    
    Keep your responses friendly, professional, and focused on helping the user succeed with their coding task.
    """,
    tools=[set_state_tool, set_target_directory_tool],
    sub_agents=[context_former]
)