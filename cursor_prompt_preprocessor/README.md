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

The system includes a built-in rate limit handling mechanism to automatically retry LLM calls when they hit rate limits. This is particularly useful when using the free tier of the Gemini API which has per-minute and per-day limits.

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

## Using the Preprocessor

The recommended way to use the preprocessor is through the ADK Web UI.

### ADK Web UI Integration

```adk web ```

Use the CONSOLE to answer questions due to the ADK Web 0.4.0 limitations in building the humans into the AI flow.

