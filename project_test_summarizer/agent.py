"""Agent definitions for Project Test Summarizer.

This module contains all the LLM agents used in the Project Test Summarizer,
defining their names, prompts, and tools for test analysis.
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools import FunctionTool

from common.logging_setup import setup_logging
from common.rate_limiting import RateLimiter, create_rate_limit_callbacks
from common.tools import (
    get_session_state,
    get_session_state_direct,
    get_structured_state,
    list_directory_contents,
    read_file_content,
    search_codebase,
    set_session_state,
    set_session_state_direct,
    set_structured_state,
)

# Import from our modules
from project_test_summarizer.config import (
    GEMINI_MODEL,
    NO_ISSUES_FOUND,
    RATE_LIMIT_MAX_CALLS,
    RATE_LIMIT_WINDOW,
    STATE_AI_REPORT,
    STATE_EXTRACTED_TESTS,
    STATE_HUMAN_REPORT,
    STATE_PROJECT_SUMMARY,
    STATE_TARGET_PROJECT,
    STATE_TEST_ANALYSIS,
    STATE_TEST_REPORTS,
)
from project_test_summarizer.tools import (
    analyze_multiple_test_reports,
    analyze_test_report_content,
    discover_test_files,
    discover_test_reports,
    save_analysis_report,
    search_test_by_name,
)

# Set up logging and rate limiting for this module
logger = setup_logging("project_test_summarizer", redirect_stdout=False)

# Create rate limiter with our configuration and enhanced retry logic
rate_limiter = RateLimiter(
    max_calls=RATE_LIMIT_MAX_CALLS, window_seconds=RATE_LIMIT_WINDOW, logger_instance=logger
)
pre_model_rate_limit, handle_rate_limit_and_server_errors = create_rate_limit_callbacks(
    rate_limiter_instance=rate_limiter, logger_instance=logger
)

# Universal constraint preamble for all agents
AGENT_INSTRUCTION_PREAMBLE = """IMPORTANT: You are a test analysis specialist. Your capabilities are strictly limited to analyzing, understanding, and discovering existing test files and test reports using ONLY the tools explicitly provided to you. You CANNOT create, write, modify, or delete files or directories. You CANNOT execute code or terminal commands. You CANNOT run tests. Your role is purely analytical - to examine existing test artifacts and provide insights about test quality, consistency, and naming. If you believe files need to be created or modified, state this as a suggestion in your textual response, but DO NOT attempt to perform the action."""


def create_rate_limited_agent(
    name, model, instruction, tools=None, output_key=None, sub_agents=None
):
    """Create an LlmAgent with rate limiting and universal constraints applied."""

    full_instruction = AGENT_INSTRUCTION_PREAMBLE + "\n\n" + instruction

    # Create the base agent with enhanced callbacks
    return LlmAgent(
        name=name,
        model=model,
        instruction=full_instruction,
        tools=tools or [],
        output_key=output_key,
        sub_agents=sub_agents or [],
        before_model_callback=pre_model_rate_limit,
        after_model_callback=handle_rate_limit_and_server_errors,
    )


# --- Tool Wrappers ---

# Create tool wrappers for our specialized test analysis tools
discover_test_reports_tool = FunctionTool(func=discover_test_reports)
analyze_test_report_content_tool = FunctionTool(func=analyze_test_report_content)
analyze_multiple_test_reports_tool = FunctionTool(func=analyze_multiple_test_reports)
discover_test_files_tool = FunctionTool(func=discover_test_files)
search_test_by_name_tool = FunctionTool(func=search_test_by_name)
save_analysis_report_tool = FunctionTool(func=save_analysis_report)

# Import common tools
read_file_content_tool = FunctionTool(func=read_file_content)
list_directory_contents_tool = FunctionTool(func=list_directory_contents)
search_codebase_tool = FunctionTool(func=search_codebase)
get_session_state_tool = FunctionTool(func=get_session_state)
set_session_state_tool = FunctionTool(func=set_session_state)

# Improved session state tools for structured data
get_structured_state_tool = FunctionTool(func=get_structured_state)
set_structured_state_tool = FunctionTool(func=set_structured_state)
get_session_state_direct_tool = FunctionTool(func=get_session_state_direct)
set_session_state_direct_tool = FunctionTool(func=set_session_state_direct)

# --- LLM Agents ---

# Test Report Discovery Agent
test_report_discovery_agent = create_rate_limited_agent(
    name="TestReportDiscoveryAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Report Discovery Agent.
    Your task is to discover and analyze test reports in the target project directory.
    
    Your workflow:
    1. Get the target project directory from session state key '{STATE_TARGET_PROJECT}' using get_structured_state
    2. Use the discover_test_reports tool to find test report files in the project
    3. **IMPORTANT**: If you find many report files (10+), use analyze_multiple_test_reports with the list of absolute file paths for efficient batch processing
    4. If you find only a few report files (<10), you may use analyze_test_report_content for individual files
    5. **CRITICAL**: Store the COMPLETE STRUCTURED DATA as JSON string in session state key '{STATE_TEST_REPORTS}' using set_structured_state
    
    **Data Storage Guidelines**:
    - Convert the tool output to JSON string before storing with set_structured_state
    - Include both discovered_reports and extracted_tests data
    - Do NOT create human-readable summaries - store the complete tool output as JSON
    - The next agent needs the structured test data to extract test names
    
    **Batch Processing Guidelines**:
    - For 10+ reports: Use analyze_multiple_test_reports with a list of absolute file paths
    - This avoids making 100+ individual tool calls and is much more efficient
    - The batch tool returns aggregated results with deduplication and summary statistics
    
    **JSON Storage Format**:
    Use set_structured_state to store a JSON string like:
    {{
        "discovery_result": {{discovered reports data}},
        "analysis_result": {{extracted tests data}},
        "framework_detected": "detected framework name",
        "summary": "brief summary for logging"
    }}
    """,
    tools=[
        get_structured_state_tool,
        discover_test_reports_tool,
        analyze_test_report_content_tool,
        analyze_multiple_test_reports_tool,
        list_directory_contents_tool,
        set_structured_state_tool,
    ],
    output_key=STATE_TEST_REPORTS,
)

