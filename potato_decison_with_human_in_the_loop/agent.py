import os
from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools import FunctionTool, LongRunningFunctionTool, ToolContext
from google.adk.sessions import InMemorySessionService
import logging
import time
import re
import threading
from collections import deque

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# --- Rate Limiter Implementation ---

class RateLimiter:
    """Rate limiter for API calls that enforces a maximum number of calls per minute.
    
    Thread-safe implementation using a sliding window approach.
    """
    def __init__(self, max_calls_per_minute=10):
        self.max_calls = max_calls_per_minute
        self.window_seconds = 60  # 1 minute
        self.call_history = deque(maxlen=max_calls_per_minute)
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        logger.info(f"Rate limiter initialized: {max_calls_per_minute} calls per minute")
    
    def wait_if_needed(self):
        """Blocks until a call can be made without exceeding the rate limit."""
        with self.lock:
            current_time = time.time()
            
            # If we haven't reached the max calls yet, allow immediately
            if len(self.call_history) < self.max_calls:
                self.call_history.append(current_time)
                return
            
            # Check if the oldest call is outside our window
            oldest_call_time = self.call_history[0]
            time_since_oldest = current_time - oldest_call_time
            
            # If we've used all our quota and need to wait
            if time_since_oldest < self.window_seconds:
                wait_time = self.window_seconds - time_since_oldest + 0.1  # Add a small buffer
                logger.info(f"Rate limit reached. Waiting for {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                # After waiting, current time has changed
                current_time = time.time()
            
            # Update our history
            self.call_history.popleft()
            self.call_history.append(current_time)

# Create a global rate limiter instance
rate_limiter = RateLimiter(max_calls_per_minute=10)

# Callback to handle 429 rate limit errors
def handle_rate_limit(callback_context, llm_response):
    """After-model callback to handle rate limit errors.
    
    Args:
        callback_context: The callback context
        llm_response: The LLM response
        
    Returns:
        Modified response if rate limit was hit, None otherwise
    """
    # Check if there's an error in the response
    error = getattr(llm_response, 'error', None)
    if error and "429" in str(error):
        logger.warning(f"Rate limit error detected: {error}")
        
        # Extract retry delay if provided in the error message
        retry_delay = 5  # Default 5 seconds
        delay_match = re.search(r"'retryDelay': '(\d+)s'", str(error))
        if delay_match:
            retry_delay = int(delay_match.group(1))
            
        # Wait before retrying
        logger.info(f"Rate limit hit, waiting for {retry_delay} seconds before retry...")
        time.sleep(retry_delay + 1)  # Add 1 second buffer
        
        # Create a modified response indicating we'll retry
        from google.genai import types
        return types.Content(
            role="model",
            parts=[types.Part(text="Rate limit hit, retrying after delay...")]
        )
    
    # If no rate limit error, return None to use the original response
    return None

# Pre-model callback to enforce rate limiting before making requests
def pre_model_rate_limit(callback_context, llm_request):
    """Pre-model callback to enforce rate limiting before making API calls.
    
    Args:
        callback_context: The callback context
        llm_request: The LLM request parameters
        
    Returns:
        None to continue with the normal request, or a response to short-circuit
    """
    # Apply rate limiting before making the request
    try:
        logger.info("Pre-model rate limit check")
        rate_limiter.wait_if_needed()
        return None  # Continue with normal request
    except Exception as e:
        logger.error(f"Error in pre-model rate limit check: {e}")
        # If there's an error in rate limiting, create a fallback response
        from google.genai import types
        return types.Content(
            role="model", 
            parts=[types.Part(text="Error in rate limiting, please try again.")]
        )

# Factory function for creating rate-limited agents
def create_rate_limited_agent(name, model, instruction, tools=None, output_key=None, sub_agents=None):
    """Factory function to create LlmAgents with rate limiting.
    
    Ensures all agents have proper rate limiting applied.
    
    Args:
        name: Agent name
        model: Model name
        instruction: Agent instructions
        tools: List of tools
        output_key: Output state key
        sub_agents: List of sub-agents
    
    Returns:
        LlmAgent with rate limiting applied
    """
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
    """Utility function for agents to set values in the session state.
    
    Args:
        key: The state key to set
        value: The value to store
    
    Returns:
        dict: Confirmation of the operation
    """
    global _session
    if _session:
        _session.state[key] = value
        logger.info(f"Set state: {key} = {value}")
    return {"status": "success", "message": f"Stored value in state key '{key}'", "key": key}

def get_state(key: str) -> dict:
    """Utility function for agents to get values from the session state.
    
    Args:
        key: The state key to get
    
    Returns:
        dict: The value or an error message
    """
    global _session
    if _session and key in _session.state:
        value = _session.state[key]
        return {"status": "success", "value": value, "key": key}
    return {"status": "error", "message": f"Key '{key}' not found in state"}

def check_for_potato() -> dict:
    """Check if 'potato' is in the user prompt or any stored clarification.
    
    Handles STATE_CLARIFICATION potentially being a list of strings.
    
    Returns:
        dict: Result of the check
    """
    global _session
    
    user_prompt = _session.state.get(STATE_USER_PROMPT, "").lower()
    clarifications_state = _session.state.get(STATE_CLARIFICATION, None)
    
    # Check prompt first
    has_potato_in_prompt = 'potato' in user_prompt
    
    # Check clarifications (handling list or string)
    has_potato_in_clarifications = False
    if isinstance(clarifications_state, list):
        # Check if 'potato' is in any string within the list (case-insensitive)
        has_potato_in_clarifications = any('potato' in str(item).lower() for item in clarifications_state)
    elif isinstance(clarifications_state, str):
        # Fallback for single string clarification (old format or direct set)
        has_potato_in_clarifications = 'potato' in clarifications_state.lower()
        
    # Combine checks
    has_potato = has_potato_in_prompt or has_potato_in_clarifications
    
    # Set the needs_clarification state
    _session.state[STATE_NEEDS_CLARIFICATION] = not has_potato
    
    return {
        "has_potato": has_potato,
        "needs_clarification": not has_potato
    }

# Update ClarifierGenerator to use console input()
class ClarifierGenerator:
    """Synchronous function to get console input for clarification."""
    __name__ = "clarify_questions_tool" # Name remains the same for agent instructions
    
    def __call__(self):
        # Prompt the user directly in the console where the agent is running
        print("--- CONSOLE INPUT REQUIRED ---")
        prompt_message = "Could you please include the word 'potato' in your clarification? This is required to proceed: "
        human_reply = input(prompt_message)
        print("--- CONSOLE INPUT RECEIVED ---")
        
        # Return the received input
        return {"reply": human_reply}

# Change to standard FunctionTool wrapping the console-input function
clarify_questions_tool = FunctionTool(func=ClarifierGenerator())

def redirect_and_exit(tool_context: ToolContext) -> dict:
    """
    stops the LoopAgent 
    and transfers control to the specified external agent.
    """
    # Signal the LoopAgent to terminate immediately
    tool_context.actions.escalate = True  
    # Transfer execution to the outside agent named "FinalizerAgent"
    tool_context.actions.transfer_to_agent = "FinalizerAgent"
    # Return an empty dict (or any user-facing content, if desired)
    return {}

# --- Agents ---

# Initial Agent - sets test_variable from user prompt
initial_agent = create_rate_limited_agent(
    name="InitialAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are the initial agent in our workflow.
    
    Your task is to:
    1. Welcome the user
    2. Store their prompt in the session state with key 'user_prompt'
    3. Set the 'test_variable' state to the same value as the user's prompt
    4. Transfer control to the clarification loop
    
    Be friendly and professional in your interactions.
    """,
    tools=[FunctionTool(func=set_state)]
)

# Potato Check Agent - checks if 'potato' is present
potato_check_agent = create_rate_limited_agent(
    name="PotatoCheckAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are the Potato Check Agent.
    
    Your task is to:
    1. Check if the word 'potato' is present in the user's prompt or any stored clarifications using the check_for_potato tool.
    2. The tool will update the 'needs_clarification' state.
    3. **Report clearly:** Based on the tool's result, state whether clarification is needed (True/False) and that you are setting the corresponding state.
    
    Be concise and clear in your response.
    """,
    tools=[
        FunctionTool(func=check_for_potato),
        FunctionTool(func=get_state)
    ]
)

# Clarification Agent - asks user for clarification if needed
clarification_agent = create_rate_limited_agent(
    name="ClarificationAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are the Clarification Agent.

    Your task is based on the 'needs_clarification' state flag:
    1. Call get_state to check the boolean value of 'needs_clarification'.
    2. **Report clearly:** State the value you retrieved for 'needs_clarification' (True or False).
    3. If 'needs_clarification' is True:
        a. Announce that you will now ask for clarification via the console tool.
        b. Use the clarify_questions_tool to get console input.
        c. Call get_state to retrieve the current list of clarifications.
        d. Append the new 'reply' received from the tool to this list.
        e. Call set_state to store the updated list back into the 'clarification' state key.
    4. If 'needs_clarification' is False:
        a. Announce that you are redirecting to the FinalizerAgent.
        b. Call redirect_and_exit() to terminate the loop.
    """,
    tools=[
        FunctionTool(func=get_state),
        clarify_questions_tool, # This is now a FunctionTool instance
        FunctionTool(func=set_state),
        FunctionTool(func=redirect_and_exit)
    ]
)

# Finalizer Agent - summarizes everything
finalizer_agent = create_rate_limited_agent(
    name="FinalizerAgent",
    model=GEMINI_MODEL,
    instruction="""
    **Report clearly:** Announce that the Finalizer Agent is now running.
    
    You are the Finalizer Agent.
    
    Your task is to:
    1. Summarize the conversation, including the initial prompt and all collected clarifications.
    2. Use get_state to retrieve all relevant session variables (like 'user_prompt', 'test_variable', and the list of 'clarification' responses).
    3. Present this information in a clear, structured format, explicitly listing all items from the 'clarification' list if it exists.
    
    Be thorough but concise in your summary.
    """,
    tools=[FunctionTool(func=get_state)],
    output_key=STATE_FINAL_SUMMARY
)

# Clarification Loop - combines the potato check and clarification agents
clarification_loop = LoopAgent(
    name="ClarificationLoop",
    sub_agents=[
        potato_check_agent,
        clarification_agent
    ],
    max_iterations=3
)

# Main Sequential Agent - the complete workflow
root_agent = SequentialAgent(
    name="MainAgent",
    sub_agents=[
        initial_agent,
        clarification_loop,
        finalizer_agent
    ]
)

