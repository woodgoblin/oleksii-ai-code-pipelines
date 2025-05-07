"""Session management for Cursor Prompt Preprocessor."""

from google.adk.sessions import InMemorySessionService
from cursor_prompt_preprocessor.config import APP_NAME, USER_ID, SESSION_ID
from cursor_prompt_preprocessor.logging_setup import logger
from typing import Dict, Any, Optional

class SessionManager:
    """Manages the application session and state.
    
    Provides access to the current session and helper methods for working with session state.
    """
    
    def __init__(self):
        """Initialize the session manager with a new session."""
        self.session_service = InMemorySessionService()
        self.session = self.session_service.create_session(
            app_name=APP_NAME, 
            user_id=USER_ID, 
            session_id=SESSION_ID
        )
        logger.info(f"Session created: {APP_NAME}/{USER_ID}/{SESSION_ID}")
        
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a value from the session state.
        
        Args:
            key: The state key to retrieve
            default: Default value to return if key doesn't exist
            
        Returns:
            The value from the session state, or the default value
        """
        return self.session.state.get(key, default)
    
    def set_state(self, key: str, value: str) -> Dict[str, str]:
        """Set a value in the session state.
        
        Args:
            key: The state key to set
            value: The value to store
            
        Returns:
            dict: Result information about the operation
        """
        self.session.state[key] = value
        logger.info(f"State updated: {key}")
        return {"status": "success", "message": f"Stored value in state key '{key}'", "key": key}
    
    def has_state(self, key: str) -> bool:
        """Check if a key exists in the session state.
        
        Args:
            key: The state key to check
            
        Returns:
            bool: True if the key exists, False otherwise
        """
        return key in self.session.state
    
    def get_session(self):
        """Get the current session object.
        
        Returns:
            The current session object
        """
        return self.session

# Create a global session manager instance
session_manager = SessionManager() 