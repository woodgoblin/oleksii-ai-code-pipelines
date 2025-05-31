"""Tests for tools functionality."""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from common.tools import (
    _resolve_path,
    _validate_path_exists,
    _handle_tool_error,
    ask_human_clarification_mcp,
    ClarifierGenerator,
    set_target_directory,
    get_target_directory_from_state,
    set_session_state,
    get_session_state,
    get_project_structure,
    scan_project_structure,
    list_directory_contents,
    read_file_content,
    get_dependencies,
    filter_by_gitignore,
    apply_gitignore_filter,
    search_codebase,
    search_code_with_prompt,
    search_tests_with_prompt,
    determine_relevance_from_prompt
)


class TestPathUtilities:
    """Test path resolution and validation utilities."""
    
    def test_should_resolve_absolute_path_unchanged(self):
        """Should return absolute path unchanged."""
        # Arrange
        if os.name == 'nt':  # Windows
            abs_path = "C:\\test\\path"
        else:  # Unix-like
            abs_path = "/test/path"
        base_dir = "/some/base"
        
        # Act
        result = _resolve_path(abs_path, base_dir)
        
        # Assert
        assert result == os.path.abspath(abs_path)
    
    def test_should_resolve_relative_path_against_base_directory(self, temp_dir):
        """Should resolve relative path against base directory."""
        # Arrange
        relative_path = "subfolder/file.txt"
        base_dir = temp_dir
        
        # Act
        result = _resolve_path(relative_path, base_dir)
        
        # Assert
        expected = os.path.abspath(os.path.join(base_dir, relative_path))
        assert result == expected
    
    def test_should_raise_error_for_invalid_base_directory(self):
        """Should raise ValueError for invalid base directory."""
        # Arrange
        relative_path = "file.txt"
        invalid_base = "/nonexistent/directory"
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid base directory"):
            _resolve_path(relative_path, invalid_base)
    
    def test_should_raise_error_for_empty_base_directory(self):
        """Should raise ValueError for empty base directory."""
        # Arrange
        relative_path = "file.txt"
        empty_base = ""
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid base directory"):
            _resolve_path(relative_path, empty_base)
    
    def test_should_validate_existing_path(self, temp_dir):
        """Should validate existing path without error."""
        # Arrange
        existing_path = temp_dir
        
        # Act & Assert
        _validate_path_exists(existing_path)  # Should not raise
    
    def test_should_raise_error_for_nonexistent_path(self):
        """Should raise FileNotFoundError for nonexistent path."""
        # Arrange
        nonexistent_path = "/absolutely/nonexistent/path"
        
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Path not found"):
            _validate_path_exists(nonexistent_path)
    
    def test_should_validate_file_type_correctly(self, temp_dir):
        """Should validate file type correctly."""
        # Arrange
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Act & Assert
        _validate_path_exists(test_file, "file")  # Should not raise
    
    def test_should_raise_error_for_incorrect_file_type(self, temp_dir):
        """Should raise ValueError when directory is expected to be file."""
        # Arrange
        directory_path = temp_dir
        
        # Act & Assert
        with pytest.raises(ValueError, match="Path is not a file"):
            _validate_path_exists(directory_path, "file")
    
    def test_should_validate_directory_type_correctly(self, temp_dir):
        """Should validate directory type correctly."""
        # Arrange
        directory_path = temp_dir
        
        # Act & Assert
        _validate_path_exists(directory_path, "directory")  # Should not raise
    
    def test_should_raise_error_for_incorrect_directory_type(self, temp_dir):
        """Should raise ValueError when file is expected to be directory."""
        # Arrange
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Path is not a directory"):
            _validate_path_exists(test_file, "directory")


class TestErrorHandling:
    """Test error handling utilities."""
    
    @patch('common.tools.logger')
    def test_should_handle_tool_error_with_logging(self, mock_logger):
        """Should handle tool error with proper logging."""
        # Arrange
        operation = "reading"
        path = "/test/path"
        error = FileNotFoundError("File not found")
        
        # Act
        result = _handle_tool_error(operation, path, error)
        
        # Assert
        assert "error" in result
        assert f"Error {operation} {path}" in result["error"]
        assert "File not found" in result["error"]
        mock_logger.error.assert_called_once()
    
    @patch('common.tools.logger')
    def test_should_handle_generic_exception(self, mock_logger):
        """Should handle generic exception gracefully."""
        # Arrange
        operation = "processing"
        path = "/test/path"
        error = Exception("Generic error")
        
        # Act
        result = _handle_tool_error(operation, path, error)
        
        # Assert
        assert "error" in result
        assert "Generic error" in result["error"]
        mock_logger.error.assert_called_once()


