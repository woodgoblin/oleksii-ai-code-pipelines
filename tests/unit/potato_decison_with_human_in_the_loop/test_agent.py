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

    @pytest.mark.asyncio
    async def test_set_session_stores_new_session_globally(self, sample_session):
        """Test that set_session correctly updates the global session reference."""
        # Arrange
        new_session = sample_session

        # Act
        set_session(new_session)

        # Assert
        import potato_decison_with_human_in_the_loop.agent as agent_module

        assert agent_module._session == new_session

    @pytest.mark.asyncio
    async def test_set_session_replaces_existing_session(self, sample_session):
        """Test that set_session can replace an existing global session."""
        # Arrange
        if InMemorySessionService:
            session_service = InMemorySessionService()
            first_session = await session_service.create_session(
                app_name="test_app", user_id="test_user", session_id="test_session_1"
            )
        else:

            class MockSession:
                def __init__(self):
                    self.state = {}

            first_session = MockSession()

        second_session = sample_session

        # Act
        set_session(first_session)
        set_session(second_session)

        # Assert
        import potato_decison_with_human_in_the_loop.agent as agent_module

        assert agent_module._session == second_session
        assert agent_module._session != first_session


class TestStateManagementFunctions:
    """Test state management utility functions."""

    @pytest.mark.asyncio
    async def test_set_state_stores_value_in_session_successfully(self, sample_session):
        """Test that set_state correctly stores a key-value pair in session state."""
        # Arrange
        session = sample_session
        set_session(session)
        test_key = "test_key"
        test_value = "test_value"

        # Act
        result = set_state(test_key, test_value)

        # Assert
        assert result["status"] == "success"
        assert result["key"] == test_key
        assert result["message"] == f"Stored value in state key '{test_key}'"
        assert session.state[test_key] == test_value

    @pytest.mark.asyncio
    async def test_set_state_overwrites_existing_value(self, sample_session):
        """Test that set_state overwrites an existing value for the same key."""
        # Arrange
        session = sample_session
        set_session(session)
        test_key = "existing_key"
        original_value = "original_value"
        new_value = "new_value"
        session.state[test_key] = original_value

        # Act
        result = set_state(test_key, new_value)

        # Assert
        assert result["status"] == "success"
        assert session.state[test_key] == new_value
        assert session.state[test_key] != original_value

    def test_set_state_handles_none_session_gracefully(self):
        """Test that set_state handles None session without crashing."""
        # Arrange
        set_session(None)

        # Act
        result = set_state("test_key", "test_value")

        # Assert
        assert result["status"] == "success"
        assert result["key"] == "test_key"

    @pytest.mark.asyncio
    async def test_get_state_retrieves_existing_value_successfully(self, sample_session):
        """Test that get_state correctly retrieves an existing value from session state."""
        # Arrange
        session = sample_session
        set_session(session)
        test_key = "existing_key"
        test_value = "existing_value"
        session.state[test_key] = test_value

        # Act
        result = get_state(test_key)

        # Assert
        assert result["status"] == "success"
        assert result["value"] == test_value
        assert result["key"] == test_key

    @pytest.mark.asyncio
    async def test_get_state_returns_error_for_missing_key(self, sample_session):
        """Test that get_state returns error status for non-existent key."""
        # Arrange
        session = sample_session
        set_session(session)
        missing_key = "missing_key"

        # Act
        result = get_state(missing_key)

        # Assert
        assert result["status"] == "error"
        assert result["message"] == f"Key '{missing_key}' not found in state"
        assert "value" not in result

    def test_get_state_handles_none_session_gracefully(self):
        """Test that get_state handles None session without crashing."""
        # Arrange
        set_session(None)

        # Act
        result = get_state("any_key")

        # Assert
        assert result["status"] == "error"


