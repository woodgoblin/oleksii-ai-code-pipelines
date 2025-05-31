# Cursor Prompt Preprocessor

[![Tests](https://github.com/coding-prompt-preprocessor/coding-prompt-preprocessor/actions/workflows/test.yml/badge.svg)](https://github.com/coding-prompt-preprocessor/coding-prompt-preprocessor/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

A multi-agent system for preprocessing coding prompts before sending them to Cursor for code generation, with Model Context Protocol (MCP) server support.

## Overview

This system analyzes the user's coding prompt along with the project structure to form an optimal context for code generation. The process follows these steps:

1. **Project Structure Analysis**: Scans the project directory to understand its structure
2. **Dependency Analysis**: Identifies and analyzes project dependencies from manifest files
3. **Gitignore Filtering**: Filters the project structure based on gitignore rules
4. **Parallel Code & Test Search**: Searches code and test files concurrently based on keywords from the prompt
5. **Relevance Determination**: Determines the relevance of found code and test files
6. **Interactive Clarification**: Asks clarifying questions to the developer when needed (with loop support)
7. **Context Formation**: Forms the final context object for code generation

## Architecture

The system uses Google ADK's multi-agent capabilities with the following agent structure:

- **PromptProcessor** (LlmAgent): The root agent and entry point. Handles initial user input and routes to ContextFormer.
  - **ContextFormer** (SequentialAgent): Orchestrates the context formation process with these sub-agents:
    - **StructureAndDependencies** (SequentialAgent): Handles initial project analysis
      - **ProjectStructureAgent** (LlmAgent): Analyzes project structure
      - **DependencyAnalysisAgent** (LlmAgent): Analyzes project dependencies
      - **GitignoreFilterAgent** (LlmAgent): Filters using gitignore rules
    - **ClarificationAndDecisionLoop** (LoopAgent): Iterative clarification process (max 3 iterations)
      - **ParallelSearchAgent** (ParallelAgent): Runs search operations concurrently
        - **CodeSearchAgent** (LlmAgent): Searches code files
        - **TestSearchAgent** (LlmAgent): Searches test files
      - **RelevanceDeterminationAgent** (LlmAgent): Determines relevance of found files
      - **QuestionAskingAgent** (LlmAgent): Generates clarifying questions
      - **UserAnswerCollectionAgent** (LlmAgent): Collects user answers via console input
    - **ContextFormationAgent** (LlmAgent): Forms the final context

## Project Components

### Main Components
- **`cursor_prompt_preprocessor/`**: Core agent system with Google ADK integration
- **`project_test_summarizer/`**: Additional agent for test summarization capabilities
- **`potato_decison_with_human_in_the_loop/`**: Example agent demonstrating human-in-the-loop decision making
- **`common/`**: Shared utilities and tools

### Common Utilities
- **Rate Limiting**: Built-in rate limit handling for Gemini API calls with exponential backoff
- **Logging**: Comprehensive logging setup with file and console output
- **Tools**: Project analysis, file operations, and search capabilities
- **MCP Server**: Model Context Protocol server exposing tools for external LLM integration

## Rate Limit Handling

The system includes a built-in rate limit handling mechanism to automatically retry LLM calls when they hit rate limits. This is particularly useful when using the free tier of the Gemini API which has per-minute and per-day limits.

### Features

- Automatically extracts the `retryDelay` from rate limit errors using regex pattern matching
- Waits for the specified delay plus 1 second before retrying
- Implements exponential backoff strategy for repeated rate limit errors
- Logs detailed information about retries, wait times, and progress
- Works with both synchronous and asynchronous functions

## Model Context Protocol (MCP) Support

The project includes an MCP server (`common/mcp_server.py`) that exposes the project analysis tools via the Model Context Protocol, enabling integration with external LLM systems.

### Available MCP Tools
- Project structure scanning
- Dependency analysis
- File content reading
- Directory listing
- Gitignore-based filtering
- Codebase searching
- Human clarification input

## Getting Started

### Prerequisites

- Python 3.10+
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

## Usage Options

### 1. ADK Web UI Integration (Recommended)

```bash
adk web
```

Select the agent from the list and use the CONSOLE to answer questions due to ADK Web UI limitations in building humans into the AI flow.

### 2. MCP Server Integration

Run the MCP server to expose tools for external LLM integration:

```bash
# Navigate to project root
mcp dev common/mcp_server.py
```

### 3. Direct Python Integration

Import and use the agents directly in your Python code:

```python
from cursor_prompt_preprocessor.agent import root_agent
# Use the agent programmatically
```

## CI/CD Pipeline

[![Tests](https://github.com/coding-prompt-preprocessor/coding-prompt-preprocessor/actions/workflows/test.yml/badge.svg)](https://github.com/coding-prompt-preprocessor/coding-prompt-preprocessor/actions/workflows/test.yml)

The project includes a comprehensive GitHub Actions workflow ([`.github/workflows/test.yml`](.github/workflows/test.yml)) that runs on pull requests and pushes to main/develop branches.

### Workflow Features

- **Multi-Python Version Testing**: Tests against Python 3.10, 3.11, and 3.12
- **Code Quality Checks**: 
  - Black code formatting validation [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
  - isort import sorting validation [![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
  - mypy type checking (non-blocking)
- **Test Execution**: Full test suite execution with pytest
- **Coverage Reporting**: Code coverage analysis with detailed reports
- **Dependency Caching**: pip dependency caching for faster builds
- **Artifact Collection**: Test results and coverage reports saved as artifacts

### Quick Actions

- **[View Latest Workflow Runs](https://github.com/coding-prompt-preprocessor/coding-prompt-preprocessor/actions)** - See current build status and history
- **[Download Latest Coverage Report](https://github.com/coding-prompt-preprocessor/coding-prompt-preprocessor/actions/workflows/test.yml)** - Get detailed coverage analysis
- **[View Workflow Configuration](.github/workflows/test.yml)** - Inspect the complete CI/CD setup

### Running Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=. --cov-report=html

# Run code quality checks
black --check .
isort --check-only .
mypy .

# Run the full CI pipeline locally (requires act)
act pull_request
```

### Contributing Guidelines

Before submitting a PR, ensure all CI checks pass:

1. **Tests**: `pytest tests/ -v` ✅
2. **Formatting**: `black --check .` ✅  
3. **Import Sorting**: `isort --check-only .` ✅
4. **Type Checking**: `mypy .` ⚠️ (warnings only)

The automated CI pipeline will verify all these checks on your PR.

## Dependencies

- **google-adk**: Multi-agent framework
- **google-generativeai**: Gemini API integration
- **mcp[cli]**: Model Context Protocol support
- **pytest**: Testing framework
- **python-dotenv**: Environment variable management
- **gitignore-parser**: Gitignore rule processing
- **black, isort, mypy**: Code quality tools