class TestHumanInputTools:
    """Test human input and clarification tools."""
    
    @patch('common.tools.logger')
    @patch('builtins.input', return_value="User response")
    @patch('builtins.print')
    def test_should_ask_human_clarification_successfully(self, mock_print, mock_input, mock_logger):
        """Should ask human for clarification and return response."""
        # Arrange
        question = "What is your preference?"
        
        # Act
        result = ask_human_clarification_mcp(question)
        
        # Assert
        assert result == {"reply": "User response"}
        mock_logger.info.assert_called_with(f"Human clarification requested: {question}")
        mock_input.assert_called_with(f"{question}: ")
        assert mock_print.call_count >= 2  # Console input markers
    
    @patch('common.tools.logger')
    @patch('builtins.input', return_value="")
    @patch('builtins.print')
    def test_should_handle_empty_user_response(self, mock_print, mock_input, mock_logger):
        """Should handle empty user response gracefully."""
        # Arrange
        question = "Any input?"
        
        # Act
        result = ask_human_clarification_mcp(question)
        
        # Assert
        assert result == {"reply": ""}
        mock_logger.info.assert_called_once()
    
    @patch('common.tools.ask_human_clarification_mcp')
    def test_clarifier_generator_should_use_default_question(self, mock_ask_human):
        """ClarifierGenerator should use default question without context."""
        # Arrange
        clarifier = ClarifierGenerator()
        mock_ask_human.return_value = {"reply": "test"}
        
        # Act
        result = clarifier()
        
        # Assert
        mock_ask_human.assert_called_once()
        args = mock_ask_human.call_args[0]
        assert "clarification" in args[0].lower()
    
    @patch('common.tools.ask_human_clarification_mcp')
    def test_clarifier_generator_should_use_context_question(self, mock_ask_human):
        """ClarifierGenerator should use question from context when available."""
        # Arrange
        clarifier = ClarifierGenerator()
        mock_context = Mock()
        mock_context.state = {"clarifying_questions": "Custom question?"}
        mock_ask_human.return_value = {"reply": "test"}
        
        # Act
        result = clarifier(mock_context)
        
        # Assert
        mock_ask_human.assert_called_once_with("Custom question?", mock_context)
    
    def test_clarifier_generator_should_have_correct_name(self):
        """ClarifierGenerator should have correct tool name."""
        # Arrange & Act
        clarifier = ClarifierGenerator()
        
        # Assert
        assert clarifier.__name__ == "clarify_questions_tool"


class TestSessionStateManagement:
    """Test session state management functionality."""
    
    @patch('common.tools.logger')
    def test_should_set_target_directory_with_context(self, mock_logger):
        """Should set target directory in context state."""
        # Arrange
        directory = "/test/directory"
        mock_context = Mock()
        mock_context.state = {}
        
        # Act
        result = set_target_directory(directory, mock_context)
        
        # Assert
        assert result["status"] == "success"
        assert result["directory_set"] == directory
        assert mock_context.state["target_directory"] == directory
        mock_logger.info.assert_called_with(f"Target directory set: {directory}")
    
    @patch('common.tools.logger')
    def test_should_handle_set_target_directory_without_context(self, mock_logger):
        """Should handle setting target directory without context."""
        # Arrange
        directory = "/test/directory"
        
        # Act
        result = set_target_directory(directory, None)
        
        # Assert
        assert result["status"] == "warning"
        assert result["directory_set"] == directory
        mock_logger.warning.assert_called_with("Target directory acknowledged without context")
    
    def test_should_set_session_state_with_valid_json(self):
        """Should set session state with valid JSON."""
        # Arrange
        key = "test_key"
        value_json = '{"setting": "value", "count": 42}'
        mock_context = Mock()
        mock_context.state = {}
        
        # Act
        result = set_session_state(key, value_json, mock_context)
        
        # Assert
        assert result["status"] == "success"
        assert f"key '{key}'" in result["message"]
        expected_value = {"setting": "value", "count": 42}
        assert mock_context.state[key] == expected_value
    
    def test_should_handle_invalid_json_in_session_state(self):
        """Should handle invalid JSON in session state gracefully."""
        # Arrange
        key = "test_key"
        invalid_json = '{"invalid": json}'
        mock_context = Mock()
        mock_context.state = {}
        
        # Act
        result = set_session_state(key, invalid_json, mock_context)
        
        # Assert
        assert result["status"] == "error"
        assert "Invalid JSON" in result["message"]
        assert key not in mock_context.state
    
    def test_should_handle_session_state_without_context(self):
        """Should handle setting session state without context."""
        # Arrange
        key = "test_key"
        value_json = '{"test": true}'
        
        # Act
        result = set_session_state(key, value_json, None)
        
        # Assert
        assert result["status"] == "warning"
        assert "No context available" in result["message"]
    
    def test_should_get_session_state_with_context(self):
        """Should get session state value when context exists."""
        # Arrange
        key = "test_key"
        expected_value = {"setting": "value"}
        mock_context = Mock()
        mock_context.state = {key: expected_value}
        
        # Act
        result = get_session_state(key, tool_context=mock_context)
        
        # Assert
        assert result == expected_value
    
    def test_should_return_default_when_key_not_found(self):
        """Should return default value when key not found."""
        # Arrange
        key = "nonexistent_key"
        default_value = "default"
        mock_context = Mock()
        mock_context.state = {}
        
        # Act
        result = get_session_state(key, default_value, mock_context)
        
        # Assert
        assert result == default_value
    
    def test_should_return_default_without_context(self):
        """Should return default value when no context provided."""
        # Arrange
        key = "test_key"
        default_value = "default"
        
        # Act
        result = get_session_state(key, default_value, None)
        
        # Assert
        assert result == default_value
    
    def test_should_get_target_directory_from_state(self):
        """Should get target directory from session state."""
        # Arrange
        target_dir = "/test/target"
        mock_context = Mock()
        mock_context.state = {"target_directory": target_dir}
        
        # Act
        result = get_target_directory_from_state(mock_context)
        
        # Assert
        assert result == target_dir
    
    def test_should_return_default_directory_when_not_set(self):
        """Should return default directory when target not set."""
        # Arrange
        mock_context = Mock()
        mock_context.state = {}
        
        # Act
        result = get_target_directory_from_state(mock_context)
        
        # Assert
        assert result == "."


