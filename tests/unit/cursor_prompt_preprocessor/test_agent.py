"""Tests for cursor_prompt_preprocessor.agent module.

This module tests the agent factory functions, tool wrappers, and agent
configuration used in the cursor prompt preprocessor system.
"""

import unittest.mock as mock
from unittest.mock import MagicMock, Mock, patch

import pytest

from cursor_prompt_preprocessor.agent import (
    AGENT_INSTRUCTION_PREAMBLE,
    apply_gitignore_filter_tool,
    clarifier_generator_callable,
    clarify_questions_tool,
    create_rate_limited_agent,
    determine_relevance_from_prompt_tool,
    get_dependencies_tool,
    list_directory_contents_tool,
    read_file_content_tool,
    scan_project_structure_tool,
    search_code_with_prompt_tool,
    search_tests_with_prompt_tool,
    set_state_tool,
    set_target_directory_tool,
)


class TestAgentSecurityConstraints:
    """Test that agents have proper security constraints in their instructions."""

    def test_given_agent_instruction_preamble_when_analyzing_constraints_then_all_critical_security_restrictions_are_present(
        self,
    ):
        """Given agent instruction preamble, when analyzing constraints, then it contains explicit restrictions preventing file creation, execution, and unauthorized actions."""
        # Arrange
        critical_constraints = [
            "CANNOT create",
            "CANNOT execute",
            "analytical assistant",
            "tools explicitly provided",
        ]

        # Act & Assert
        assert isinstance(AGENT_INSTRUCTION_PREAMBLE, str) and len(AGENT_INSTRUCTION_PREAMBLE) > 0
        for constraint in critical_constraints:
            assert (
                constraint in AGENT_INSTRUCTION_PREAMBLE
            ), f"Missing critical security constraint: {constraint}"


class TestAgentFactoryFunction:
    """Test the agent creation factory function behavior."""

    @patch("cursor_prompt_preprocessor.agent.LlmAgent")
    def test_given_minimal_agent_parameters_when_creating_agent_then_factory_produces_agent_with_security_preamble_and_rate_limiting(
        self, mock_llm_agent
    ):
        """Given minimal agent parameters, when creating agent, then factory produces agent with security preamble prepended and rate limiting callbacks attached."""
        # Arrange
        name = "TestAgent"
        model = "test-model"
        instruction = "Test instruction"

        # Act
        create_rate_limited_agent(name, model, instruction)

        # Assert
        mock_llm_agent.assert_called_once()
        call_kwargs = mock_llm_agent.call_args.kwargs

        # Verify basic parameters
        assert call_kwargs["name"] == name
        assert call_kwargs["model"] == model

        # Verify security preamble is prepended
        full_instruction = call_kwargs["instruction"]
        assert full_instruction.startswith(AGENT_INSTRUCTION_PREAMBLE)
        assert instruction in full_instruction

        # Verify rate limiting callbacks are attached
        assert call_kwargs["before_model_callback"] is not None
        assert call_kwargs["after_model_callback"] is not None

    @patch("cursor_prompt_preprocessor.agent.LlmAgent")
    def test_given_agent_with_tools_and_sub_agents_when_creating_agent_then_all_components_are_properly_configured(
        self, mock_llm_agent
    ):
        """Given agent with tools and sub-agents, when creating agent, then all components are properly configured and passed to LlmAgent constructor."""
        # Arrange
        name = "ComplexAgent"
        model = "complex-model"
        instruction = "Complex instruction"
        tools = [Mock(), Mock()]
        output_key = "test_output"
        sub_agents = [Mock(), Mock()]

        # Act
        create_rate_limited_agent(name, model, instruction, tools, output_key, sub_agents)

        # Assert
        call_kwargs = mock_llm_agent.call_args.kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["output_key"] == output_key
        assert call_kwargs["sub_agents"] == sub_agents

    @patch("cursor_prompt_preprocessor.agent.LlmAgent")
    def test_given_none_optional_parameters_when_creating_agent_then_factory_provides_safe_defaults(
        self, mock_llm_agent
    ):
        """Given None optional parameters, when creating agent, then factory provides safe defaults (empty lists for tools/sub_agents)."""
        # Act
        create_rate_limited_agent("Agent", "model", "instruction", None, None, None)

        # Assert
        call_kwargs = mock_llm_agent.call_args.kwargs
        assert call_kwargs["tools"] == []
        assert call_kwargs["output_key"] is None
        assert call_kwargs["sub_agents"] == []


class TestToolWrapperIntegration:
    """Test that tool wrappers are properly integrated with underlying functions."""

    def test_given_project_structure_tool_when_accessing_function_reference_then_it_points_to_correct_underlying_function(
        self,
    ):
        """Given project structure tool, when accessing function reference, then it points to scan_project_structure function."""
        # Arrange & Act & Assert
        assert scan_project_structure_tool is not None
        assert hasattr(scan_project_structure_tool, "func")
        assert callable(scan_project_structure_tool.func)
        # Verify it's the correct function by checking the name
        assert scan_project_structure_tool.func.__name__ == "scan_project_structure"


class TestClarifierGeneratorIntegration:
    """Test the clarifier generator tool integration and behavior."""

    def test_given_clarifier_callable_when_checking_tool_name_then_it_has_correct_adk_compatible_name(
        self,
    ):
        """Given clarifier callable, when checking tool name, then it has correct ADK-compatible name for tool registration."""
        # Act & Assert
        assert clarifier_generator_callable.__name__ == "clarify_questions_tool"

    @patch("cursor_prompt_preprocessor.agent.ClarifierGenerator")
    def test_given_clarifier_generator_when_calling_tool_then_it_instantiates_generator_and_returns_response(
        self, mock_clarifier_class
    ):
        """Given clarifier generator, when calling tool, then it instantiates ClarifierGenerator, calls it, and returns the response."""
        # Arrange
        expected_response = {"reply": "test clarification response"}
        mock_instance = Mock()
        mock_call_method = Mock(return_value=expected_response)
        mock_instance.__call__ = mock_call_method
        mock_clarifier_class.return_value = mock_instance

        # Act
        result = clarifier_generator_callable()

        # Assert
        mock_clarifier_class.assert_called_once()
        mock_call_method.assert_called_once()
        assert result == expected_response

    def test_given_clarify_questions_tool_when_checking_function_reference_then_it_points_to_clarifier_callable(
        self,
    ):
        """Given clarify questions tool, when checking function reference, then it points to clarifier_generator_callable."""
        # Act & Assert
        assert clarify_questions_tool is not None
        assert hasattr(clarify_questions_tool, "func")
        assert clarify_questions_tool.func == clarifier_generator_callable
