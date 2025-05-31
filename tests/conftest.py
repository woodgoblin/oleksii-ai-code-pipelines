"""Shared pytest fixtures for the entire test suite."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest


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
        full_path.write_text(content, encoding="utf-8")

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
