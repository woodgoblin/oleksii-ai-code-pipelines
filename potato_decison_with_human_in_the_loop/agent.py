"""Agent definitions for the Potato Decision Loop with Human-in-the-Loop.

This agent demonstrates a simple decision loop that requires human clarification
to proceed. The agent asks the user to include 'potato' in their response to continue.
"""

from typing import Optional

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import FunctionTool, ToolContext

from common.logging_setup import logger

# Import from common modules
from common.rate_limiting import RateLimiter, create_rate_limit_callbacks
from common.retry_runner import create_enhanced_runner

# Define state keys
STATE_USER_PROMPT = "user_prompt"
STATE_TEST_VARIABLE = "test_variable"
STATE_CLARIFICATION = "clarification"
STATE_NEEDS_CLARIFICATION = "needs_clarification"
STATE_FINAL_SUMMARY = "final_summary"

# Use a modern Gemini model
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

# Create rate limiter and callbacks
rate_limiter = RateLimiter(logger_instance=logger)
pre_model_rate_limit, handle_rate_limit_and_server_errors = create_rate_limit_callbacks(
    rate_limiter_instance=rate_limiter, logger_instance=logger
)


# Factory function for creating rate-limited agents
def create_rate_limited_agent(
    name, model, instruction, tools=None, output_key=None, sub_agents=None
):
    """Factory function to create LlmAgents with rate limiting."""
    return LlmAgent(
        name=name,
        model=model,
        instruction=instruction,
        tools=tools or [],
        output_key=output_key,
        sub_agents=sub_agents or [],
        before_model_callback=pre_model_rate_limit,
        after_model_callback=handle_rate_limit_and_server_errors,
    )


# --- Tools ---


def set_state_tool(key: str, value: str, tool_context: Optional[ToolContext] = None) -> dict:
    """Tool for setting state values."""
    if tool_context and hasattr(tool_context, "state"):
        tool_context.state[key] = value
        logger.info(f"Potato decision state updated: {key}")
        return {"status": "success", "message": f"Stored value in state key '{key}'", "key": key}

    logger.error("No tool context available for state setting")
    return {"status": "error", "message": "No tool context available"}


def get_state_tool(key: str, tool_context: Optional[ToolContext] = None) -> dict:
    """Tool for getting state values."""
    if tool_context and hasattr(tool_context, "state"):
        value = tool_context.state.get(key)
        if value is not None:
            return {"status": "success", "value": str(value), "key": key}
        return {"status": "error", "message": f"Key '{key}' not found in state"}

    return {"status": "error", "message": "No tool context available"}


def check_for_potato(tool_context: Optional[ToolContext] = None) -> dict:
    """Check if 'potato' is in the user prompt or any stored clarification."""
    if not tool_context or not hasattr(tool_context, "state"):
        return {"error": "No tool context available"}

    user_prompt = tool_context.state.get(STATE_USER_PROMPT, "").lower()
    clarifications_state = tool_context.state.get(STATE_CLARIFICATION, None)

    # Check prompt first
    has_potato_in_prompt = "potato" in user_prompt

    # Check clarifications (handling list or string)
    has_potato_in_clarifications = False
    if isinstance(clarifications_state, list):
        has_potato_in_clarifications = any(
            "potato" in str(item).lower() for item in clarifications_state
        )
    elif isinstance(clarifications_state, str):
        has_potato_in_clarifications = "potato" in clarifications_state.lower()

    # Combine checks
    has_potato = has_potato_in_prompt or has_potato_in_clarifications

    # Set the needs_clarification state
    tool_context.state[STATE_NEEDS_CLARIFICATION] = not has_potato

    return {"has_potato": has_potato, "needs_clarification": not has_potato}


def clarify_questions_tool_func(tool_context: Optional[ToolContext] = None) -> dict:
    """Get clarification from the user via console input."""
    print("--- CONSOLE INPUT REQUIRED ---")
    prompt_message = "Could you please include the word 'potato' in your clarification? This is required to proceed: "
    human_reply = input(prompt_message)
    print("--- CONSOLE INPUT RECEIVED ---")
    return {"reply": human_reply}