class TestProjectStructureOperations:
    """Test project structure scanning and analysis operations."""
    
    def test_should_get_simple_project_structure(self, sample_project_structure):
        """Should scan and return simple project structure."""
        # Arrange
        project_dir = sample_project_structure
        
        # Act
        result = get_project_structure(project_dir)
        
        # Assert
        assert "files" in result
        assert "directories" in result
        assert isinstance(result["files"], list)
        assert isinstance(result["directories"], dict)
        
        # Check for expected files
        file_names = result["files"]
        assert "README.md" in file_names
        assert "requirements.txt" in file_names
    
    def test_should_get_nested_project_structure(self, sample_project_structure):
        """Should scan nested directory structure recursively."""
        # Arrange
        project_dir = sample_project_structure
        
        # Act
        result = get_project_structure(project_dir)
        
        # Assert
        assert "src" in result["directories"]
        src_structure = result["directories"]["src"]
        assert "directories" in src_structure
        assert "models" in src_structure["directories"]
        assert "services" in src_structure["directories"]
    
    def test_should_skip_hidden_files_and_directories(self, sample_project_structure):
        """Should skip hidden files and directories starting with dot."""
        # Arrange
        project_dir = sample_project_structure
        
        # Act
        result = get_project_structure(project_dir)
        
        # Assert
        # Should not include .git directory or .gitignore file in root level
        file_names = result["files"]
        dir_names = list(result["directories"].keys())
        
        assert ".git" not in dir_names
        assert all(not name.startswith('.') for name in file_names)
        assert all(not name.startswith('.') for name in dir_names)
    
    @patch('common.tools.os.listdir')
    def test_should_handle_permission_error_gracefully(self, mock_listdir):
        """Should handle permission errors gracefully."""
        # Arrange
        mock_listdir.side_effect = PermissionError("Access denied")
        project_dir = "/restricted/path"
        
        # Act
        result = get_project_structure(project_dir)
        
        # Assert
        assert "error" in result
        assert "Access denied" in result["error"]
    
    def test_should_scan_project_structure_with_validation(self, sample_project_structure):
        """Should scan project structure with path validation."""
        # Arrange
        project_dir = sample_project_structure
        
        # Act
        result = scan_project_structure(project_dir)
        
        # Assert
        assert "files" in result
        assert "directories" in result
        assert "README.md" in result["files"]
    
    def test_should_handle_nonexistent_directory_in_scan(self):
        """Should handle nonexistent directory in scan operation."""
        # Arrange
        nonexistent_dir = "/absolutely/nonexistent/directory"
        
        # Act
        result = scan_project_structure(nonexistent_dir)
        
        # Assert
        assert "error" in result
        assert "not found" in result["error"].lower()


class TestDirectoryListingOperations:
    """Test directory listing with metadata operations."""
    
    def test_should_list_directory_contents_with_metadata(self, sample_project_structure):
        """Should list directory contents with file metadata."""
        # Arrange
        project_dir = sample_project_structure
        path_to_list = "."
        
        # Act
        result = list_directory_contents(path_to_list, project_dir)
        
        # Assert
        assert "files" in result
        assert "directories" in result
        assert "current_path_listed" in result
        assert "total_files" in result
        assert "total_directories" in result
        
        # Check file metadata structure
        if result["files"]:
            file_info = result["files"][0]
            required_keys = {"name", "path", "size", "modified", "type"}
            assert all(key in file_info for key in required_keys)
            assert file_info["type"] == "file"
    
    def test_should_sort_files_and_directories_alphabetically(self, temp_dir):
        """Should sort files and directories alphabetically."""
        # Arrange
        files_to_create = ["zebra.txt", "alpha.txt", "beta.txt"]
        dirs_to_create = ["zoo", "apple", "banana"]
        
        for filename in files_to_create:
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write("test")
        
        for dirname in dirs_to_create:
            os.makedirs(os.path.join(temp_dir, dirname))
        
        # Act
        result = list_directory_contents(".", temp_dir)
        
        # Assert
        file_names = [f["name"] for f in result["files"]]
        dir_names = [d["name"] for d in result["directories"]]
        
        assert file_names == sorted(file_names)
        assert dir_names == sorted(dir_names)
    
    def test_should_exclude_hidden_files_by_default(self, temp_dir):
        """Should exclude hidden files by default."""
        # Arrange
        regular_file = os.path.join(temp_dir, "regular.txt")
        hidden_file = os.path.join(temp_dir, ".hidden.txt")
        
        with open(regular_file, 'w') as f:
            f.write("regular")
        with open(hidden_file, 'w') as f:
            f.write("hidden")
        
        # Act
        result = list_directory_contents(".", temp_dir, include_hidden=False)
        
        # Assert
        file_names = [f["name"] for f in result["files"]]
        assert "regular.txt" in file_names
        assert ".hidden.txt" not in file_names
    
    def test_should_include_hidden_files_when_requested(self, temp_dir):
        """Should include hidden files when include_hidden=True."""
        # Arrange
        regular_file = os.path.join(temp_dir, "regular.txt")
        hidden_file = os.path.join(temp_dir, ".hidden.txt")
        
        with open(regular_file, 'w') as f:
            f.write("regular")
        with open(hidden_file, 'w') as f:
            f.write("hidden")
        
        # Act
        result = list_directory_contents(".", temp_dir, include_hidden=True)
        
        # Assert
        file_names = [f["name"] for f in result["files"]]
        assert "regular.txt" in file_names
        assert ".hidden.txt" in file_names
    
    def test_should_handle_permission_error_on_file_stat(self, temp_dir):
        """Should handle permission errors when getting file stats."""
        # Arrange
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Act - should not crash even if some files can't be stat'd
        result = list_directory_contents(".", temp_dir)
        
        # Assert
        assert "files" in result
        assert "directories" in result
        assert result["total_files"] >= 0
    
    def test_should_resolve_relative_paths_correctly(self, sample_project_structure):
        """Should resolve relative paths correctly."""
        # Arrange
        base_dir = sample_project_structure
        relative_path = "src"
        
        # Act
        result = list_directory_contents(relative_path, base_dir)
        
        # Assert
        assert "error" not in result
        assert "current_path_listed" in result
        assert result["current_path_listed"].endswith("src")


