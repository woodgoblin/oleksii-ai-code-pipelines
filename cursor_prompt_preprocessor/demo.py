#!/usr/bin/env python
"""Simple resilient demo that directly implements rate limiting for ADK."""

import asyncio
import os
import sys
import logging
import argparse
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cursor_prompt_preprocessor")

# Load environment variables from .env file
load_dotenv()

# Configure Google AI API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please set it in .env file.")
genai.configure(api_key=api_key)

# Add the parent directory to the path for imports to work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the root agent from our package
from cursor_prompt_preprocessor import root_agent
from cursor_prompt_preprocessor.agent import set_target_directory, set_global_session

# Setup constants
APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "demo_user"
SESSION_ID = "demo_session"

# Create session service and session
session_service = InMemorySessionService()
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

# Set the global session for the agent module
set_global_session(session)

# Create runner with the root agent
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# Manual retry implementation for ADK calls
async def run_with_retry(prompt, max_retries=3, initial_delay=1, backoff_factor=2, max_delay=60):
    """Run the ADK agent with prompt and implement manual retry logic for rate limits."""
    from google.genai import types
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    
    delay = initial_delay
    retry_count = 0
    
    while True:
        try:
            events = []
            # Process the events
            async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                events.append(event)
                
                # Check if the event is a final response
                is_final = False
                try:
                    is_final = hasattr(event, 'is_final_response') and event.is_final_response()
                except AttributeError:
                    is_final = False
                
                # If not final, treat as an intermediate event
                if not is_final:
                    source = getattr(event, 'author', 'System')
                    if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                        if len(event.content.parts) > 0 and hasattr(event.content.parts[0], 'text'):
                            print(f"\n[{source}]: {event.content.parts[0].text}\n")
                
                # Handle final response
                if is_final:
                    if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                        if len(event.content.parts) > 0 and hasattr(event.content.parts[0], 'text'):
                            print(f"\n=== Final Context ===\n")
                            print(event.content.parts[0].text)
            
            # If we get here, it was successful
            return events
            
        except Exception as e:
            error_message = str(e)
            retry_count += 1
            
            # If it's a rate limit error and we haven't exceeded max retries
            if "429 RESOURCE_EXHAUSTED" in error_message and retry_count <= max_retries:
                # Extract retry delay if available
                import re
                delay_match = re.search(r"'retryDelay': '(\d+)s'", error_message)
                if delay_match:
                    wait_time = int(delay_match.group(1)) + 1
                else:
                    wait_time = min(delay, max_delay)
                    delay *= backoff_factor
                
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                await asyncio.sleep(wait_time)
            else:
                # If not a rate limit error or we've exhausted retries, re-raise
                logger.error(f"Error after {retry_count-1} retries: {error_message}")
                raise

async def set_directory_in_state(target_dir):
    """Set the target directory in the agent state."""
    from google.genai import types
    
    # Create a message to call the set_target_directory function
    message = f"Process the following directory: {target_dir}"
    content = types.Content(role='user', parts=[types.Part(text=message)])
    
    # This will just trigger the agent to store the directory
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        # We just need to run this to set up the state
        pass
    
    # Manually set the target directory in the session state
    session.state["target_directory"] = target_dir
    logger.info(f"Set target directory in state: {target_dir}")

async def simple_demo(target_dir=None):
    """Run a simple demonstration with manual retry logic.
    
    Args:
        target_dir: Optional target directory to analyze. If None, current directory is used.
    """
    print("=== Simple Resilient Demo ===")
    print("This demo implements manual retry logic for rate limits")
    
    # Set the target directory if provided
    if target_dir:
        print(f"\nUsing target directory: {target_dir}")
        await set_directory_in_state(target_dir)
    else:
        print("\nUsing current directory for analysis")
        await set_directory_in_state(os.getcwd())
    
    # Get user prompt
    prompt = input("\nEnter your coding prompt (or press Enter for a sample prompt): ")
    if not prompt:
        prompt = "Create a function to calculate the Fibonacci sequence using recursion"
        print(f"Using sample prompt: '{prompt}'")
    
    print("\nProcessing prompt... (this may take a minute)")
    print("Note: If rate limits are hit, the system will automatically retry")
    
    try:
        # Process the prompt with retry logic
        events = await run_with_retry(prompt)
        
        print("\n=== Demo Complete ===")
        print("The above represents how the context would be formed and passed to Cursor.")
        
        # Debug info - show state keys
        print("\n=== State Keys ===")
        for key in session.state.keys():
            print(f"- {key}")
        
        # Access state at the end
        final_context = session.state.get("final_context", "Context not found")
        if final_context != "Context not found":
            print("\n=== Final Context Object ===")
            print(f"The final context object has been stored in the session state.")
            print(f"Length: {len(str(final_context))} characters")
    
    except Exception as e:
        logger.error(f"Failed to complete demo: {str(e)}")
        print(f"\n=== ERROR ===\n{str(e)}")
        print("\nDebug information:")
        print(f"Session state keys: {list(session.state.keys())}")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Cursor Prompt Preprocessor Demo")
    parser.add_argument(
        "--dir", "-d", 
        dest="target_dir",
        help="Target directory to analyze (defaults to current directory)",
        default=None
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    asyncio.run(simple_demo(args.target_dir))