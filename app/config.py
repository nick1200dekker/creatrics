"""
Configuration management.
"""
import os
import json
import logging

logger = logging.getLogger('config')

# Configuration cache
_config_cache = {}

def get_config():
    """Get configuration from environment variables."""
    global _config_cache
    
    # Return cached config if available
    if _config_cache:
        return _config_cache
    
    # Get configuration from environment variables
    env_config = {
        "supabase_url": os.environ.get("SUPABASE_URL", ""),
        "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
        "supabase_service_key": os.environ.get("SUPABASE_SERVICE_KEY", ""),
        "supabase_jwt_secret": os.environ.get("SUPABASE_JWT_SECRET", ""),
        "firebase_storage_bucket": os.environ.get("FIREBASE_STORAGE_BUCKET", "")
    }
    
    # Check if we have necessary environment variables
    if env_config["supabase_url"] and env_config["supabase_anon_key"]:
        _config_cache = env_config
        return _config_cache
    
    # If missing critical variables, log error and return dummy values
    logger.error("Missing critical environment variables (SUPABASE_URL/SUPABASE_ANON_KEY)")
    return {
        "supabase_url": "FAILED-TO-LOAD",
        "supabase_anon_key": "FAILED-TO-LOAD",
    }