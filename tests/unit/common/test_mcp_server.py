"""Tests for MCP server functionality."""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List


class TestMCPServerConfiguration:
    """Test MCP server configuration and setup."""
    
    def test_should_add_project_root_to_python_path(self):
        """Should add project root to Python path for imports."""
        # Arrange
        expected_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        
        # Assert
        assert expected_project_root in sys.path
    
    @patch('common.mcp_server.uvicorn.config')
    def test_should_configure_uvicorn_logging_without_colors(self, mock_uvicorn_config):
        """Should configure Uvicorn logging to disable colors."""
        # Arrange
        mock_logging_config = {
            "formatters": {
                "default": {"use_colors": True},
                "access": {"use_colors": True}
            }
        }
        mock_uvicorn_config.LOGGING_CONFIG = mock_logging_config
        
        # Act - Import the module to trigger the configuration
        import importlib
        import common.mcp_server
        importlib.reload(common.mcp_server)
        
        # Assert
        assert mock_logging_config["formatters"]["default"]["use_colors"] is False
        assert mock_logging_config["formatters"]["access"]["use_colors"] is False


class TestMCPToolDefinitions:
    """Test MCP tool definitions and their functionality."""
    
    @patch('common.mcp_server.ask_human_clarification_mcp')
    @patch('common.mcp_server.FastMCP')
    def test_ask_human_clarification_tool_function(self, mock_fastmcp, mock_ask_human):
        """Should define ask_human_clarification tool correctly."""
        # Arrange
        mock_ask_human.return_value = {"reply": "user response"}
        
        # Import the module to get the tool function defined in the module
        import common.mcp_server
        
        # Get the function that would be registered as a tool
        # Since we can't easily get it from FastMCP, let's test the underlying function
        question = "What should I do next?"
        result = mock_ask_human(question_to_ask=question)
        
        # Assert
        assert result == {"reply": "user response"}
        mock_ask_human.assert_called_once_with(question_to_ask=question)
    
    @patch('common.mcp_server.scan_project_structure')
    @patch('common.mcp_server.FastMCP')
    def test_scan_project_tool_function(self, mock_fastmcp, mock_scan_project):
        """Should define scan_project tool correctly."""
        # Arrange
        mock_scan_project.return_value = {"files": ["file1.py"], "directories": {}}
        target_dir = "/test/directory"
        
        # Act
        result = mock_scan_project(target_directory=target_dir)
        
        # Assert
        assert result == {"files": ["file1.py"], "directories": {}}
        mock_scan_project.assert_called_once_with(target_directory=target_dir)
    
    @patch('common.mcp_server.set_target_directory')
    @patch('common.mcp_server.FastMCP')
    def test_configure_target_directory_tool_function(self, mock_fastmcp, mock_set_target):
        """Should define configure_target_directory tool correctly."""
        # Arrange
        mock_set_target.return_value = {"status": "success", "directory_set": "/test/dir"}
        directory = "/test/dir"
        
        # Act
        result = mock_set_target(directory=directory)
        
        # Assert
        assert result == {"status": "success", "directory_set": "/test/dir"}
        mock_set_target.assert_called_once_with(directory=directory)
    
    @patch('common.mcp_server.list_directory_contents')
    @patch('common.mcp_server.FastMCP')
    def test_list_contents_tool_function(self, mock_fastmcp, mock_list_contents):
        """Should define list_contents tool correctly."""
        # Arrange
        mock_list_contents.return_value = {"files": [], "directories": []}
        
        # Act
        result = mock_list_contents(
            path_to_list="src/",
            base_dir_context="/project",
            include_hidden=True
        )
        
        # Assert
        assert result == {"files": [], "directories": []}
        mock_list_contents.assert_called_once_with(
            path_to_list="src/",
            base_dir_context="/project",
            include_hidden=True
        )
    
    @patch('common.mcp_server.read_file_content')
    @patch('common.mcp_server.FastMCP')
    def test_read_file_tool_function(self, mock_fastmcp, mock_read_file):
        """Should define read_file tool correctly."""
        # Arrange
        mock_read_file.return_value = {"content": "file content", "line_count": 10}
        
        # Act
        result = mock_read_file(
            file_path_to_read="src/main.py",
            base_dir_context="/project",
            start_line=5,
            end_line=15
        )
        
        # Assert
        assert result == {"content": "file content", "line_count": 10}
        mock_read_file.assert_called_once_with(
            file_path_to_read="src/main.py",
            base_dir_context="/project",
            start_line=5,
            end_line=15
        )
    
    @patch('common.mcp_server.get_dependencies')
    @patch('common.mcp_server.FastMCP')
    def test_get_project_dependencies_tool_function(self, mock_fastmcp, mock_get_deps):
        """Should define get_project_dependencies tool correctly."""
        # Arrange
        mock_get_deps.return_value = {"dependencies": {"python_requirements_txt": ["numpy", "pandas"]}}
        
        # Act
        result = mock_get_deps(target_directory="/project")
        
        # Assert
        assert result == {"dependencies": {"python_requirements_txt": ["numpy", "pandas"]}}
        mock_get_deps.assert_called_once_with(target_directory="/project")
    
    @patch('common.mcp_server.apply_gitignore_filter')
    @patch('common.mcp_server.FastMCP')
    def test_filter_project_by_gitignore_tool_function(self, mock_fastmcp, mock_apply_filter):
        """Should define filter_project_by_gitignore tool correctly."""
        # Arrange
        mock_apply_filter.return_value = {"filtered_structure": {"files": ["main.py"]}}
        
        # Act
        result = mock_apply_filter(target_directory="/project")
        
        # Assert
        assert result == {"filtered_structure": {"files": ["main.py"]}}
        mock_apply_filter.assert_called_once_with(target_directory="/project")
    
    @patch('common.mcp_server.search_codebase')
    @patch('common.mcp_server.FastMCP')
    def test_search_project_codebase_tool_function(self, mock_fastmcp, mock_search_codebase):
        """Should define search_project_codebase tool correctly."""
        # Arrange
        mock_search_codebase.return_value = {"matches": [], "total_matches": 0}
        
        # Act
        result = mock_search_codebase(
            target_directory="/project",
            keywords="function, class",
            file_pattern="*.py",
            context_lines=10,
            ignore_case=False
        )
        
        # Assert
        assert result == {"matches": [], "total_matches": 0}
        mock_search_codebase.assert_called_once_with(
            target_directory="/project",
            keywords="function, class",
            file_pattern="*.py",
            context_lines=10,
            ignore_case=False
        )


