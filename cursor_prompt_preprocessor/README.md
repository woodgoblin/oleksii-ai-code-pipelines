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

## Usage

You can use this system via the ADK Web UI or programmatically.

### Using ADK Web UI

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

### Using Programmatically

```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from cursor_prompt_preprocessor import root_agent

# Setup
APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "user_id"
SESSION_ID = "session_id"

# Create session and runner
session_service = InMemorySessionService()
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# Send a prompt
def process_prompt(prompt):
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)
    
    for event in events:
        if event.is_final_response():
            print(f"Response: {event.content.parts[0].text}")

# Example
process_prompt("I want a REST API that handles the nuclear rocket launch")
```

## Requirements

- Python 3.8+
- google-adk>=0.1.0
- gitignore_parser

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/coding-prompt-preprocessor.git
cd coding-prompt-preprocessor

# Install dependencies
pip install -r requirements.txt
pip install gitignore_parser

# Install as package (optional)
pip install -e .
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 