# Test Name Extraction Agent
test_extraction_agent = create_rate_limited_agent(
    name="TestExtractionAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Name Extraction Agent.
    Your task is to extract and consolidate all unique test names from the discovered test reports.
    
    Your workflow:
    1. Retrieve the test reports data from session state key '{STATE_TEST_REPORTS}' using get_structured_state
    2. **IMPORTANT**: Parse the JSON string returned - look for 'analysis_result' containing extracted_tests or unique_tests
    3. Extract all unique test names from the structured test data
    4. Clean and normalize test names (handle duplicates, variations)
    5. Identify likely parameterized tests (tests with similar names but different parameters)
    6. Store the extracted test list as JSON string in session state key '{STATE_EXTRACTED_TESTS}' using set_structured_state
    
    **JSON Data Parsing Guidelines**:
    - Use get_structured_state to retrieve data as JSON string, then parse it
    - The input data will be structured JSON with 'discovery_result' and 'analysis_result' keys
    - Look for 'extracted_tests' or 'unique_tests' arrays in the analysis_result
    - Each test should have properties like 'test_name', 'full_name', 'class_name', etc.
    - Handle missing or malformed data gracefully
    
    **Error Handling**:
    - If structured data is missing, return an error message explaining what's needed
    - If no tests are found, still store an empty but valid structure as JSON
    - Log any parsing issues for debugging
    
    **JSON Storage Format**:
    Use set_structured_state to store a JSON string like:
    {{
        "extracted_tests": [
            {{
                "original_name": "test name from report",
                "normalized_name": "cleaned test name", 
                "full_name": "class.method or full identifier",
                "source_reports": ["file1.xml", "file2.xml"],
                "test_type": "unit|integration|etc",
                "confidence": "high|medium|low"
            }}
        ],
        "extraction_summary": {{
            "total_tests_found": 0,
            "unique_tests_extracted": 0,
            "frameworks_detected": [],
            "parsing_issues": []
        }}
    }}
    """,
    tools=[get_structured_state_tool, set_structured_state_tool],
    output_key=STATE_EXTRACTED_TESTS,
)

# Individual Test Analysis Agent
test_analysis_agent = create_rate_limited_agent(
    name="TestAnalysisAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Test Analysis Agent.
    Your task is to analyze each extracted test by finding it in the codebase and evaluating its quality.
    
    Your workflow:
    1. Get the target project directory from session state key '{STATE_TARGET_PROJECT}' using get_structured_state
    2. Retrieve extracted tests from session state key '{STATE_EXTRACTED_TESTS}' using get_structured_state
    3. **IMPORTANT**: Parse the JSON string returned - look for 'extracted_tests' array
    4. For each test, perform detailed analysis as described below
    5. Store comprehensive results as JSON string in session state key '{STATE_TEST_ANALYSIS}' using set_structured_state
    
    **For each test, you must**:
    
    1. **Find the test in code**:
       - Use search_test_by_name with both exact and fuzzy matching
       - Use read_file_content to examine the actual test implementation
       - If not found exactly, try variations and similar names
    
    2. **Analyze consistency**:
       - From the test code, determine the actual function/method name in code under test. Search it in the codebase using search_codebase tool.
       - Compare the test name from reports with the actual function/method name in code under test (NOT IN THE TEST CODE)
       - Check if display name (docstring/@DisplayName) matches the test purpose
       - IMPORTANT: Flag any inconsistencies between report name and code implementation
    
    3. **Evaluate test meaningfulness**:
       - Check if the test has meaningful assertions (not just testing the framework)
       - Verify it tests actual functionality, not just mocks or trivial operations
       - Identify tests that don't actually test anything meaningful
       - Look for proper setup/teardown and realistic test data
    
    4. **Assess naming clarity**:
       - Evaluate if the test name accurately describes what the test does
       - Check if the name follows good naming conventions 
       - Suggest improvements for unclear or misleading names (If the name is given as a human readable sentence don't suggest snake_case or camelCase. However you can suggest better human readable names)
    
    **Error Handling**:
    - If extracted_tests data is missing or malformed, return detailed error information
    - If no tests to analyze, return empty but valid structure as JSON
    - Continue processing other tests if one fails
    
    **JSON Storage Format**:
    Use set_structured_state to store a JSON string like:
    {{
        "analyzed_tests": [
            {{
                "test_name": "original test name",
                "test_location": {{
                    "file_path": "path/to/test/file.py",
                    "line_number": 123,
                    "found": true
                }},
                "consistency_issues": ["list of issues"],
                "meaningfulness_score": "high|medium|low", 
                "meaningfulness_notes": "explanation of assessment",
                "naming_clarity_score": "high|medium|low",
                "naming_suggestions": ["suggested improvements"],
                "code_under_test": "function/method being tested",
                "issues_found": ["all problems identified"],
                "recommendations": ["specific improvement suggestions"]
            }}
        ],
        "analysis_summary": {{
            "total_tests_analyzed": 0,
            "tests_found_in_code": 0,
            "critical_issues": 0,
            "moderate_issues": 0,
            "good_tests": 0
        }}
    }}
    """,
    tools=[
        get_structured_state_tool,
        search_test_by_name_tool,
        read_file_content_tool,
        search_codebase_tool,
        discover_test_files_tool,
        set_structured_state_tool,
    ],
    output_key=STATE_TEST_ANALYSIS,
)