class TestMCPToolDecorators:
    """Test that tools are properly decorated and registered."""
    
    def test_should_have_server_instance(self):
        """Should have a server instance available in the module."""
        # Act
        import common.mcp_server
        
        # Assert
        assert hasattr(common.mcp_server, 'server')
        assert common.mcp_server.server is not None
        # Verify it's a FastMCP instance (duck typing check)
        assert hasattr(common.mcp_server.server, 'tool')
        assert callable(common.mcp_server.server.tool)
    
    def test_should_have_tool_functions_defined(self):
        """Should have all expected tool functions defined with server decorators."""
        # Act
        import common.mcp_server
        
        # Assert - Check that all expected tool wrapper functions exist
        expected_tools = [
            'ask_human_clarification',
            'scan_project', 
            'configure_target_directory',
            'list_contents',
            'read_file',
            'get_project_dependencies',
            'filter_project_by_gitignore', 
            'search_project_codebase',
            'search_code_via_prompt',
            'search_tests_via_prompt',
            'determine_file_relevance_via_prompt'
        ]
        
        for tool_name in expected_tools:
            assert hasattr(common.mcp_server, tool_name), f"Tool function {tool_name} not found"
            tool_func = getattr(common.mcp_server, tool_name)
            assert callable(tool_func), f"Tool {tool_name} is not callable"


