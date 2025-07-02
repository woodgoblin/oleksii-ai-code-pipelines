#!/usr/bin/env python3
"""
ADK Web with Google AI Client Patch for 429 Retry.

This version patches the Google AI client directly to add retry logic
where ClientError exceptions actually occur, not at the HTTP layer.
"""

import asyncio
import logging
import random
import re
import time
from functools import wraps
from typing import Any, Callable, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("adk_web_client_patch")


def extract_retry_delay_from_error(error_details: dict) -> Optional[float]:
    """Extract retry delay from Google AI error details."""
    
    # Look for retryDelay in error details
    if isinstance(error_details, dict):
        details = error_details.get('error', {}).get('details', [])
        for detail in details:
            if detail.get('@type') == 'type.googleapis.com/google.rpc.RetryInfo':
                retry_delay = detail.get('retryDelay', '')
                if retry_delay.endswith('s'):
                    try:
                        return float(retry_delay[:-1])
                    except ValueError:
                        pass
    
    # Fallback patterns
    error_str = str(error_details)
    patterns = [
        r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"',
        r'retryDelay:\s*(\d+(?:\.\d+)?)',
        r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_str)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    
    return None


def google_ai_retry_decorator(max_retries: int = 30, base_delay: float = 2.0):
    """Decorator to add retry logic to Google AI client methods."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"🤖 Google AI call attempt {attempt + 1}/{max_retries + 1}: {func.__name__}")
                    result = await func(*args, **kwargs)
                    logger.info(f"✅ Google AI call succeeded: {func.__name__}")
                    return result
                    
                except Exception as e:
                    error_str = str(e)
                    
                    # Check if it's a 429 error
                    if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                        if attempt >= max_retries:
                            logger.error(f"💀 Max retries ({max_retries}) exceeded for {func.__name__}")
                            raise
                        
                        # Extract retry delay from error
                        retry_delay = None
                        if len(e.args) > 1:
                            retry_delay = extract_retry_delay_from_error(e.args[1])
                        if not retry_delay:
                            # Try extracting from the full error string
                            error_str = str(e)
                            match = re.search(r"'retryDelay':\s*'(\d+)s'", error_str)
                            if match:
                                retry_delay = float(match.group(1))
                        
                        if retry_delay:
                            delay = retry_delay + 1.0  # Add 1-second buffer as requested
                            logger.warning(f"⏳ 429 Error: Waiting {delay}s (Google AI suggested {retry_delay}s + 1s buffer)")
                        else:
                            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"⏳ 429 Error: Waiting {delay:.1f}s (exponential backoff)")
                        
                        await asyncio.sleep(delay)
                        continue
                    
                    # Check if it's another retryable error (5xx)
                    elif any(code in error_str for code in ["500", "502", "503", "504"]):
                        if attempt >= max_retries:
                            logger.error(f"💀 Max retries ({max_retries}) exceeded for {func.__name__}")
                            raise
                        
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"⏳ Server Error: Waiting {delay:.1f}s before retry {attempt + 2}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Non-retryable error
                        logger.error(f"❌ Non-retryable error in {func.__name__}: {e}")
                        raise
            
            # Should never reach here
            raise RuntimeError(f"Unexpected error in retry logic for {func.__name__}")
        
        @wraps(func) 
        def sync_wrapper(*args, **kwargs):
            # For sync functions, convert to async temporarily
            import asyncio
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return async wrapper if the original function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def patch_google_ai_client():
    """Patch the Google AI client to add retry logic."""
    
    try:
        logger.info("🔧 Patching Google AI client for retry logic...")
        
        # Patch the async generate_content method
        from google.genai.models import AsyncModels
        
        if hasattr(AsyncModels, 'generate_content'):
            original_generate_content = AsyncModels.generate_content
            patched_generate_content = google_ai_retry_decorator(max_retries=30, base_delay=2.0)(original_generate_content)
            AsyncModels.generate_content = patched_generate_content
            logger.info("✅ Patched AsyncModels.generate_content")
        
        # Also patch the main API client request method
        try:
            from google.genai._api_client import AsyncAPIClient
            
            if hasattr(AsyncAPIClient, '_async_request_once'):
                original_async_request = AsyncAPIClient._async_request_once
                patched_async_request = google_ai_retry_decorator(max_retries=30, base_delay=2.0)(original_async_request)
                AsyncAPIClient._async_request_once = patched_async_request
                logger.info("✅ Patched AsyncAPIClient._async_request_once")
        except ImportError:
            logger.warning("⚠️  Could not patch AsyncAPIClient (not found)")
        
        logger.info("🎯 Google AI client patched successfully!")
        logger.info("✅ Features:")
        logger.info("   • 429 retry with Google AI retryDelay extraction")
        logger.info("   • 1-second buffer on retry delays")
        logger.info("   • Exponential backoff for 5xx errors")
        logger.info("   • 30 retry attempts maximum")
        
    except ImportError as e:
        logger.error(f"❌ Failed to patch Google AI client: {e}")
        logger.error("Make sure google-genai is installed")
    except Exception as e:
        logger.error(f"❌ Unexpected error during patching: {e}")


def create_patched_adk_web():
    """Create the real ADK Web with Google AI client patches."""
    
    try:
        # Apply the patches BEFORE importing ADK Web
        patch_google_ai_client()
        
        # Import the REAL ADK Web FastAPI app
        from google.adk.cli.fast_api import get_fast_api_app
        
        logger.info("🔧 Loading REAL ADK Web FastAPI application...")
        app = get_fast_api_app(agents_dir=".", web=True)
        logger.info("✅ REAL ADK Web app loaded with patched Google AI client!")
        
        return app
        
    except ImportError as e:
        logger.error(f"❌ Could not import REAL ADK Web: {e}")
        raise


def main():
    """Main entry point."""
    
    logger.info("🚀 Starting REAL ADK Web with Google AI Client Patches")
    logger.info("=" * 60)
    logger.info("✅ This patches the Google AI client DIRECTLY")
    logger.info("🌐 Web UI will work normally")
    logger.info("🔄 Google AI ClientError exceptions will be retried")
    logger.info("🎯 Catches 429 errors WHERE THEY ACTUALLY HAPPEN")
    logger.info("=" * 60)
    
    try:
        app = create_patched_adk_web()
        
        import uvicorn
        logger.info("🌐 Starting server on http://127.0.0.1:8000")
        logger.info("🛡️  Google AI client retry patches are ACTIVE")
        
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
        
    except KeyboardInterrupt:
        logger.info("🛑 Server shutdown requested")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    main() 