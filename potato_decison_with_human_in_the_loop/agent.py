"""Agent definitions for the Potato Decision Loop with Human-in-the-Loop.

This agent demonstrates a simple decision loop that requires human clarification
to proceed. The agent asks the user to include 'potato' in their response to continue.
"""

import re
import time

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.sessions import InMemorySessionService

# Import from common modules 
from common.rate_limiting import pre_model_rate_limit, handle_rate_limit
from common.logging_setup import logger

# Session setup
APP_NAME = "test_poc_agent"
USER_ID = "demo_user"
SESSION_ID = "demo_session"

# Create session service and session
session_service = InMemorySessionService()
_session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

# Define state keys
STATE_USER_PROMPT = "user_prompt"
STATE_TEST_VARIABLE = "test_variable"
STATE_CLARIFICATION = "clarification"
STATE_NEEDS_CLARIFICATION = "needs_clarification"
STATE_FINAL_SUMMARY = "final_summary"

# Use a modern Gemini model
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

# Global session manager for the demo
def set_session(session):
    """Set the global session for this agent module."""
    global _session
    _session = session

# Factory function for creating rate-limited agents
def create_rate_limited_agent(name, model, instruction, tools=None, output_key=None, sub_agents=None):
    """Factory function to create LlmAgents with rate limiting."""
    return LlmAgent(
        name=name,
        model=model,
        instruction=instruction,
        tools=tools or [],
        output_key=output_key,
        sub_agents=sub_agents or [],
        before_model_callback=pre_model_rate_limit,
        after_model_callback=handle_rate_limit
    )

# --- Tools ---

def set_state(key: str, value: str) -> dict:
    """Utility function for agents to set values in the session state."""
    global _session
    if _session:
        _session.state[key] = value
        logger.info(f"Set state: {key} = {value}")
    return {"status": "success", "message": f"Stored value in state key '{key}'", "key": key}

def get_state(key: str) -> dict:
    """Utility function for agents to get values from the session state."""
    global _session
    if _session and key in _session.state:
        value = _session.state[key]
        return {"status": "success", "value": value, "key": key}
    return {"status": "error", "message": f"Key '{key}' not found in state"}

def check_for_potato() -> dict:
    """Check if 'potato' is in the user prompt or any stored clarification."""
    global _session
    
    user_prompt = _session.state.get(STATE_USER_PROMPT, "").lower()
    clarifications_state = _session.state.get(STATE_CLARIFICATION, None)
    
    # Check prompt first
    has_potato_in_prompt = 'potato' in user_prompt
    
    # Check clarifications (handling list or string)
    has_potato_in_clarifications = False
    if isinstance(clarifications_state, list):
        has_potato_in_clarifications = any('potato' in str(item).lower() for item in clarifications_state)
    elif isinstance(clarifications_state, str):
        has_potato_in_clarifications = 'potato' in clarifications_state.lower()
        
    # Combine checks
    has_potato = has_potato_in_prompt or has_potato_in_clarifications
    
    # Set the needs_clarification state
    _session.state[STATE_NEEDS_CLARIFICATION] = not has_potato
    
    return {
        "has_potato": has_potato,
        "needs_clarification": not has_potato
    }

class ClarifierGenerator:
    """Synchronous function to get console input for clarification."""
    __name__ = "clarify_questions_tool"
    
    def __call__(self):
        print("--- CONSOLE INPUT REQUIRED ---")
        prompt_message = "Could you please include the word 'potato' in your clarification? This is required to proceed: "
        human_reply = input(prompt_message)
        print("--- CONSOLE INPUT RECEIVED ---")
        return {"reply": human_reply}

# Change to standard FunctionTool wrapping the console-input function
clarify_questions_tool = FunctionTool(func=ClarifierGenerator())

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
    tools=[
        FunctionTool(func=set_state),
        FunctionTool(func=check_for_potato)
    ],
    output_key=STATE_TEST_VARIABLE
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
        FunctionTool(func=set_state),
        FunctionTool(func=check_for_potato)
    ]
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
    tools=[
        FunctionTool(func=get_state),
        FunctionTool(func=redirect_and_exit)
    ]
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
    tools=[FunctionTool(func=get_state)]
)

# Create the loop agent that will repeatedly run until 'potato' is found
potato_loop = LoopAgent(
    name="PotatoLoop",
    sub_agents=[
        initial_agent,
        clarification_agent, 
        decision_agent
    ],
    max_iterations=5  # Prevent infinite loops
)

# Main sequential agent that runs the loop then the finalizer
root_agent = SequentialAgent(
    name="PotatoDecisionAgent",
    sub_agents=[
        potato_loop,
        finalizer_agent
    ]
)

