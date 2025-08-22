"""Tests for potato_decison_with_human_in_the_loop.agent module.

This module tests the agent functionality that implements a human-in-the-loop
decision process requiring 'potato' to be included in user responses.
"""

# type: ignore

import unittest.mock as mock
from unittest.mock import MagicMock, Mock

import pytest

try:
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools import ToolContext
except ImportError:
    InMemorySessionService = None
    ToolContext = None

from potato_decison_with_human_in_the_loop.agent import (
    GEMINI_MODEL,
    STATE_CLARIFICATION,
    STATE_FINAL_SUMMARY,
    STATE_NEEDS_CLARIFICATION,
    STATE_TEST_VARIABLE,
    STATE_USER_PROMPT,
    check_for_potato,
    clarify_questions_tool_func,
    create_rate_limited_agent,
    get_state_tool,
    redirect_and_exit,
    set_state_tool,
)


class MockToolContext:
    """Mock tool context for testing."""

    def __init__(self):
        self.state = {}
        self.actions = Mock()


class TestStateConstants:
    """Test state constants."""

    def test_state_constants_exist(self):
        """Test that state constants are defined."""
        assert STATE_USER_PROMPT == "user_prompt"
        assert STATE_CLARIFICATION == "clarification"
        assert STATE_NEEDS_CLARIFICATION == "needs_clarification"
        assert STATE_TEST_VARIABLE == "test_variable"
        assert STATE_FINAL_SUMMARY == "final_summary"

    def test_gemini_model_constant(self):
        """Test that GEMINI_MODEL is defined."""
        assert GEMINI_MODEL == "gemini-2.5-flash-preview-04-17"


class TestSetStateTool:
    """Test the set_state_tool function."""

    def test_sets_state_with_context(self):
        """Test setting state with valid context."""
        # Arrange
        mock_context = MockToolContext()

        # Act
        result = set_state_tool("test_key", "test_value", mock_context)  # type: ignore

        # Assert
        assert result["status"] == "success"
        assert result["key"] == "test_key"
        assert mock_context.state["test_key"] == "test_value"

    def test_handles_no_context(self):
        """Test handling no tool context."""
        # Act
        result = set_state_tool("test_key", "test_value", None)

        # Assert
        assert result["status"] == "error"
        assert "No tool context available" in result["message"]


class TestGetStateTool:
    """Test the get_state_tool function."""

    def test_gets_existing_state(self):
        """Test getting existing state value."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state["test_key"] = "test_value"

        # Act
        result = get_state_tool("test_key", mock_context)

        # Assert
        assert result["status"] == "success"
        assert result["value"] == "test_value"

    def test_handles_missing_key(self):
        """Test handling missing state key."""
        # Arrange
        mock_context = MockToolContext()

        # Act
        result = get_state_tool("missing_key", mock_context)

        # Assert
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_handles_no_context(self):
        """Test handling no tool context."""
        # Act
        result = get_state_tool("test_key", None)

        # Assert
        assert result["status"] == "error"
        assert "No tool context available" in result["message"]


class TestCheckForPotato:
    """Test the check_for_potato function."""

    def test_finds_potato_in_user_prompt(self):
        """Test detecting 'potato' in user prompt."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I really like potato chips"

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False
        assert mock_context.state[STATE_NEEDS_CLARIFICATION] is False

    def test_finds_potato_case_insensitive(self):
        """Test detecting 'potato' regardless of case."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I love POTATO salad"

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is True

    def test_detects_missing_potato(self):
        """Test identifying when 'potato' is missing."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I like vegetables and fruits"

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is False
        assert result["needs_clarification"] is True
        assert mock_context.state[STATE_NEEDS_CLARIFICATION] is True

    def test_finds_potato_in_clarification_string(self):
        """Test detecting 'potato' in string clarification."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I like vegetables"
        mock_context.state[STATE_CLARIFICATION] = "Actually, I prefer potato dishes"

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is True

    def test_finds_potato_in_clarification_list(self):
        """Test detecting 'potato' in list clarification."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I like vegetables"
        mock_context.state[STATE_CLARIFICATION] = ["carrots", "potato soup", "broccoli"]

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is True

    def test_handles_empty_clarification_list(self):
        """Test handling empty clarification list."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I like vegetables"
        mock_context.state[STATE_CLARIFICATION] = []

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is False

    def test_handles_mixed_clarification_types(self):
        """Test handling non-string items in clarification."""
        # Arrange
        mock_context = MockToolContext()
        mock_context.state[STATE_USER_PROMPT] = "I like vegetables"
        mock_context.state[STATE_CLARIFICATION] = [123, {"text": "potato is great"}, None]

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is True

    def test_handles_missing_state_keys(self):
        """Test handling missing state keys."""
        # Arrange
        mock_context = MockToolContext()

        # Act
        result = check_for_potato(mock_context)

        # Assert
        assert result["has_potato"] is False

    def test_handles_no_context(self):
        """Test handling no tool context."""
        # Act
        result = check_for_potato(None)

        # Assert
        assert "error" in result
        assert "No tool context available" in result["error"]


class TestClarifyQuestionsTool:
    """Test the clarify_questions_tool_func function."""

    @mock.patch("builtins.input", return_value="Yes, potato!")
    def test_returns_user_input(self, mock_input):
        """Test returning user input."""
        # Act
        result = clarify_questions_tool_func()

        # Assert
        assert result == {"reply": "Yes, potato!"}

    @mock.patch("builtins.input", return_value="")
    def test_handles_empty_input(self, mock_input):
        """Test handling empty input."""
        # Act
        result = clarify_questions_tool_func()

        # Assert
        assert result == {"reply": ""}


class TestRedirectAndExit:
    """Test the redirect_and_exit function."""

    def test_sets_escalate_flag(self):
        """Test setting escalate flag."""
        # Arrange
        mock_context = Mock()
        mock_context.actions = Mock()

        # Act
        result = redirect_and_exit(mock_context)

        # Assert
        assert mock_context.actions.escalate is True
        assert result == {}

    def test_sets_transfer_agent(self):
        """Test setting transfer agent."""
        # Arrange
        mock_context = Mock()
        mock_context.actions = Mock()

        # Act
        redirect_and_exit(mock_context)

        # Assert
        assert mock_context.actions.transfer_to_agent == "FinalizerAgent"


class TestCreateRateLimitedAgent:
    """Test the create_rate_limited_agent function."""

    @mock.patch("potato_decison_with_human_in_the_loop.agent.LlmAgent")
    def test_creates_agent_with_minimal_params(self, mock_llm_agent):
        """Test creating agent with minimal parameters."""
        # Act
        create_rate_limited_agent("TestAgent", "test-model", "Test instruction")

        # Assert
        mock_llm_agent.assert_called_once()
        call_args = mock_llm_agent.call_args.kwargs
        assert call_args["name"] == "TestAgent"
        assert call_args["model"] == "test-model"
        assert call_args["before_model_callback"] is not None

    @mock.patch("potato_decison_with_human_in_the_loop.agent.LlmAgent")
    def test_creates_agent_with_all_params(self, mock_llm_agent):
        """Test creating agent with all parameters."""
        # Arrange
        tools = [Mock()]
        sub_agents = [Mock()]

        # Act
        create_rate_limited_agent("TestAgent", "model", "instruction", tools, "output", sub_agents)

        # Assert
        call_args = mock_llm_agent.call_args.kwargs
        assert call_args["tools"] == tools
        assert call_args["sub_agents"] == sub_agents
