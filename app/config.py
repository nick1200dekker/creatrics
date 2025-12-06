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
        "firebase_storage_bucket": os.environ.get("FIREBASE_STORAGE_BUCKET", ""),
        "firebase_project_id": os.environ.get("FIREBASE_PROJECT_ID", ""),
        "firebase_api_key": os.environ.get("FIREBASE_API_KEY", ""),
        "firebase_auth_domain": os.environ.get("FIREBASE_AUTH_DOMAIN", "")
    }
    
    _config_cache = env_config
    return _config_cache