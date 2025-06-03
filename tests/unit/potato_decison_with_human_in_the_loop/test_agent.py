"""Tests for potato_decison_with_human_in_the_loop.agent module.

This module tests the agent functionality that implements a human-in-the-loop
decision process requiring 'potato' to be included in user responses.
"""

import unittest.mock as mock
from unittest.mock import MagicMock, Mock

import pytest

try:
    from google.adk.sessions import InMemorySessionService
except ImportError:
    InMemorySessionService = None


class MockSession:
    """Simple mock session for testing."""

    def __init__(self):
        self.state = {}


from potato_decison_with_human_in_the_loop.agent import (
    APP_NAME,
    GEMINI_MODEL,
    SESSION_ID,
    STATE_CLARIFICATION,
    STATE_FINAL_SUMMARY,
    STATE_NEEDS_CLARIFICATION,
    STATE_TEST_VARIABLE,
    STATE_USER_PROMPT,
    USER_ID,
    ClarifierGenerator,
    check_for_potato,
    create_rate_limited_agent,
    get_state,
    redirect_and_exit,
    set_session,
    set_state,
)


class TestSessionUtilityFunctions:
    """Test session-related utility functions."""

    def test_set_session_stores_new_session_globally(self, sample_session):
        """Test that set_session updates the global session."""
        # Act
        set_session(sample_session)

        # Assert
        import potato_decison_with_human_in_the_loop.agent as agent_module

        assert agent_module._session == sample_session

    def test_set_session_replaces_existing_session(self, sample_session):
        """Test that set_session can replace an existing session."""
        # Arrange
        first_session = MockSession()
        second_session = sample_session

        # Act
        set_session(first_session)
        set_session(second_session)

        # Assert
        import potato_decison_with_human_in_the_loop.agent as agent_module

        assert agent_module._session == second_session


class TestStateManagementFunctions:
    """Test state management utility functions."""

    def test_set_state_stores_value_successfully(self, sample_session):
        """Test that set_state stores a key-value pair."""
        # Arrange
        set_session(sample_session)

        # Act
        result = set_state("test_key", "test_value")

        # Assert
        assert result["status"] == "success"
        assert result["key"] == "test_key"
        assert sample_session.state["test_key"] == "test_value"

    def test_set_state_overwrites_existing_value(self, sample_session):
        """Test that set_state overwrites existing values."""
        # Arrange
        set_session(sample_session)
        sample_session.state["key"] = "old_value"

        # Act
        result = set_state("key", "new_value")

        # Assert
        assert result["status"] == "success"
        assert sample_session.state["key"] == "new_value"

    def test_set_state_handles_none_session(self):
        """Test that set_state handles None session gracefully."""
        # Arrange
        set_session(None)

        # Act
        result = set_state("test_key", "test_value")

        # Assert
        assert result["status"] == "success"

    def test_get_state_retrieves_existing_value(self, sample_session):
        """Test that get_state retrieves existing values."""
        # Arrange
        set_session(sample_session)
        sample_session.state["test_key"] = "test_value"

        # Act
        result = get_state("test_key")

        # Assert
        assert result["status"] == "success"
        assert result["value"] == "test_value"

    def test_get_state_returns_error_for_missing_key(self, sample_session):
        """Test that get_state returns error for missing keys."""
        # Arrange
        set_session(sample_session)

        # Act
        result = get_state("missing_key")

        # Assert
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_get_state_handles_none_session(self):
        """Test that get_state handles None session gracefully."""
        # Arrange
        set_session(None)

        # Act
        result = get_state("any_key")

        # Assert
        assert result["status"] == "error"