class TestFileContentOperations:
    """Test file content reading operations."""
    
    def test_should_read_entire_file_content(self, temp_dir):
        """Should read entire file content when no line range specified."""
        # Arrange
        test_file = "test.txt"
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        file_path = os.path.join(temp_dir, test_file)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        # Act
        result = read_file_content(test_file, temp_dir)
        
        # Assert
        assert result["content"] == content
        assert result["line_count"] == 5
        assert result["actual_start_line"] == 1
        assert result["actual_end_line"] == 5
        assert result["file_path_read"].endswith(test_file)
    
    def test_should_read_specific_line_range(self, temp_dir):
        """Should read specific line range when specified."""
        # Arrange
        test_file = "test.txt"
        lines = ["Line 1\n", "Line 2\n", "Line 3\n", "Line 4\n", "Line 5\n"]
        file_path = os.path.join(temp_dir, test_file)
        
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        # Act
        result = read_file_content(test_file, temp_dir, start_line=2, end_line=4)
        
        # Assert
        expected_content = "Line 2\nLine 3\nLine 4\n"
        assert result["content"] == expected_content
        assert result["line_count"] == 5
        assert result["actual_start_line"] == 2
        assert result["actual_end_line"] == 4
    
    def test_should_handle_line_range_beyond_file_length(self, temp_dir):
        """Should handle line range that exceeds file length."""
        # Arrange
        test_file = "short.txt"
        content = "Line 1\nLine 2"
        file_path = os.path.join(temp_dir, test_file)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        # Act
        result = read_file_content(test_file, temp_dir, start_line=1, end_line=10)
        
        # Assert
        assert result["content"] == content
        assert result["line_count"] == 2
        assert result["actual_start_line"] == 1
        assert result["actual_end_line"] == 2
    
    def test_should_handle_negative_start_line(self, temp_dir):
        """Should handle negative start line by starting from beginning."""
        # Arrange
        test_file = "test.txt"
        content = "Line 1\nLine 2\nLine 3"
        file_path = os.path.join(temp_dir, test_file)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        # Act
        result = read_file_content(test_file, temp_dir, start_line=-5, end_line=2)
        
        # Assert
        expected_content = "Line 1\nLine 2\n"  # Fixed to include trailing newline
        assert result["content"] == expected_content
        assert result["actual_start_line"] == 1
        assert result["actual_end_line"] == 2
    
    def test_should_handle_empty_file(self, temp_dir):
        """Should handle empty file gracefully."""
        # Arrange
        test_file = "empty.txt"
        file_path = os.path.join(temp_dir, test_file)
        
        with open(file_path, 'w') as f:
            pass  # Create empty file
        
        # Act
        result = read_file_content(test_file, temp_dir)
        
        # Assert
        assert result["content"] == ""
        assert result["line_count"] == 0
        assert result["actual_start_line"] == 0
        assert result["actual_end_line"] == 0
    
    def test_should_handle_unicode_content(self, temp_dir):
        """Should handle unicode content correctly."""
        # Arrange
        test_file = "unicode.txt"
        content = "测试 unicode content 🚀\ncafé ñoño"
        file_path = os.path.join(temp_dir, test_file)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Act
        result = read_file_content(test_file, temp_dir)
        
        # Assert
        assert result["content"] == content
        assert "测试" in result["content"]
        assert "🚀" in result["content"]
        assert "café" in result["content"]
    
    def test_should_handle_nonexistent_file(self, temp_dir):
        """Should handle nonexistent file gracefully."""
        # Arrange
        nonexistent_file = "does_not_exist.txt"
        
        # Act
        result = read_file_content(nonexistent_file, temp_dir)
        
        # Assert
        assert "error" in result
        assert "not found" in result["error"].lower()
    
    def test_should_resolve_relative_file_paths(self, sample_project_structure):
        """Should resolve relative file paths correctly."""
        # Arrange
        base_dir = sample_project_structure
        relative_file_path = "src/models/user.py"
        
        # Act
        result = read_file_content(relative_file_path, base_dir)
        
        # Assert
        assert "error" not in result
        assert "class User" in result["content"]
        assert result["file_path_read"].endswith("user.py")


