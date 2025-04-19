# Coding Prompt Preprocessor

A multi-agent framework for preprocessing coding prompts before code generation, powered by Google ADK.

## Architecture

The coding prompt preprocessor implements a context forming pipeline that processes user prompts before passing them to code generation tools like Cursor. The preprocessor follows this workflow:

1. **Project Structure Analysis**: Scans the project directory to understand its structure
2. **Dependency Analysis**: Identifies and analyzes project dependencies
3. **Gitignore Filtering**: Filters the project structure based on gitignore rules
4. **Code Search**: Searches code files based on keywords from the prompt
5. **Test Search**: Searches test files based on keywords from the prompt
6. **Relevance Determination**: Determines the relevance of code and test files
7. **Question Asking**: Asks clarifying questions to the developer when needed
8. **Context Formation**: Forms the final context object for code generation

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/coding-prompt-preprocessor.git
cd coding-prompt-preprocessor
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your API Key:
```bash
# Create a .env file in the cursor_prompt_preprocessor directory
echo "GOOGLE_API_KEY=your_api_key_here" > cursor_prompt_preprocessor/.env
```

## Usage

### Running the Demo

The easiest way to use the preprocessor is through the demo script:

```bash
# Process a prompt using the current directory as context
python cursor_prompt_preprocessor/demo.py

# Process a prompt using a specific directory as context
python cursor_prompt_preprocessor/demo.py --dir /path/to/your/project

# On Windows, use full path with quotes if needed
python cursor_prompt_preprocessor/demo.py --dir "C:\Users\YourUsername\path\to\project"
```

The demo will:
1. Scan the target directory to understand its structure
2. Analyze project dependencies
3. Filter by gitignore rules
4. Search for relevant code and test files
5. Form a comprehensive context object for code generation

### Rate Limit Handling

The demo script includes built-in rate limit handling with exponential backoff, automatically retrying API calls when rate limits are hit. This is particularly useful when using the free tier of the Gemini API.

### Using Programmatically

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

# Send a prompt
def process_prompt(prompt):
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)
    
    for event in events:
        if event.is_final_response():
            print(f"Response: {event.content.parts[0].text}")

# Example
process_prompt("Create a REST API endpoint for user authentication")
```

## Requirements

- Python 3.8+
- google-adk>=0.1.0
- google-generativeai>=0.6.0
- gitignore_parser
- python-dotenv

## License

[MIT License](LICENSE)
