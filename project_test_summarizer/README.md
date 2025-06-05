# Project Test Summarizer

A framework-agnostic test analysis agent that analyzes software projects for test quality, consistency, and naming clarity using Google ADK's multi-agent capabilities.

## Overview

The Project Test Summarizer is an intelligent agent system that discovers, analyzes, and reports on the quality of tests in any software project. It works across multiple testing frameworks (pytest, JUnit, Jest, etc.) and provides both human-readable and AI-friendly reports to help improve test quality.

## Key Features

### 🔍 **Framework-Agnostic Test Discovery**
- Automatically discovers test reports in XML, JSON, and HTML formats
- Supports multiple testing frameworks: pytest, JUnit, Jest, Mocha, and more
- Finds test files using common naming patterns across languages
- Batch processing for efficient analysis of large test suites

### 📊 **Comprehensive Test Analysis**
- **Consistency Checking**: Compares test names in reports with actual code implementation
- **Meaningfulness Assessment**: Evaluates whether tests actually validate real functionality
- **Naming Quality**: Analyzes test names for clarity and adherence to conventions
- **Code Location**: Finds actual test implementations in the codebase

### 📋 **Multi-Format Reporting**
- **Human-Friendly Reports**: Structured JSON with problems, solutions, and recommendations
- **AI-Friendly Reports**: Formatted as prompts for AI coding assistants
- **Executive Summaries**: 3-sentence, paragraph, and full-page summaries
- **Exportable Results**: Complete analysis saved to JSON files

### ⚡ **Performance Optimized**
- Built-in rate limiting with automatic retry logic
- Batch processing for large numbers of test reports
- Parallel report generation for faster results
- Efficient codebase searching with fuzzy matching

## Architecture

The system uses Google ADK's multi-agent architecture with specialized agents for different analysis tasks:

```
TestSummarizerRoot (Entry Point)
└── AnalysisPipeline
    ├── TestDiscoveryAndExtraction
    │   ├── TestReportDiscoveryAgent
    │   └── TestExtractionAgent
    ├── TestAnalysisAgent
    ├── ReportGeneration (Parallel)
    │   ├── HumanReportAgent
    │   ├── AIReportAgent
    │   └── ProjectSummaryAgent
    └── ReportExportAgent
```

### Agent Responsibilities

- **TestReportDiscoveryAgent**: Discovers test reports and identifies testing frameworks
- **TestExtractionAgent**: Extracts and normalizes test names from reports
- **TestAnalysisAgent**: Analyzes individual tests for quality and consistency
- **HumanReportAgent**: Generates human-readable analysis reports
- **AIReportAgent**: Creates AI-friendly prompts for code improvement
- **ProjectSummaryAgent**: Produces high-level project testing summaries
- **ReportExportAgent**: Compiles and exports final analysis results

## Supported Test Formats

### Test Reports
- **JUnit XML**: Maven Surefire/Failsafe, Gradle test results
- **pytest XML/HTML**: pytest-generated reports
- **Jest JSON**: JavaScript test results
- **Coverage XML**: Code coverage reports
- **Generic formats**: Any XML/JSON/HTML test output

### Test Files
- **Python**: `test_*.py`, `*_test.py`, `test*.py`
- **Java**: `*Test.java`, `*Tests.java`, `Test*.java`
- **JavaScript/TypeScript**: `*.test.js`, `*.spec.js`, `*.test.ts`, `*.spec.ts`
- **Directory patterns**: `test/`, `tests/`, `src/test/`

## Installation

### Prerequisites
- Python 3.8+
- Google AI Gemini API key

### Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure API key**:
Create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_gemini_api_key_here
```

## Usage

### ADK Web UI (Recommended)

1. **Start the ADK Web UI**:
```bash
adk web
```

2. **Select the agent**: Choose "TestSummarizerRoot" from the agent list

3. **Provide project path**: Enter the absolute path to your project directory

4. **Review results**: The agent will analyze your tests and provide comprehensive reports

### Programmatic Usage

```python
from project_test_summarizer.agent import root_agent
from project_test_summarizer.session import session_manager

# Initialize session
session = session_manager.get_session()

# Run analysis
result = root_agent.run(
    input_data={"project_path": "/path/to/your/project"},
    session=session
)

# Access results
human_report = session_manager.get_state("human_friendly_report")
ai_report = session_manager.get_state("ai_friendly_report")
```

## Analysis Output

### Human-Friendly Report Structure
```json
{
  "executive_summary": {
    "total_tests": 150,
    "framework": "pytest",
    "overall_quality": "moderate",
    "major_issues": 12
  },
  "critical_issues": [
    {
      "test_name": "test_user_login",
      "location": "tests/test_auth.py:45",
      "problems": ["No meaningful assertions", "Tests mocks only"],
      "solutions": ["Add real authentication validation", "Test actual login flow"],
      "better_name": "test_user_login_with_valid_credentials_succeeds"
    }
  ],
  "recommendations": {
    "naming_conventions": "Use descriptive test names that explain the scenario",
    "framework_practices": "Follow pytest best practices for fixtures"
  }
}
```

### AI-Friendly Report Structure
```json
{
  "improvement_prompts": [
    {
      "test_name": "test_user_login",
      "prompt": "Please improve this test: test_user_login\n\nCurrent issues:\n- No meaningful assertions\n- Tests mocks only\n\nPlease:\n1. Add real authentication validation\n2. Improve test naming to: test_user_login_with_valid_credentials_succeeds\n3. Test actual login flow instead of just mocks"
    }
  ],
  "creation_prompts": [
    {
      "functionality": "password_reset",
      "prompt": "Please create a test for password reset functionality..."
    }
  ]
}
```

## Configuration

Key configuration options in `config.py`:

```python
# Model configuration
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"

# Rate limiting
RATE_LIMIT_MAX_CALLS = 10
RATE_LIMIT_WINDOW = 60

# Test discovery patterns
TEST_REPORT_PATTERNS = [
    "**/test-results/**/*.xml",
    "**/pytest-report.xml",
    "**/coverage.xml",
    # ... more patterns
]
```

## Rate Limiting & Error Handling

The system includes robust rate limiting and error handling:

- **Automatic retries** for rate limit errors (429) and server errors (500)
- **Exponential backoff** strategy for repeated failures
- **Detailed logging** of retry attempts and wait times
- **Graceful degradation** when API limits are reached

## Best Practices

### For Optimal Analysis Results

1. **Ensure test reports exist**: Run your tests before analysis to generate reports
2. **Use descriptive test names**: The agent analyzes naming quality
3. **Include meaningful assertions**: Tests should validate real functionality
4. **Follow framework conventions**: Stick to established patterns for your testing framework

### For Large Projects

1. **Use batch processing**: The agent automatically optimizes for large test suites
2. **Monitor rate limits**: Consider upgrading API quotas for very large projects
3. **Review incrementally**: Focus on critical issues first

## Troubleshooting

### Common Issues

**No test reports found**:
- Ensure tests have been run recently
- Check that test output directories exist
- Verify test report patterns match your project structure

**Rate limit errors**:
- The system automatically handles these with retries
- Consider upgrading your Gemini API quota
- Monitor the logs for retry information

**Missing test implementations**:
- Ensure test files follow common naming conventions
- Check that test files are in expected directories
- Review the fuzzy matching results for partial matches

## Contributing

The Project Test Summarizer is part of the larger coding-prompt-preprocessor project. Contributions are welcome for:

- Additional test framework support
- Enhanced analysis algorithms
- Improved report formats
- Performance optimizations

## License

This project is licensed under the same terms as the parent coding-prompt-preprocessor project. 