# Set the function name for proper tool registration
clarify_questions_tool_func.__name__ = "clarify_questions_tool"

# Create the FunctionTool
clarify_questions_tool = FunctionTool(func=clarify_questions_tool_func)


def redirect_and_exit(tool_context: ToolContext) -> dict:
    """Stop the LoopAgent and transfer control to the specified external agent."""
    tool_context.actions.escalate = True
    tool_context.actions.transfer_to_agent = "FinalizerAgent"
    return {}


# --- Agents ---

# Initial Agent - sets test_variable from user prompt
initial_agent = create_rate_limited_agent(
    name="InitialAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the Initial Agent. Your task is to:
    1. Extract the user prompt from '{STATE_USER_PROMPT}' in the state
    2. Store it in '{STATE_TEST_VARIABLE}' using the set_state tool
    3. Call the check_for_potato tool to see if the prompt contains 'potato'
    
    If 'potato' is found, indicate that no clarification is needed.
    If 'potato' is not found, indicate that clarification will be needed.
    """,
    tools=[FunctionTool(func=set_state_tool), FunctionTool(func=check_for_potato)],
    output_key=STATE_TEST_VARIABLE,
)

# Clarification Agent - asks for clarification if needed
clarification_agent = create_rate_limited_agent(
    name="ClarificationAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the Clarification Agent. Your task is to:
    1. Check the state key '{STATE_NEEDS_CLARIFICATION}' 
    2. If it's True, ask the user for clarification using the clarify_questions_tool
    3. Store the clarification in '{STATE_CLARIFICATION}' using set_state
    4. Call check_for_potato again to see if the clarification contains 'potato'
    
    Keep asking for clarification until 'potato' is found in the user's response.
    """,
    tools=[
        clarify_questions_tool,
        FunctionTool(func=set_state_tool),
        FunctionTool(func=check_for_potato),
    ],
)

# Decision Agent - makes the final decision
decision_agent = create_rate_limited_agent(
    name="DecisionAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the Decision Agent. Your task is to:
    1. Check if '{STATE_NEEDS_CLARIFICATION}' is False (meaning 'potato' was found)
    2. If so, congratulate the user and end the loop by calling redirect_and_exit
    3. If not, allow the loop to continue
    
    Only call redirect_and_exit when the clarification process is complete.
    """,
    tools=[FunctionTool(func=get_state_tool), FunctionTool(func=redirect_and_exit)],
)

# Finalizer Agent - provides the final response
finalizer_agent = create_rate_limited_agent(
    name="FinalizerAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are the Finalizer Agent. You are called when the potato decision loop has completed successfully.
    
    Your task is to:
    1. Get the final state using get_state tools
    2. Provide a summary of what happened during the process
    3. Congratulate the user on successfully including 'potato' in their input
    
    Be friendly and summarize the interaction.
    """,
    tools=[FunctionTool(func=get_state_tool)],
)

# Create the loop agent that will repeatedly run until 'potato' is found
potato_loop = LoopAgent(
    name="PotatoLoop",
    sub_agents=[initial_agent, clarification_agent, decision_agent],
    max_iterations=5,  # Prevent infinite loops
)

# Main sequential agent that runs the loop then the finalizer
root_agent = SequentialAgent(name="PotatoDecisionAgent", sub_agents=[potato_loop, finalizer_agent])


def create_enhanced_potato_runner(session_service):
    """Create an enhanced runner with retry logic for the potato decision agent.

    This wraps the entire agent execution with retry logic that can catch
    Google AI ClientError exceptions and retry them with proper delays.
    """
    return create_enhanced_runner(
        agent=root_agent,
        app_name="PotatoDecisionWithRetry",
        session_service=session_service,
        max_retries=3,
        base_delay=2.0,
        logger_instance=logger,
    )