class TestPotatoDetectionLogic:
    """Test the potato detection functionality."""

    @pytest.mark.asyncio
    async def test_check_for_potato_finds_potato_in_user_prompt(self, sample_session):
        """Test that check_for_potato detects 'potato' in user prompt."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I really like potato chips"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False
        assert session.state[STATE_NEEDS_CLARIFICATION] is False

    @pytest.mark.asyncio
    async def test_check_for_potato_finds_potato_case_insensitive(self, sample_session):
        """Test that check_for_potato detects 'potato' regardless of case."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I love POTATO salad"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_check_for_potato_detects_missing_potato_in_prompt(self, sample_session):
        """Test that check_for_potato correctly identifies when 'potato' is missing from prompt."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I like vegetables and fruits"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is False
        assert result["needs_clarification"] is True
        assert session.state[STATE_NEEDS_CLARIFICATION] is True

    @pytest.mark.asyncio
    async def test_check_for_potato_finds_potato_in_string_clarification(self, sample_session):
        """Test that check_for_potato detects 'potato' in string clarification."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I like vegetables"
        session.state[STATE_CLARIFICATION] = "Actually, I prefer potato dishes"

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_check_for_potato_finds_potato_in_list_clarification(self, sample_session):
        """Test that check_for_potato detects 'potato' in list of clarifications."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I like vegetables"
        session.state[STATE_CLARIFICATION] = [
            "I like carrots",
            "I also enjoy potato soup",
            "And some broccoli",
        ]

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_check_for_potato_handles_empty_clarification_list(self, sample_session):
        """Test that check_for_potato handles empty clarification list correctly."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I like vegetables"
        session.state[STATE_CLARIFICATION] = []

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is False
        assert result["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_check_for_potato_handles_non_string_clarification_items(self, sample_session):
        """Test that check_for_potato handles non-string items in clarification list."""
        # Arrange
        session = sample_session
        set_session(session)
        session.state[STATE_USER_PROMPT] = "I like vegetables"
        session.state[STATE_CLARIFICATION] = [123, {"text": "potato is great"}, None]

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is True
        assert result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_check_for_potato_handles_missing_state_keys(self, sample_session):
        """Test that check_for_potato handles missing state keys gracefully."""
        # Arrange
        session = sample_session
        set_session(session)
        # Don't set any state keys

        # Act
        result = check_for_potato()

        # Assert
        assert result["has_potato"] is False
        assert result["needs_clarification"] is True


class TestClarifierGenerator:
    """Test the ClarifierGenerator class for human input."""

    def test_clarifier_generator_has_correct_name_attribute(self):
        """Test that ClarifierGenerator has the expected __name__ attribute."""
        # Arrange & Act
        clarifier = ClarifierGenerator()

        # Assert
        assert clarifier.__name__ == "clarify_questions_tool"

    @mock.patch("builtins.input")
    @mock.patch("builtins.print")
    def test_clarifier_generator_call_returns_user_input(self, mock_print, mock_input):
        """Test that ClarifierGenerator.__call__ returns user input in expected format."""
        # Arrange
        mock_input.return_value = "Yes, I love potato chips!"
        clarifier = ClarifierGenerator()

        # Act
        result = clarifier()

        # Assert
        assert result == {"reply": "Yes, I love potato chips!"}
        mock_input.assert_called_once_with(
            "Could you please include the word 'potato' in your clarification? This is required to proceed: "
        )

    @mock.patch("builtins.input")
    @mock.patch("builtins.print")
    def test_clarifier_generator_prints_console_messages(self, mock_print, mock_input):
        """Test that ClarifierGenerator prints appropriate console messages."""
        # Arrange
        mock_input.return_value = "potato response"
        clarifier = ClarifierGenerator()

        # Act
        clarifier()

        # Assert
        mock_print.assert_any_call("--- CONSOLE INPUT REQUIRED ---")
        mock_print.assert_any_call("--- CONSOLE INPUT RECEIVED ---")
        assert mock_print.call_count == 2

    @mock.patch("builtins.input")
    def test_clarifier_generator_handles_empty_input(self, mock_input):
        """Test that ClarifierGenerator handles empty user input."""
        # Arrange
        mock_input.return_value = ""
        clarifier = ClarifierGenerator()

        # Act
        result = clarifier()

        # Assert
        assert result == {"reply": ""}


class TestRedirectAndExit:
    """Test the redirect_and_exit function."""

    def test_redirect_and_exit_sets_escalate_flag(self):
        """Test that redirect_and_exit sets the escalate flag in tool context."""
        # Arrange
        mock_tool_context = Mock()
        mock_tool_context.actions = Mock()

        # Act
        result = redirect_and_exit(mock_tool_context)

        # Assert
        assert mock_tool_context.actions.escalate is True
        assert result == {}

    def test_redirect_and_exit_sets_transfer_agent(self):
        """Test that redirect_and_exit sets the transfer_to_agent in tool context."""
        # Arrange
        mock_tool_context = Mock()
        mock_tool_context.actions = Mock()

        # Act
        redirect_and_exit(mock_tool_context)

        # Assert
        assert mock_tool_context.actions.transfer_to_agent == "FinalizerAgent"

    def test_redirect_and_exit_returns_empty_dict(self):
        """Test that redirect_and_exit always returns an empty dictionary."""
        # Arrange
        mock_tool_context = Mock()
        mock_tool_context.actions = Mock()

        # Act
        result = redirect_and_exit(mock_tool_context)

        # Assert
        assert result == {}
        assert isinstance(result, dict)


class TestCreateRateLimitedAgent:
    """Test the create_rate_limited_agent factory function."""

    @mock.patch("potato_decison_with_human_in_the_loop.agent.LlmAgent")
    def test_create_rate_limited_agent_with_minimal_parameters(self, mock_llm_agent):
        """Test creating rate limited agent with only required parameters."""
        # Arrange
        name = "TestAgent"
        model = "test-model"
        instruction = "Test instruction"

        # Act
        create_rate_limited_agent(name, model, instruction)

        # Assert
        mock_llm_agent.assert_called_once_with(
            name=name,
            model=model,
            instruction=instruction,
            tools=[],
            output_key=None,
            sub_agents=[],
            before_model_callback=mock.ANY,
            after_model_callback=mock.ANY,
        )

    @mock.patch("potato_decison_with_human_in_the_loop.agent.LlmAgent")
    def test_create_rate_limited_agent_with_all_parameters(self, mock_llm_agent):
        """Test creating rate limited agent with all optional parameters."""
        # Arrange
        name = "TestAgent"
        model = "test-model"
        instruction = "Test instruction"
        tools = [Mock(), Mock()]
        output_key = "test_output"
        sub_agents = [Mock()]

        # Act
        create_rate_limited_agent(name, model, instruction, tools, output_key, sub_agents)

        # Assert
        mock_llm_agent.assert_called_once_with(
            name=name,
            model=model,
            instruction=instruction,
            tools=tools,
            output_key=output_key,
            sub_agents=sub_agents,
            before_model_callback=mock.ANY,
            after_model_callback=mock.ANY,
        )

    @mock.patch("potato_decison_with_human_in_the_loop.agent.LlmAgent")
    def test_create_rate_limited_agent_includes_rate_limit_callbacks(self, mock_llm_agent):
        """Test that rate limit callbacks are included in agent creation."""
        # Arrange
        name = "TestAgent"
        model = "test-model"
        instruction = "Test instruction"

        # Act
        create_rate_limited_agent(name, model, instruction)

        # Assert
        call_args = mock_llm_agent.call_args
        assert call_args.kwargs["before_model_callback"] is not None
        assert call_args.kwargs["after_model_callback"] is not None


class TestModuleConstants:
    """Test that module constants are properly defined."""

    def test_state_constants_are_strings(self):
        """Test that all state constants are properly defined as strings."""
        # Act & Assert
        assert isinstance(STATE_USER_PROMPT, str)
        assert isinstance(STATE_TEST_VARIABLE, str)
        assert isinstance(STATE_CLARIFICATION, str)
        assert isinstance(STATE_NEEDS_CLARIFICATION, str)
        assert isinstance(STATE_FINAL_SUMMARY, str)

    def test_state_constants_have_expected_values(self):
        """Test that state constants have the expected values."""
        # Act & Assert
        assert STATE_USER_PROMPT == "user_prompt"
        assert STATE_TEST_VARIABLE == "test_variable"
        assert STATE_CLARIFICATION == "clarification"
        assert STATE_NEEDS_CLARIFICATION == "needs_clarification"
        assert STATE_FINAL_SUMMARY == "final_summary"

    def test_app_constants_are_strings(self):
        """Test that application constants are properly defined as strings."""
        # Act & Assert
        assert isinstance(APP_NAME, str)
        assert isinstance(USER_ID, str)
        assert isinstance(SESSION_ID, str)
        assert isinstance(GEMINI_MODEL, str)

    def test_app_constants_have_expected_values(self):
        """Test that application constants have the expected values."""
        # Act & Assert
        assert APP_NAME == "test_poc_agent"
        assert USER_ID == "demo_user"
        assert SESSION_ID == "demo_session"
        assert GEMINI_MODEL == "gemini-2.5-flash-preview-04-17"


class TestModuleIntegration:
    """Test integration scenarios involving multiple components."""

    @pytest.mark.asyncio
    async def test_complete_potato_detection_workflow_with_prompt(self, sample_session):
        """Test complete workflow when potato is found in initial prompt."""
        # Arrange
        session = sample_session
        set_session(session)
        user_input = "I would like to cook some potato dishes today"

        # Act
        set_state(STATE_USER_PROMPT, user_input)
        potato_result = check_for_potato()

        # Assert
        assert session.state[STATE_USER_PROMPT] == user_input
        assert potato_result["has_potato"] is True
        assert potato_result["needs_clarification"] is False
        assert session.state[STATE_NEEDS_CLARIFICATION] is False

    @pytest.mark.asyncio
    async def test_complete_potato_detection_workflow_with_clarification(self, sample_session):
        """Test complete workflow when potato is found in clarification."""
        # Arrange
        session = sample_session
        set_session(session)
        initial_prompt = "I like cooking vegetables"
        clarification = "Especially potato-based recipes"

        # Act
        set_state(STATE_USER_PROMPT, initial_prompt)
        set_state(STATE_CLARIFICATION, clarification)
        potato_result = check_for_potato()

        # Assert
        assert session.state[STATE_USER_PROMPT] == initial_prompt
        assert session.state[STATE_CLARIFICATION] == clarification
        assert potato_result["has_potato"] is True
        assert potato_result["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_state_management_persists_across_operations(self, sample_session):
        """Test that state changes persist across multiple operations."""
        # Arrange
        session = sample_session
        set_session(session)

        # Act
        set_state("key1", "value1")
        set_state("key2", "value2")
        result1 = get_state("key1")
        result2 = get_state("key2")

        # Assert
        assert result1["value"] == "value1"
        assert result2["value"] == "value2"
        assert session.state["key1"] == "value1"
        assert session.state["key2"] == "value2"