# Human-Friendly Report Generator
human_report_agent = create_rate_limited_agent(
    name="HumanReportAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Human-Friendly Report Generator.
    Your task is to create a comprehensive, readable report for human developers.
    
    Using data from session state key '{STATE_TEST_ANALYSIS}' (retrieved with get_structured_state and parsed as JSON), create a report with:
    
    **Executive Summary**:
    - Total tests analyzed
    - Overall test quality assessment
    - Major issues found
    - Framework(s) detected
    
    **Per-Test Analysis** (organized by severity):
    1. **Critical Issues**: Tests with major problems
    2. **Moderate Issues**: Tests with room for improvement  
    3. **Good Tests**: Tests that are well-written
    
    For each test, include:
    - Test name and location
    - **Problems**: List of specific issues found
    - **Solutions**: Concrete steps to fix each problem
    - **Suggestions**: Recommendations for improvement
    - **Better Name**: Suggested improved test name (if applicable)
    
    **Recommendations**:
    - Overall testing strategy improvements
    - Naming convention suggestions
    - Framework-specific best practices
    
    Format as a JSON structure that is human-readable but also structured.
    Store as JSON string in session state key '{STATE_HUMAN_REPORT}' using set_structured_state.
    """,
    tools=[get_structured_state_tool, set_structured_state_tool],
    output_key=STATE_HUMAN_REPORT,
)

# AI-Friendly Report Generator
ai_report_agent = create_rate_limited_agent(
    name="AIReportAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are an AI-Friendly Report Generator.
    Your task is to create a structured report optimized for AI-assisted coding tools.
    
    Using data from session state key '{STATE_TEST_ANALYSIS}' (retrieved with get_structured_state and parsed as JSON), create a report formatted as prompts for AI coding assistants.
    
    For each test with issues, generate:
    
    **Improvement Prompt**:
    "Please improve this test: [test name]
    
    Current issues:
    - [Issue 1 with specific details]
    - [Issue 2 with specific details]
    
    Current test code location: [file path]
    
    Please:
    1. Fix the identified issues
    2. Improve test naming to: [suggested name]
    3. Ensure proper assertions and meaningful test logic
    4. Follow [framework] best practices
    
    Expected outcome: A well-structured, meaningful test that clearly validates [specific functionality]."
    
    **Creation Prompt** (for missing tests):
    "Please create a test for: [functionality]
    
    Requirements:
    - Test name: [suggested name]
    - Framework: [detected framework]
    - Should verify: [specific behavior]
    - Include: [specific assertions needed]"
    
    Format as a JSON structure optimized for programmatic consumption.
    Store as JSON string in session state key '{STATE_AI_REPORT}' using set_structured_state.
    """,
    tools=[get_structured_state_tool, set_structured_state_tool],
    output_key=STATE_AI_REPORT,
)

