#!/usr/bin/env python
"""Demo script for the Cursor Prompt Preprocessor."""

import asyncio
import os
import sys
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the path for imports to work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the root agent from our package
from cursor_prompt_preprocessor import root_agent

# Setup constants
APP_NAME = "cursor_prompt_preprocessor"
USER_ID = "demo_user"
SESSION_ID = "demo_session"

async def run_demo():
    """Run a demonstration of the cursor prompt preprocessor."""
    print("=== Cursor Prompt Preprocessor Demo ===")
    print("This demo shows how the system processes a coding prompt and forms context.")
    print("The system will analyze the project structure, dependencies, and relevant code.")
    
    # Create session and runner
    session_service = InMemorySessionService()
    session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    
    # Sample prompt (or get from user input)
    prompt = input("\nEnter your coding prompt (or press Enter for a sample prompt): ")
    if not prompt:
        prompt = "Create a function to calculate the Fibonacci sequence using recursion"
        print(f"Using sample prompt: '{prompt}'")
    
    print("\nProcessing prompt... (this may take a minute)")
    
    # Send the prompt to the agent
    content = types.Content(role='user', parts=[types.Part(text=prompt)])
    events = []
    
    try:
        # Collect events and process them
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
        print(f"\n=== ERROR ===\n{str(e)}")
        print("\nDebug information:")
        print(f"Event type: {type(event)}")
        print(f"Event attributes: {dir(event)}")


if __name__ == "__main__":
    asyncio.run(run_demo()) 