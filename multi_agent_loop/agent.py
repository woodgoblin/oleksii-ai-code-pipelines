import datetime
from zoneinfo import ZoneInfo
import time
from collections import deque
from google.adk.agents import Agent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.llm_agent import LlmAgent

class RateLimiter:
    """Rate limiter to control API call frequency.
    
    Limits the number of calls to a specified maximum per time window.
    
    Attributes:
        max_calls (int): Maximum number of calls allowed per time window.
        window_seconds (int): Time window in seconds for rate limiting.
        call_timestamps (deque): Queue of timestamps for recent calls.
    """
    
    def __init__(self, max_calls_per_minute=10):
        """Initialize the rate limiter.
        
        Args:
            max_calls_per_minute (int): Maximum calls allowed per minute.
        """
        self.max_calls = max_calls_per_minute
        self.window_seconds = 60  # 1 minute window
        self.call_timestamps = deque(maxlen=max_calls_per_minute)
    
    def wait_if_needed(self):
        """Check if rate limit would be exceeded and wait if necessary.
        
        This method blocks until it's safe to make another call without exceeding
        the configured rate limit.
        """
        current_time = time.time()
        
        # If we haven't reached max calls yet, proceed immediately
        if len(self.call_timestamps) < self.max_calls:
            self.call_timestamps.append(current_time)
            return
        
        # Check if oldest timestamp is outside our window
        oldest_timestamp = self.call_timestamps[0]
        time_elapsed = current_time - oldest_timestamp
        
        # If we've used all our calls for this window, wait until window slides
        if time_elapsed < self.window_seconds:
            wait_time = self.window_seconds - time_elapsed
            time.sleep(wait_time)
            # After waiting, current time has changed
            current_time = time.time()
        
        # Remove the oldest timestamp and add the new one
        self.call_timestamps.popleft()
        self.call_timestamps.append(current_time)

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (41 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """

    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (
                f"Sorry, I don't have timezone information for {city}."
            ),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = (
        f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    )
    return {"status": "success", "report": report}

APP_NAME = "doc_writing_app"
USER_ID = "dev_user_01"
SESSION_ID = "session_01"
GEMINI_MODEL = "gemini-2.0-flash"

# --- State Keys ---
STATE_INITIAL_TOPIC = "quantum physics"
STATE_CURRENT_DOC = "current_document"
STATE_CRITICISM = "criticism"

# Create rate limiter for LLM calls (10 calls per minute)
rate_limiter = RateLimiter(max_calls_per_minute=10)

# Wrap LlmAgent's generate method to enforce rate limiting
original_llm_agent_generate = LlmAgent.generate

def rate_limited_generate(self, *args, **kwargs):
    """Wrapper around LlmAgent's generate method to enforce rate limiting."""
    # Wait if needed before making the API call
    rate_limiter.wait_if_needed()
    # Call the original generate method
    return original_llm_agent_generate(self, *args, **kwargs)

# Patch the LlmAgent's generate method
LlmAgent.generate = rate_limited_generate

writer_agent = LlmAgent(
    name="WriterAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Creative Writer AI.
    Check the session state for '{STATE_CURRENT_DOC}'.
    If '{STATE_CURRENT_DOC}' does NOT exist or is empty, write a very short (1-2 sentence) story or document based on the topic in state key '{STATE_INITIAL_TOPIC}'.
    If '{STATE_CURRENT_DOC}' *already exists* and '{STATE_CRITICISM}', refine '{STATE_CURRENT_DOC}' according to the comments in '{STATE_CRITICISM}'."
    Output *only* the story or the exact pass-through message.
    """,
    description="Writes the initial document draft.",
    output_key=STATE_CURRENT_DOC # Saves output to state
)

# Critic Agent (LlmAgent)
critic_agent = LlmAgent(
    name="CriticAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Constructive Critic AI.
    Review the document provided in the session state key '{STATE_CURRENT_DOC}'.
    Provide 1-2 brief suggestions for improvement (e.g., "Make it more exciting", "Add more detail").
    Output *only* the critique.
    """,
    description="Reviews the current document draft.",
    output_key=STATE_CRITICISM # Saves critique to state
)


root_agent = LoopAgent(
    name="LoopAgent", sub_agents=[writer_agent, critic_agent], max_iterations=5
)