# Project Test Summarizer Agent
project_summary_agent = create_rate_limited_agent(
    name="ProjectSummaryAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Project Test Summarizer.
    Your task is to create high-level summaries of the project's testing landscape.
    
    Using data from all previous analysis stages, especially the {STATE_TEST_ANALYSIS} (retrieved with get_structured_state and parsed as JSON), create three different summary formats:
    
    **3-Sentence Summary**:
    A concise overview of testing state, major frameworks used, and overall quality.
    
    **Paragraph Summary**:
    A detailed paragraph covering testing frameworks, test coverage approach, 
    quality assessment, major issues found, and recommendations.
    
    **Full Summary** (A4 page equivalent):
    A comprehensive analysis including:
    - Testing strategy and frameworks in use
    - Quality assessment with specific metrics
    - Detailed breakdown of issues by category
    - Comparison with testing best practices
    - Specific recommendations for improvement
    - Suggested next steps for the development team
    
    Store all three summaries as JSON string in session state key '{STATE_PROJECT_SUMMARY}' using set_structured_state.
    """,
    tools=[get_structured_state_tool, set_structured_state_tool],
    output_key=STATE_PROJECT_SUMMARY,
)

# Report Compilation and Export Agent
report_export_agent = create_rate_limited_agent(
    name="ReportExportAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Report Export Agent.
    Your task is to compile all analysis results and export them to a JSON file.
    
    Your workflow:
    1. Gather all results from session state using get_structured_state and parse JSON strings:
       - Test reports data from '{STATE_TEST_REPORTS}'
       - Extracted tests from '{STATE_EXTRACTED_TESTS}'
       - Analysis results from '{STATE_TEST_ANALYSIS}'
       - Human report from '{STATE_HUMAN_REPORT}'
       - AI report from '{STATE_AI_REPORT}'
       - Project summary from '{STATE_PROJECT_SUMMARY}'
    
    2. Compile into a comprehensive final report structure
    
    3. Use save_analysis_report tool to export the complete analysis
    
    4. Provide a final summary to the user about what was analyzed and where the report was saved
    
    The exported report should be a complete record of the entire test analysis process.
    """,
    tools=[get_structured_state_tool, save_analysis_report_tool],
)

# --- Agent Pipeline Construction ---

# Sequential analysis pipeline
test_discovery_and_extraction = SequentialAgent(
    name="TestDiscoveryAndExtraction",
    sub_agents=[test_report_discovery_agent, test_extraction_agent],
)

# Parallel report generation
report_generation = ParallelAgent(
    name="ReportGeneration", sub_agents=[human_report_agent, ai_report_agent, project_summary_agent]
)

# Complete analysis pipeline
analysis_pipeline = SequentialAgent(
    name="AnalysisPipeline",
    sub_agents=[
        test_discovery_and_extraction,
        test_analysis_agent,
        report_generation,
        report_export_agent,
    ],
)

# The root agent (entry point)
root_agent = create_rate_limited_agent(
    name="TestSummarizerRoot",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the Project Test Summarizer - a framework-agnostic test analysis agent.
    
    Your mission is to analyze a software project's tests for quality, consistency, and naming clarity.
    
    **Your workflow**:
    1. Welcome the user and confirm the target project directory
    2. Store the project path as JSON string in session state key '{STATE_TARGET_PROJECT}' using set_structured_state
    3. Transfer control to the AnalysisPipeline to perform comprehensive test analysis
    4. Present a final summary of findings and where the detailed report was saved
    
    **You analyze**:
    - Test reports (XML, JSON, HTML) to extract test names
    - Test code to verify consistency with reported names
    - Test meaningfulness (does it actually test something?)
    - Test naming clarity and suggestions for improvement
    
    **You generate**:
    - Human-friendly JSON report with problems, solutions, and suggestions
    - AI-friendly JSON report formatted as coding prompts
    - Project testing summaries (3 sentences, paragraph, full page)
    
    **You are framework-agnostic**: Works with pytest, JUnit, Jest, and other testing frameworks.
    
    Keep your responses professional and focused on helping improve test quality.
    """,
    tools=[set_structured_state_tool, list_directory_contents_tool],
    sub_agents=[analysis_pipeline],
)