class TestPotatoDetectionLogic:
    """Test the potato detection functionality."""

    def test_finds_potato_in_user_prompt(self, sample_session):
        """Test detecting 'potato' in user prompt."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I really like potato chips"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False

    def test_finds_potato_case_insensitive(self, sample_session):
        """Test detecting 'potato' regardless of case."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I love POTATO salad"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True

    def test_detects_missing_potato(self, sample_session):
        """Test identifying when 'potato' is missing."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I like vegetables and fruits"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is False
        assert result["needs_clarification"] is True

    def test_finds_potato_in_clarification_string(self, sample_session):
        """Test detecting 'potato' in string clarification."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I like vegetables"
        sample_session.state[STATE_CLARIFICATION] = "Actually, I prefer potato dishes"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True

    def test_finds_potato_in_clarification_list(self, sample_session):
        """Test detecting 'potato' in list clarification."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I like vegetables"
        sample_session.state[STATE_CLARIFICATION] = ["carrots", "potato soup", "broccoli"]

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True

    def test_handles_empty_clarification_list(self, sample_session):
        """Test handling empty clarification list."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I like vegetables"
        sample_session.state[STATE_CLARIFICATION] = []

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is False

    def test_handles_mixed_clarification_types(self, sample_session):
        """Test handling non-string items in clarification."""
        # Arrange
        set_session(sample_session)
        sample_session.state[STATE_USER_PROMPT] = "I like vegetables"
        sample_session.state[STATE_CLARIFICATION] = [123, {"text": "potato is great"}, None]

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True

    def test_handles_missing_state_keys(self, sample_session):
        """Test handling missing state keys."""
        # Arrange
        set_session(sample_session)

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is False


class TestClarifierGenerator:
    """Test human input tool."""

    def test_has_correct_name(self):
        """Test tool name."""
        # Act
        clarifier = ClarifierGenerator()

        # Assert
        assert clarifier.__name__ == "clarify_questions_tool"

    @mock.patch("builtins.input", return_value="Yes, potato!")
    def test_returns_user_input(self, mock_input):
        """Test returning user input."""
        # Arrange
        clarifier = ClarifierGenerator()

        # Act
        result = clarifier()

        # Assert
        assert result == {"reply": "Yes, potato!"}

    @mock.patch("builtins.input", return_value="")
    def test_handles_empty_input(self, mock_input):
        """Test handling empty input."""
        # Arrange
        clarifier = ClarifierGenerator()

        # Act
        result = clarifier()

        # Assert
        assert result == {"reply": ""}


class TestRedirectAndExit:
    """Test redirect function."""

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
    """Test agent creation."""

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


class TestModuleConstants:
    """Test module constants."""

    def test_state_constants(self):
        """Test state constants are correct."""
        # Assert
        assert STATE_USER_PROMPT == "user_prompt"
        assert STATE_CLARIFICATION == "clarification"
        assert STATE_NEEDS_CLARIFICATION == "needs_clarification"

    def test_app_constants(self):
        """Test app constants are correct."""
        # Assert
        assert APP_NAME == "test_poc_agent"
        assert USER_ID == "demo_user"
        assert GEMINI_MODEL == "gemini-2.5-flash-preview-04-17"


class TestModuleIntegration:
    """Test complete workflows."""

    def test_complete_workflow_with_potato_in_prompt(self, sample_session):
        """Test workflow when potato is found in prompt."""
        # Arrange
        set_session(sample_session)

        # Act
        set_state(STATE_USER_PROMPT, "I want potato dishes")
        result = check_for_potato()

        # Assert
        assert sample_session.state[STATE_USER_PROMPT] == "I want potato dishes"
        assert result["has_potato"] is True

    def test_complete_workflow_with_potato_in_clarification(self, sample_session):
        """Test workflow when potato is found in clarification."""
        # Arrange
        set_session(sample_session)

        # Act
        set_state(STATE_USER_PROMPT, "I like cooking")
        set_state(STATE_CLARIFICATION, "Especially potato recipes")
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True

    def test_state_persistence(self, sample_session):
        """Test state persists across operations."""
        # Arrange
        set_session(sample_session)

        # Act
        set_state("key1", "value1")
        set_state("key2", "value2")

        # Assert
        assert get_state("key1")["value"] == "value1"
        assert get_state("key2")["value"] == "value2"
