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

## Usage

### CLI

The preprocessor can be used as a command-line tool:

```bash
# Process a prompt directly
python main.py "Create a REST API endpoint for user authentication"

# Process a prompt from a file
python main.py -f prompt.txt

# Save the context to a file
python main.py "Create a login form" -o context.json

# Run in interactive mode
python main.py -i
```

## License

[MIT License](LICENSE)