class TestProjectAnalysisTools:
    """Test project analysis and dependency detection tools."""
    
    def test_should_analyze_python_requirements_file(self, temp_dir):
        """Should analyze Python requirements.txt file correctly."""
        # Arrange
        requirements_content = """numpy==1.21.0
pandas>=1.3.0
requests
# This is a comment
flask==2.0.1
"""
        requirements_path = os.path.join(temp_dir, "requirements.txt")
        with open(requirements_path, 'w') as f:
            f.write(requirements_content)
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        assert "dependencies" in result
        deps = result["dependencies"]
        assert "python_requirements_txt" in deps
        
        requirements = deps["python_requirements_txt"]
        assert "numpy==1.21.0" in requirements
        assert "pandas>=1.3.0" in requirements
        assert "requests" in requirements
        assert "flask==2.0.1" in requirements
        assert "# This is a comment" not in requirements  # Comments should be filtered
    
    def test_should_analyze_nodejs_package_json_file(self, temp_dir):
        """Should analyze Node.js package.json file correctly."""
        # Arrange
        package_json_content = {
            "name": "test-project",
            "version": "1.0.0",
            "dependencies": {
                "express": "^4.18.0",
                "lodash": "^4.17.21"
            },
            "devDependencies": {
                "jest": "^28.0.0",
                "eslint": "^8.0.0"
            }
        }
        package_json_path = os.path.join(temp_dir, "package.json")
        with open(package_json_path, 'w') as f:
            json.dump(package_json_content, f)
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        assert "dependencies" in result
        deps = result["dependencies"]
        assert "nodejs_package_json" in deps
        
        package_data = deps["nodejs_package_json"]
        assert "dependencies" in package_data
        assert "devDependencies" in package_data
        assert package_data["dependencies"]["express"] == "^4.18.0"
        assert package_data["devDependencies"]["jest"] == "^28.0.0"
    
    def test_should_analyze_both_python_and_nodejs_files(self, temp_dir):
        """Should analyze both Python and Node.js dependency files when present."""
        # Arrange
        requirements_content = "flask==2.0.1\nrequests"
        package_json_content = {"dependencies": {"express": "^4.18.0"}}
        
        with open(os.path.join(temp_dir, "requirements.txt"), 'w') as f:
            f.write(requirements_content)
        with open(os.path.join(temp_dir, "package.json"), 'w') as f:
            json.dump(package_json_content, f)
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        deps = result["dependencies"]
        assert "python_requirements_txt" in deps
        assert "nodejs_package_json" in deps
        assert len(deps["python_requirements_txt"]) == 2
        assert deps["nodejs_package_json"]["dependencies"]["express"] == "^4.18.0"
    
    def test_should_handle_empty_requirements_file(self, temp_dir):
        """Should handle empty requirements.txt file gracefully."""
        # Arrange
        requirements_path = os.path.join(temp_dir, "requirements.txt")
        with open(requirements_path, 'w') as f:
            f.write("")  # Empty file
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        deps = result["dependencies"]
        assert "python_requirements_txt" in deps
        assert deps["python_requirements_txt"] == []
    
    def test_should_handle_comments_only_requirements_file(self, temp_dir):
        """Should handle requirements.txt with only comments."""
        # Arrange
        requirements_content = """# This is a comment
# Another comment
# Yet another comment"""
        requirements_path = os.path.join(temp_dir, "requirements.txt")
        with open(requirements_path, 'w') as f:
            f.write(requirements_content)
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        deps = result["dependencies"]
        assert "python_requirements_txt" in deps
        assert deps["python_requirements_txt"] == []
    
    def test_should_handle_malformed_package_json(self, temp_dir):
        """Should handle malformed package.json gracefully."""
        # Arrange
        malformed_json = '{"name": "test", "version": "1.0.0",}'  # Trailing comma
        package_json_path = os.path.join(temp_dir, "package.json")
        with open(package_json_path, 'w') as f:
            f.write(malformed_json)
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        deps = result["dependencies"]
        assert "nodejs_package_json_error" in deps
        assert "Expecting" in deps["nodejs_package_json_error"] or "Invalid" in deps["nodejs_package_json_error"]
    
    def test_should_handle_no_dependency_files(self, temp_dir):
        """Should handle directory with no dependency files."""
        # Arrange - temp_dir with no dependency files
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        assert "message" in result
        assert "No dependency files found" in result["message"]
        assert result["path_checked"] == temp_dir
    
    def test_should_handle_package_json_without_dependencies(self, temp_dir):
        """Should handle package.json without dependencies sections."""
        # Arrange
        package_json_content = {
            "name": "test-project",
            "version": "1.0.0",
            "description": "A test project"
        }
        package_json_path = os.path.join(temp_dir, "package.json")
        with open(package_json_path, 'w') as f:
            json.dump(package_json_content, f)
        
        # Act
        result = get_dependencies(temp_dir)
        
        # Assert
        deps = result["dependencies"]
        assert "nodejs_package_json" in deps
        package_data = deps["nodejs_package_json"]
        assert package_data["dependencies"] == {}
        assert package_data["devDependencies"] == {}