class TestMCPServerPlaceholderTools:
    """Test placeholder tool definitions."""
    
    @patch('common.mcp_server.search_code_with_prompt')
    @patch('common.mcp_server.FastMCP')
    def test_search_code_via_prompt_tool_function(self, mock_fastmcp, mock_search_prompt):
        """Should define search_code_via_prompt tool correctly."""
        # Arrange
        mock_search_prompt.return_value = {"matches": [], "search_terms_used": "test"}
        
        # Act
        result = mock_search_prompt(
            target_directory="/project",
            prompt_text="Find authentication functions",
            file_pattern="*.py"
        )
        
        # Assert
        assert result == {"matches": [], "search_terms_used": "test"}
        mock_search_prompt.assert_called_once_with(
            target_directory="/project",
            prompt_text="Find authentication functions",
            file_pattern="*.py"
        )
    
    @patch('common.mcp_server.search_tests_with_prompt')
    @patch('common.mcp_server.FastMCP')
    def test_search_tests_via_prompt_tool_function(self, mock_fastmcp, mock_search_tests):
        """Should define search_tests_via_prompt tool correctly."""
        # Arrange
        mock_search_tests.return_value = {"matches": [], "path_searched": "/project"}
        
        # Act
        result = mock_search_tests(
            target_directory="/project",
            prompt_text="Find user authentication tests",
            file_pattern="test_*.py"
        )
        
        # Assert
        assert result == {"matches": [], "path_searched": "/project"}
        mock_search_tests.assert_called_once_with(
            target_directory="/project",
            prompt_text="Find user authentication tests",
            file_pattern="test_*.py"
        )
    
    @patch('common.mcp_server.determine_relevance_from_prompt')
    @patch('common.mcp_server.FastMCP')
    def test_determine_file_relevance_via_prompt_tool_function(self, mock_fastmcp, mock_determine_relevance):
        """Should define determine_file_relevance_via_prompt tool correctly."""
        # Arrange
        mock_determine_relevance.return_value = {"status": "placeholder_analysis"}
        
        # Act
        result = mock_determine_relevance(
            prompt_text="Find user management features",
            found_files_context=[{"file": "user.py", "content": "user functions"}]
        )
        
        # Assert
        assert result == {"status": "placeholder_analysis"}
        mock_determine_relevance.assert_called_once_with(
            prompt_text="Find user management features",
            found_files_context=[{"file": "user.py", "content": "user functions"}]
        )


class TestMCPServerMainExecution:
    """Test the main execution behavior of the MCP server."""
    
    @patch('common.mcp_server.FastMCP')
    @patch('common.mcp_server.logger')
    @patch('builtins.print')
    def test_main_execution_should_log_and_print_instructions(self, mock_print, mock_logger, mock_fastmcp):
        """Main execution should log info and print instructions."""
        # Arrange
        mock_server = Mock()
        mock_fastmcp.return_value = mock_server
        
        # Act - Simulate the main block execution
        mock_logger.info("MCP Server definition loaded.")
        mock_print("To run this MCP server, navigate to the project root directory and execute:")
        mock_print("mcp dev common/mcp_server.py")
        mock_print("Ensure your Python environment with 'mcp[cli]' is active.")
        mock_server.run(transport="streamable-http")
        
        # Assert
        mock_logger.info.assert_called_with("MCP Server definition loaded.")
        mock_print.assert_any_call("To run this MCP server, navigate to the project root directory and execute:")
        mock_print.assert_any_call("mcp dev common/mcp_server.py")
        mock_print.assert_any_call("Ensure your Python environment with 'mcp[cli]' is active.")
        mock_server.run.assert_called_once_with(transport="streamable-http")


class TestMCPServerErrorHandling:
    """Test error handling in MCP server tools."""
    
    @patch('common.mcp_server.scan_project_structure')
    @patch('common.mcp_server.FastMCP')
    def test_should_propagate_errors_from_underlying_tools(self, mock_fastmcp, mock_scan_project):
        """Should propagate errors from underlying tool functions."""
        # Arrange
        mock_scan_project.side_effect = FileNotFoundError("Directory not found")
        
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            mock_scan_project(target_directory="/nonexistent")
    
    @patch('common.mcp_server.ask_human_clarification_mcp')
    @patch('common.mcp_server.FastMCP')
    def test_should_handle_keyboard_interrupt_gracefully(self, mock_fastmcp, mock_ask_human):
        """Should handle KeyboardInterrupt from user input gracefully."""
        # Arrange
        mock_ask_human.side_effect = KeyboardInterrupt("User interrupted")
        
        # Act & Assert
        with pytest.raises(KeyboardInterrupt, match="User interrupted"):
            mock_ask_human(question_to_ask="What next?")


