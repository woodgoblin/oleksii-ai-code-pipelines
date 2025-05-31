"""Shared pytest fixtures for the entire test suite."""

import pytest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing file operations.
    
    Provides a clean temporary directory that gets automatically cleaned up
    after the test completes.
    """
    # Arrange
    temp_path = tempfile.mkdtemp()
    
    yield temp_path
    
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_project_structure(temp_dir):
    """Create a sample project structure for testing.
    
    Creates a realistic project structure with various file types
    and directories for comprehensive testing.
    """
    # Arrange
    project_root = Path(temp_dir)
    
    # Create directory structure
    (project_root / "src").mkdir()
    (project_root / "src" / "models").mkdir()
    (project_root / "src" / "services").mkdir()
    (project_root / "tests").mkdir()
    (project_root / "docs").mkdir()
    (project_root / ".git").mkdir()
    
    # Create sample files
    files_to_create = {
        "README.md": "# Sample Project\nThis is a test project.",
        "requirements.txt": "pytest==7.4.0\nrequests==2.31.0\n",
        "package.json": '{"name": "test-project", "dependencies": {"lodash": "^4.17.21"}}',
        ".gitignore": "*.pyc\n__pycache__/\n.env\n",
        "src/models/user.py": "class User:\n    def __init__(self, name):\n        self.name = name",
        "src/services/api.py": "def get_data():\n    return {'status': 'ok'}",
        "tests/test_user.py": "def test_user_creation():\n    assert True",
        "docs/api.md": "# API Documentation\nEndpoints...",
    }
    
    for file_path, content in files_to_create.items():
        full_path = project_root / file_path
        full_path.write_text(content, encoding='utf-8')
    
    return str(project_root)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing logging functionality."""
    # Arrange
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    
    return logger


@pytest.fixture
def mock_async_function():
    """Create a mock async function for testing retry logic."""
    # Arrange
    mock_func = AsyncMock()
    
    return mock_func


@pytest.fixture
def sample_error_messages():
    """Provide sample error messages for testing error parsing."""
    # Arrange
    return {
        "rate_limit_with_delay": '{"error": "rate limit exceeded", "retryDelay":"10s"}',
        "rate_limit_unquoted": "Error: rate limit exceeded, retryDelay: 15",
        "retry_after_header": "HTTP 429: Too Many Requests\nRetry-After: 30",
        "resource_exhausted": "RESOURCE_EXHAUSTED: Quota exceeded for requests",
        "generic_error": "HTTP 500: Internal Server Error",
        "network_error": "Connection timeout occurred",
    }


@pytest.fixture
def sample_file_contents():
    """Provide sample file contents for testing file operations."""
    # Arrange
    return {
        "python_file": "#!/usr/bin/env python3\n\ndef hello_world():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    hello_world()",
        "json_file": '{\n  "name": "test",\n  "version": "1.0.0",\n  "dependencies": {\n    "pytest": "^7.0.0"\n  }\n}',
        "text_file": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5",
        "empty_file": "",
        "large_file": "\n".join([f"Line {i}" for i in range(1, 1001)]),  # 1000 lines
    }


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext for testing tool functions."""
    # Arrange
    context = Mock()
    context.state = {}
    
    return context


@pytest.fixture
def sample_dependencies_data():
    """Provide sample dependency data for testing dependency analysis."""
    # Arrange
    return {
        "requirements_txt": [
            "pytest==7.4.0",
            "requests==2.31.0",
            "fastapi>=0.100.0",
            "uvicorn[standard]",
        ],
        "package_json": {
            "dependencies": {
                "lodash": "^4.17.21",
                "express": "~4.18.0",
                "react": "^18.2.0"
            },
            "devDependencies": {
                "jest": "^29.0.0",
                "eslint": "^8.0.0"
            }
        }
    } 