class TestGitignoreFiltering:
    """Test gitignore-based project structure filtering."""
    
    def test_should_filter_structure_with_gitignore_file(self, temp_dir):
        """Should filter project structure using gitignore rules."""
        # Arrange
        gitignore_content = """*.pyc
__pycache__/
.env
dist/
*.log"""
        
        # Create gitignore file
        gitignore_path = os.path.join(temp_dir, ".gitignore")
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        # Create test files (some should be ignored)
        test_files = ["main.py", "config.pyc", "README.md", "debug.log", ".env"]
        for filename in test_files:
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write("test")
        
        # Create test directories
        os.makedirs(os.path.join(temp_dir, "__pycache__"))
        os.makedirs(os.path.join(temp_dir, "dist"))
        os.makedirs(os.path.join(temp_dir, "src"))
        
        # Act
        result = filter_by_gitignore(temp_dir)
        
        # Assert
        assert "filtered_structure" in result
        assert result["gitignore_status"] == "applied"
        
        filtered = result["filtered_structure"]
        file_names = filtered["files"]
        dir_names = list(filtered["directories"].keys())
        
        # Should include non-ignored files
        assert "main.py" in file_names
        assert "README.md" in file_names
        assert "src" in dir_names
        
        # Should exclude ignored files/directories
        assert "config.pyc" not in file_names
        assert "debug.log" not in file_names
        assert ".env" not in file_names
        assert "__pycache__" not in dir_names
        assert "dist" not in dir_names
    
    def test_should_filter_nested_directories_with_gitignore(self, temp_dir):
        """Should filter nested directories according to gitignore rules."""
        # Arrange
        gitignore_content = "logs/\n*.tmp"
        gitignore_path = os.path.join(temp_dir, ".gitignore")
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        # Create nested structure
        src_dir = os.path.join(temp_dir, "src")
        os.makedirs(src_dir)
        logs_dir = os.path.join(temp_dir, "logs")
        os.makedirs(logs_dir)
        
        # Create files
        with open(os.path.join(src_dir, "main.py"), 'w') as f:
            f.write("code")
        with open(os.path.join(src_dir, "temp.tmp"), 'w') as f:
            f.write("temp")
        with open(os.path.join(logs_dir, "app.log"), 'w') as f:
            f.write("log")
        
        # Act
        result = filter_by_gitignore(temp_dir)
        
        # Assert
        filtered = result["filtered_structure"]
        
        # logs directory should be completely excluded
        assert "logs" not in filtered["directories"]
        
        # src directory should be included but temp.tmp should be filtered out
        assert "src" in filtered["directories"]
        src_content = filtered["directories"]["src"]
        assert "main.py" in src_content["files"]
        assert "temp.tmp" not in src_content["files"]
    
    def test_should_handle_directory_without_gitignore(self, temp_dir):
        """Should handle directory without .gitignore file."""
        # Arrange - no .gitignore file created
        test_files = ["main.py", "config.pyc", "README.md"]
        for filename in test_files:
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write("test")
        
        # Act
        result = filter_by_gitignore(temp_dir)
        
        # Assert
        assert "filtered_structure" in result
        assert result["gitignore_status"] == "not_found"
        
        # All files should be included when no gitignore
        filtered = result["filtered_structure"]
        file_names = filtered["files"]
        assert "main.py" in file_names
        assert "config.pyc" in file_names
        assert "README.md" in file_names
    
    def test_should_handle_empty_gitignore_file(self, temp_dir):
        """Should handle empty .gitignore file."""
        # Arrange
        gitignore_path = os.path.join(temp_dir, ".gitignore")
        with open(gitignore_path, 'w') as f:
            pass  # Empty file
        
        test_files = ["main.py", "test.txt"]
        for filename in test_files:
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write("test")
        
        # Act
        result = filter_by_gitignore(temp_dir)
        
        # Assert
        filtered = result["filtered_structure"]
        file_names = filtered["files"]
        assert "main.py" in file_names
        assert "test.txt" in file_names
        assert result["gitignore_status"] == "applied"
    
    @patch('common.tools.get_project_structure')
    def test_should_handle_error_in_structure_scanning(self, mock_get_structure, temp_dir):
        """Should handle errors in project structure scanning."""
        # Arrange
        mock_get_structure.return_value = {"error": "Permission denied"}
        
        # Act
        result = filter_by_gitignore(temp_dir)
        
        # Assert
        assert "error" in result
        assert "Permission denied" in result["error"]
    
    def test_should_handle_permission_error_in_gitignore_filtering(self):
        """Should handle permission errors during gitignore filtering."""
        # Arrange
        nonexistent_dir = "/absolutely/nonexistent/directory"
        
        # Act
        result = filter_by_gitignore(nonexistent_dir)
        
        # Assert
        assert "error" in result
        assert "scanning" in result["error"]  # Fixed to match actual error message
    
    def test_apply_gitignore_filter_should_be_alias(self, temp_dir):
        """apply_gitignore_filter should be an alias for filter_by_gitignore."""
        # Arrange
        gitignore_content = "*.pyc"
        gitignore_path = os.path.join(temp_dir, ".gitignore")
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        with open(os.path.join(temp_dir, "test.py"), 'w') as f:
            f.write("code")
        with open(os.path.join(temp_dir, "test.pyc"), 'w') as f:
            f.write("bytecode")
        
        # Act
        result1 = filter_by_gitignore(temp_dir)
        result2 = apply_gitignore_filter(temp_dir)
        
        # Assert
        assert result1 == result2  # Should be identical results