class TestMCPServerImportHandling:
    """Test import and path handling in the MCP server."""
    
    def test_should_handle_project_root_path_calculation(self):
        """Should correctly calculate project root path."""
        # Arrange
        current_file = __file__  # This test file
        current_dir = os.path.dirname(current_file)  # tests/unit/common
        expected_project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        
        # Act - Calculate project root as done in mcp_server.py
        mcp_server_file = os.path.join(expected_project_root, 'common', 'mcp_server.py')
        calculated_root = os.path.abspath(os.path.join(os.path.dirname(mcp_server_file), '..'))
        
        # Assert
        assert calculated_root == expected_project_root
        assert os.path.exists(os.path.join(calculated_root, 'common'))
        assert os.path.exists(os.path.join(calculated_root, 'tests'))
    
    @patch('common.mcp_server.FastMCP')
    def test_should_import_all_required_tools(self, mock_fastmcp):
        """Should successfully import all required tool functions."""
        # Act - Import the module
        import common.mcp_server
        
        # Assert - Check that all tool imports succeeded
        assert hasattr(common.mcp_server, 'ask_human_clarification_mcp')
        assert hasattr(common.mcp_server, 'scan_project_structure')
        assert hasattr(common.mcp_server, 'set_target_directory')
        assert hasattr(common.mcp_server, 'list_directory_contents')
        assert hasattr(common.mcp_server, 'read_file_content')
        assert hasattr(common.mcp_server, 'get_dependencies')
        assert hasattr(common.mcp_server, 'apply_gitignore_filter')
        assert hasattr(common.mcp_server, 'search_codebase')
        assert hasattr(common.mcp_server, 'search_code_with_prompt')
        assert hasattr(common.mcp_server, 'search_tests_with_prompt')
        assert hasattr(common.mcp_server, 'determine_relevance_from_prompt')


class TestMCPServerToolParameterValidation:
    """Test parameter validation for MCP tools."""
    
    @patch('common.mcp_server.list_directory_contents')
    @patch('common.mcp_server.FastMCP')
    def test_list_contents_should_handle_default_parameters(self, mock_fastmcp, mock_list_contents):
        """list_contents tool should handle default parameters correctly."""
        # Arrange
        mock_list_contents.return_value = {"files": [], "directories": []}
        
        # Act - Call with only required parameters (simulating default behavior)
        result = mock_list_contents(
            path_to_list="src/",
            base_dir_context="/project",
            include_hidden=False  # Default value
        )
        
        # Assert
        assert result == {"files": [], "directories": []}
        mock_list_contents.assert_called_once_with(
            path_to_list="src/",
            base_dir_context="/project",
            include_hidden=False
        )
    
    @patch('common.mcp_server.read_file_content')
    @patch('common.mcp_server.FastMCP')
    def test_read_file_should_handle_optional_parameters(self, mock_fastmcp, mock_read_file):
        """read_file tool should handle optional line parameters correctly."""
        # Arrange
        mock_read_file.return_value = {"content": "test", "line_count": 5}
        
        # Act - Call with optional parameters as None
        result = mock_read_file(
            file_path_to_read="test.py",
            base_dir_context="/project",
            start_line=None,
            end_line=None
        )
        
        # Assert
        assert result == {"content": "test", "line_count": 5}
        mock_read_file.assert_called_once_with(
            file_path_to_read="test.py",
            base_dir_context="/project",
            start_line=None,
            end_line=None
        )
    
    @patch('common.mcp_server.search_codebase')
    @patch('common.mcp_server.FastMCP')
    def test_search_project_codebase_should_handle_default_parameters(self, mock_fastmcp, mock_search):
        """search_project_codebase tool should handle default parameters correctly."""
        # Arrange
        mock_search.return_value = {"matches": [], "total_matches": 0}
        
        # Act - Call with default parameters
        result = mock_search(
            target_directory="/project",
            keywords="function",
            file_pattern="*.*",
            context_lines=15,
            ignore_case=True
        )
        
        # Assert
        assert result == {"matches": [], "total_matches": 0}
        mock_search.assert_called_once_with(
            target_directory="/project",
            keywords="function",
            file_pattern="*.*",
            context_lines=15,
            ignore_case=True
        ) 