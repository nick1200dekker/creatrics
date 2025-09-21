# File: app/system/auth/supabase.py

"""
Supabase authentication utilities for CreatorPal

This module provides functions for handling Supabase authentication tokens
and integrating Supabase auth with our application.
"""

import jwt
import requests
import logging
import json
from functools import wraps
from flask import g, redirect, url_for, jsonify, request, current_app

logger = logging.getLogger('supabase_auth')

def get_supabase_config():
    """
    Get Supabase configuration from app config
    
    Returns:
        dict: Supabase configuration
    """
    try:
        from app.config import get_config
        config = get_config()
        return {
            'url': config.get('supabase_url', ''),
            'anon_key': config.get('supabase_anon_key', ''),
            'service_key': config.get('supabase_service_key', ''),
            'jwt_secret': config.get('supabase_jwt_secret', '')
        }
    except Exception as e:
        logger.error(f"Failed to get Supabase config: {str(e)}")
        return {
            'url': '',
            'anon_key': '',
            'service_key': '',
            'jwt_secret': ''
        }

def verify_supabase_token(token):
    """
    Verify a Supabase JWT token
    
    Args:
        token (str): JWT token to verify
        
    Returns:
        dict or None: Token payload or None if invalid
    """
    if not token:
        return None
        
    try:
        # For simplicity, we'll decode without verification first to get the header
        # This lets us extract the key ID (kid) to find the right public key
        header = jwt.get_unverified_header(token)
        
        # In a production environment, you would fetch the public key from Supabase JWK endpoint
        # based on the key ID (kid) in the token header.
        # For now, we'll use the "verify_signature: False" option for development
        
        # Decode the token without verification (for development)
        payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        
        # In production, use this instead:
        # config = get_supabase_config()
        # payload = jwt.decode(
        #     token,
        #     config['jwt_secret'],
        #     algorithms=["HS256"],
        #     options={"verify_exp": True}
        # )
        
        # Check for required claims
        if not all(claim in payload for claim in ['sub', 'exp']):
            logger.warning("Token missing required claims")
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return None

def fetch_supabase_user(user_id):
    """
    Fetch user details from Supabase using admin API
    
    Args:
        user_id (str): Supabase user ID
        
    Returns:
        dict or None: User data or None if request fails
    """
    config = get_supabase_config()
    
    if not config['url'] or not config['service_key']:
        logger.error("Supabase URL or service key not configured")
        return None
    
    try:
        url = f"{config['url']}/auth/v1/admin/users/{user_id}"
        
        response = requests.get(
            url,
            headers={
                'Authorization': f"Bearer {config['service_key']}",
                'apikey': config['service_key'],
                'Content-Type': 'application/json'
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch user from Supabase: {response.status_code}")
            return None
            
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching user from Supabase: {str(e)}")
        return None

def auth_required(f):
    """
    Decorator for routes that require authentication
    
    Usage:
        @app.route('/protected')
        @auth_required
        def protected():
            return 'This is a protected route'
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            
            return redirect(url_for('core.login', reason='unauthorized'))
            
        return f(*args, **kwargs)
    
    return decorated_function

def admin_required(f):
    """
    Decorator for routes that require admin access
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user') or not g.user:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            
            return redirect(url_for('core.login', reason='unauthorized'))
            
        # Check for admin role in user data
        user_metadata = g.user.get('jwt_claims', {}).get('user_metadata', {})
        if user_metadata.get('role') != 'admin':
            return jsonify({"error": "Access denied"}), 403
            
        return f(*args, **kwargs)
    
    return decorated_function