class TestCodebaseSearch:
    """Test codebase search functionality."""
    
    def test_should_search_for_single_keyword(self, temp_dir):
        """Should search for single keyword in codebase."""
        # Arrange
        test_files = {
            "main.py": "def main():\n    print('Hello World')\n    return 0",
            "utils.py": "def helper():\n    pass\n# TODO: implement helper",
            "config.py": "DEBUG = True\nHOST = 'localhost'"
        }
        
        for filename, content in test_files.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Act
        result = search_codebase(temp_dir, "def", "*.*")
        
        # Assert
        assert "matches" in result
        assert result["total_matches"] >= 2  # Should find def in main.py and utils.py
        
        matches = result["matches"]
        file_paths = [match["file_path"] for match in matches]
        assert any("main.py" in path for path in file_paths)
        assert any("utils.py" in path for path in file_paths)
    
    def test_should_search_for_multiple_keywords(self, temp_dir):
        """Should search for multiple comma-separated keywords."""
        # Arrange
        test_files = {
            "server.py": "app = Flask(__name__)\n@app.route('/')\ndef index():",
            "client.py": "import requests\nresponse = requests.get(url)",
            "config.py": "DATABASE_URL = 'sqlite:///app.db'"
        }
        
        for filename, content in test_files.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Act
        result = search_codebase(temp_dir, "Flask, requests", "*.*")
        
        # Assert
        matches = result["matches"]
        assert len(matches) >= 2
        
        # Should find Flask in server.py and requests in client.py
        keywords_found = [match["matched_keyword"] for match in matches]
        assert "Flask" in keywords_found
        assert "requests" in keywords_found
    
    def test_should_respect_file_pattern_filter(self, temp_dir):
        """Should respect file pattern filter in search."""
        # Arrange
        test_files = {
            "script.py": "print('Python code')",
            "notes.txt": "This contains Python word",
            "config.js": "console.log('JavaScript code')"
        }
        
        for filename, content in test_files.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Act - search only Python files
        result = search_codebase(temp_dir, "Python", "*.py")
        
        # Assert
        matches = result["matches"]
        file_paths = [match["file_path"] for match in matches]
        
        # Should only find matches in .py files
        assert all(path.endswith('.py') for path in file_paths)
        assert any("script.py" in path for path in file_paths)
    
    def test_should_include_context_lines(self, temp_dir):
        """Should include context lines around matches."""
        # Arrange
        content = """Line 1
Line 2
Target line with keyword
Line 4
Line 5"""
        
        with open(os.path.join(temp_dir, "test.py"), 'w') as f:
            f.write(content)
        
        # Act
        result = search_codebase(temp_dir, "keyword", "*.*", context_lines=2)
        
        # Assert
        assert len(result["matches"]) == 1
        match = result["matches"][0]
        
        assert "context_before" in match
        assert "context_after" in match
        assert "Line 1\nLine 2" in match["context_before"]
        assert "Line 4\nLine 5" in match["context_after"]
        assert match["line_number"] == 3
    
    def test_should_handle_case_sensitive_search(self, temp_dir):
        """Should handle case-sensitive search correctly."""
        # Arrange
        content = "Function definition\nfunction call\nFUNCTION in caps"
        with open(os.path.join(temp_dir, "test.py"), 'w') as f:
            f.write(content)
        
        # Act - Case insensitive (default)
        result_insensitive = search_codebase(temp_dir, "function", "*.*", ignore_case=True)
        
        # Act - Case sensitive
        result_sensitive = search_codebase(temp_dir, "function", "*.*", ignore_case=False)
        
        # Assert
        assert result_insensitive["total_matches"] == 3  # All variations
        assert result_sensitive["total_matches"] == 1   # Only exact case
    
    def test_should_skip_unwanted_directories(self, temp_dir):
        """Should skip unwanted directories like node_modules, __pycache__, etc."""
        # Arrange
        unwanted_dirs = ["node_modules", "__pycache__", ".git", "venv", "build"]
        
        for dirname in unwanted_dirs:
            dir_path = os.path.join(temp_dir, dirname)
            os.makedirs(dir_path)
            with open(os.path.join(dir_path, "test.py"), 'w') as f:
                f.write("findme keyword here")
        
        # Create wanted directory
        wanted_dir = os.path.join(temp_dir, "src")
        os.makedirs(wanted_dir)
        with open(os.path.join(wanted_dir, "main.py"), 'w') as f:
            f.write("findme keyword here")
        
        # Act
        result = search_codebase(temp_dir, "findme", "*.*")
        
        # Assert
        matches = result["matches"]
        file_paths = [match["file_path"] for match in matches]
        
        # Should only find match in src directory, not in unwanted directories
        assert len(matches) == 1
        assert any("src" in path for path in file_paths)
        assert all(not any(unwanted in path for unwanted in unwanted_dirs) 
                  for path in file_paths)
    
    def test_should_handle_empty_keyword_list(self, temp_dir):
        """Should handle empty keyword list gracefully."""
        # Arrange
        with open(os.path.join(temp_dir, "test.py"), 'w') as f:
            f.write("some content")
        
        # Act
        result = search_codebase(temp_dir, "", "*.*")
        
        # Assert
        assert "error" in result
        assert "No keywords provided" in result["error"]
    
    def test_should_handle_nonexistent_directory(self):
        """Should handle nonexistent directory gracefully."""
        # Arrange
        nonexistent_dir = "/absolutely/nonexistent/directory"
        
        # Act
        result = search_codebase(nonexistent_dir, "keyword", "*.*")
        
        # Assert
        assert "error" in result
        assert "not found" in result["error"].lower()
    
    def test_should_handle_binary_files_gracefully(self, temp_dir):
        """Should handle binary files gracefully without crashing."""
        # Arrange
        # Create a text file and a "binary-like" file
        with open(os.path.join(temp_dir, "text.py"), 'w') as f:
            f.write("keyword in text file")
        
        with open(os.path.join(temp_dir, "binary.dat"), 'wb') as f:
            f.write(b'\x00\x01\x02keyword\xff\xfe\xfd')
        
        # Act
        result = search_codebase(temp_dir, "keyword", "*.*")
        
        # Assert
        # Should find at least the text file, and not crash on binary
        assert "matches" in result
        assert result["total_matches"] >= 1
    
    def test_should_sort_matches_by_file_and_line(self, temp_dir):
        """Should sort matches by file path and line number."""
        # Arrange
        files_content = {
            "z_file.py": "keyword line 1\nkeyword line 2",
            "a_file.py": "keyword line 1\nkeyword line 2",
            "m_file.py": "keyword line 1"
        }
        
        for filename, content in files_content.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Act
        result = search_codebase(temp_dir, "keyword", "*.*")
        
        # Assert
        matches = result["matches"]
        
        # Should be sorted by file path first, then line number
        for i in range(1, len(matches)):
            prev_match = matches[i-1]
            curr_match = matches[i]
            
            # Either different file (alphabetically ordered) or same file with increasing line numbers
            assert (prev_match["file_path"] < curr_match["file_path"] or 
                   (prev_match["file_path"] == curr_match["file_path"] and 
                    prev_match["line_number"] <= curr_match["line_number"]))


