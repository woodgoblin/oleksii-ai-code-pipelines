# Cursor Prompt Preprocessor

A multi-agent system for preprocessing coding prompts before sending them to Cursor for code generation.

## Overview

This system analyzes the user's coding prompt along with the project structure to form an optimal context for code generation. The process follows these steps:

1. **Project Structure Analysis**: Scans the project directory to understand its structure
2. **Dependency Analysis**: Identifies and analyzes project dependencies
3. **Gitignore Filtering**: Filters the project structure based on gitignore rules
4. **Code Search**: Searches code files based on keywords from the prompt
5. **Test Search**: Searches test files based on keywords from the prompt
6. **Relevance Determination**: Determines the relevance of code and test files
7. **Question Asking**: Asks clarifying questions to the developer when needed
8. **Context Formation**: Forms the final context object for code generation

## Architecture

The system uses Google ADK's multi-agent capabilities with the following agent structure:

- **PromptProcessor** (LlmAgent): The root agent and entry point. Handles initial user input and routes to ContextFormer.
  - **ContextFormer** (SequentialAgent): Orchestrates the context formation process with these sub-agents:
    - **ProjectStructureAgent** (LlmAgent): Analyzes project structure
    - **DependencyAnalysisAgent** (LlmAgent): Analyzes project dependencies
    - **GitignoreFilterAgent** (LlmAgent): Filters using gitignore rules
    - **ParallelSearchAgent** (ParallelAgent): Runs search operations concurrently
      - **CodeSearchAgent** (LlmAgent): Searches code files
      - **TestSearchAgent** (LlmAgent): Searches test files
    - **RelevanceDeterminationAgent** (LlmAgent): Determines relevance of found files
    - **QuestionAskingAgent** (LlmAgent): Generates clarifying questions
    - **ContextFormationAgent** (LlmAgent): Forms the final context

## Rate Limit Handling

The demo script includes a built-in rate limit handling mechanism to automatically retry LLM calls when they hit rate limits. This is particularly useful when using the free tier of the Gemini API which has per-minute and per-day limits.

### Features

- Automatically extracts the `retryDelay` from rate limit errors using regex pattern matching
- Waits for the specified delay plus 1 second before retrying
- Implements exponential backoff strategy for repeated rate limit errors
- Logs detailed information about retries, wait times, and progress
- Works with both synchronous and asynchronous functions

## Getting Started

### Prerequisites

- Python 3.8+
- A Google AI Gemini API key

### Setup

1. Create a `.env` file in this directory with your API key:
```
GOOGLE_API_KEY=your_api_key_here
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Demo

The demo script provides a simple way to test the preprocessor with your own coding prompts and target directories.

### Basic Usage

```bash
# From the root directory of the project
python cursor_prompt_preprocessor/demo.py
```

This will:
1. Use the current directory as the target for code analysis
2. Prompt you for a coding prompt or use a default example
3. Process the prompt through the agent pipeline
4. Display the resulting context

### Analyzing a Specific Directory

```bash
# Analyze a specific directory (use absolute paths for reliability)
python cursor_prompt_preprocessor/demo.py --dir /path/to/your/project

# On Windows, use full path with quotes if needed
python cursor_prompt_preprocessor/demo.py --dir "C:\Users\YourUsername\path\to\project"
```

### Example Prompts

Here are some example prompts you can try:

- "Create a function to calculate the Fibonacci sequence using recursion"
- "Add a new REST API endpoint for user authentication"
- "Implement a rate limiter for HTTP requests"
- "Create a React component that displays a sortable table"

### Output

The demo will display:
1. Intermediate responses from the agents as they analyze your code
2. A final context that would be sent to a code generation system
3. Debug information including all state keys stored during processing

## Using Programmatically

```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from cursor_prompt_preprocessor import root_agent
from cursor_prompt_preprocessor.agent import set_global_session

# Setup
APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "user_id"
SESSION_ID = "session_id"

# Create session and runner
session_service = InMemorySessionService()
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

# Set the global session for proper target directory handling
set_global_session(session)

# Set target directory in session state
session.state["target_directory"] = "/path/to/your/project"

# Create runner
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# Process a prompt with manual retry logic
async def process_prompt_with_retry(prompt, max_retries=3):
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    
    delay = 1
    retry_count = 0
    
    while True:
        try:
            events = []
            async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                events.append(event)
                
                # Process events as needed
                if event.is_final_response():
                    print(f"Final response: {event.content.parts[0].text}")
            
            return events
            
        except Exception as e:
            error_message = str(e)
            retry_count += 1
            
            # If it's a rate limit error and we haven't exceeded max retries
            if "429 RESOURCE_EXHAUSTED" in error_message and retry_count <= max_retries:
                import re
                import asyncio
                
                # Extract retry delay if available
                delay_match = re.search(r"'retryDelay': '(\d+)s'", error_message)
                if delay_match:
                    wait_time = int(delay_match.group(1)) + 1
                else:
                    wait_time = delay
                    delay *= 2
                
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                # If not a rate limit error or we've exhausted retries, re-raise
                raise
```

## ADK Web UI Integration

You can also run the preprocessor in the ADK Web UI:

1. Install the ADK CLI:

```bash
pip install google-adk[cli]
```

2. Run the ADK web server:

```bash
adk-cli web --app cursor_prompt_preprocessor
```

3. Open your browser to http://localhost:8080
4. Start a conversation with the system by entering your coding prompt 