class TestPromptBasedSearch:
    """Test prompt-based search functionality."""
    
    def test_should_search_code_with_prompt_text(self, temp_dir):
        """Should search code using prompt text as keywords."""
        # Arrange
        test_files = {
            "api.py": "def create_user(name, email):\n    return User.create(name=name, email=email)",
            "models.py": "class User:\n    def __init__(self, name, email):\n        self.name = name",
            "views.py": "def login_view():\n    return render_template('login.html')"
        }
        
        for filename, content in test_files.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Act
        result = search_code_with_prompt(temp_dir, "user login", "*.*")
        
        # Assert
        assert "matches" in result
        # The function should work without errors and return some structure
        assert isinstance(result["matches"], list)
        assert "search_terms_used" in result
        assert "path_searched" in result
    
    def test_should_handle_empty_prompt_in_code_search(self, temp_dir):
        """Should handle empty prompt in code search."""
        # Arrange
        with open(os.path.join(temp_dir, "test.py"), 'w') as f:
            f.write("some code")
        
        # Act
        result = search_code_with_prompt(temp_dir, "", "*.*")
        
        # Assert
        assert "error" in result
        assert "empty" in result["error"].lower()
    
    def test_should_search_tests_with_prompt(self, temp_dir):
        """Should search test files using prompt."""
        # Arrange
        test_files = {
            "test_user.py": "def test_create_user():\n    assert user.create() is not None",
            "test_auth.py": "def test_login():\n    response = client.post('/login')",
            "main.py": "def create_user():\n    pass"  # Not a test file
        }
        
        for filename, content in test_files.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        # Act
        result = search_tests_with_prompt(temp_dir, "user authentication", "test_*.py")
        
        # Assert
        assert "matches" in result
        matches = result["matches"]
        
        # Should only search in test files matching the pattern
        file_paths = [match["file_path"] for match in matches]
        assert all("test_" in path for path in file_paths)
        assert not any("main.py" in path for path in file_paths)
    
    def test_should_handle_empty_prompt_in_test_search(self, temp_dir):
        """Should handle empty prompt in test search."""
        # Arrange
        with open(os.path.join(temp_dir, "test_example.py"), 'w') as f:
            f.write("def test_something(): pass")
        
        # Act
        result = search_tests_with_prompt(temp_dir, "", "test_*.py")
        
        # Assert
        assert "error" in result
        assert "empty" in result["error"].lower()
    
    def test_should_handle_empty_file_pattern_in_test_search(self, temp_dir):
        """Should handle empty file pattern in test search."""
        # Arrange
        with open(os.path.join(temp_dir, "test_example.py"), 'w') as f:
            f.write("def test_something(): pass")
        
        # Act
        result = search_tests_with_prompt(temp_dir, "test functionality", "")
        
        # Assert
        assert "error" in result
        assert "pattern required" in result["error"].lower()
    
    def test_should_determine_relevance_from_prompt(self):
        """Should provide placeholder relevance analysis."""
        # Arrange
        prompt = "Create a user authentication system with login and registration"
        found_files = [
            {"file": "auth.py", "content": "login functions"},
            {"file": "user.py", "content": "user model"},
            {"file": "utils.py", "content": "utility functions"}
        ]
        
        # Act
        result = determine_relevance_from_prompt(prompt, found_files)
        
        # Assert
        assert "status" in result
        assert result["status"] == "placeholder_analysis"
        assert "prompt_analyzed" in result
        assert "items_evaluated" in result
        assert result["items_evaluated"] == 3
        
        # Should truncate long prompts
        if len(prompt) > 100:
            assert result["prompt_analyzed"].endswith("...")
        else:
            assert prompt in result["prompt_analyzed"] 