# File: app/system/auth/firebase_auth.py

"""
Firebase authentication utilities for CreatorPal

This module provides functions for handling Firebase authentication tokens
and integrating Firebase Auth with our application.
"""

import logging
from functools import wraps
from flask import g, redirect, url_for, jsonify, request
from firebase_admin import auth

logger = logging.getLogger('firebase_auth')

def verify_firebase_token(token):
    """
    Verify a Firebase ID token
    
    Args:
        token (str): Firebase ID token to verify
        
    Returns:
        dict or None: Token payload or None if invalid
    """
    if not token:
        return None
        
    try:
        # Verify the ID token with Firebase Admin SDK
        # This automatically checks signature, expiration, and audience
        decoded_token = auth.verify_id_token(token)
        
        # Check for required claims
        if not all(claim in decoded_token for claim in ['uid', 'exp']):
            logger.warning("Token missing required claims")
            return None
        
        # Convert to format compatible with existing middleware
        # Map Firebase 'uid' to 'sub' for consistency
        payload = {
            'sub': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'exp': decoded_token.get('exp'),
            'user_metadata': {
                'username': decoded_token.get('name'),
                'full_name': decoded_token.get('name'),
                'display_name': decoded_token.get('name'),
                'email': decoded_token.get('email')
            }
        }
        
        return payload
        
    except auth.ExpiredIdTokenError:
        logger.warning("Token expired")
        return None
    except auth.RevokedIdTokenError:
        logger.warning("Token has been revoked")
        return None
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return None

def fetch_firebase_user(user_id):
    """
    Fetch user details from Firebase Auth
    
    Args:
        user_id (str): Firebase user ID (uid)
        
    Returns:
        dict or None: User data or None if request fails
    """
    try:
        user = auth.get_user(user_id)
        
        return {
            'uid': user.uid,
            'email': user.email,
            'email_verified': user.email_verified,
            'display_name': user.display_name,
            'photo_url': user.photo_url,
            'disabled': user.disabled,
            'metadata': {
                'creation_timestamp': user.user_metadata.creation_timestamp,
                'last_sign_in_timestamp': user.user_metadata.last_sign_in_timestamp
            },
            'provider_data': [
                {
                    'provider_id': provider.provider_id,
                    'uid': provider.uid,
                    'email': provider.email,
                    'display_name': provider.display_name
                }
                for provider in user.provider_data
            ]
        }
    except auth.UserNotFoundError:
        logger.error(f"User not found: {user_id}")
        return None
    except Exception as e:
        logger.error(f"Error fetching user from Firebase: {str(e)}")
        return None

def create_firebase_user(email, password, display_name=None):
    """
    Create a new user in Firebase Auth
    
    Args:
        email (str): User email
        password (str): User password
        display_name (str, optional): User display name
        
    Returns:
        dict or None: User data or None if creation fails
    """
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=False
        )
        
        logger.info(f"Successfully created user: {user.uid}")
        
        return {
            'uid': user.uid,
            'email': user.email,
            'display_name': user.display_name
        }
    except auth.EmailAlreadyExistsError:
        logger.error(f"Email already exists: {email}")
        return None
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return None

def update_firebase_user(user_id, **kwargs):
    """
    Update user details in Firebase Auth
    
    Args:
        user_id (str): Firebase user ID
        **kwargs: Fields to update (email, password, display_name, photo_url, etc.)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        auth.update_user(user_id, **kwargs)
        logger.info(f"Successfully updated user: {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        return False

def delete_firebase_user(user_id):
    """
    Delete a user from Firebase Auth
    
    Args:
        user_id (str): Firebase user ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        auth.delete_user(user_id)
        logger.info(f"Successfully deleted user: {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return False

def generate_password_reset_link(email):
    """
    Generate a password reset link for a user
    
    Args:
        email (str): User email
        
    Returns:
        str or None: Password reset link or None if failed
    """
    try:
        link = auth.generate_password_reset_link(email)
        logger.info(f"Generated password reset link for: {email}")
        return link
    except Exception as e:
        logger.error(f"Error generating password reset link: {str(e)}")
        return None

def generate_email_verification_link(email):
    """
    Generate an email verification link for a user
    
    Args:
        email (str): User email
        
    Returns:
        str or None: Email verification link or None if failed
    """
    try:
        link = auth.generate_email_verification_link(email)
        logger.info(f"Generated email verification link for: {email}")
        return link
    except Exception as e:
        logger.error(f"Error generating email verification link: {str(e)}")
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
            
        # Check for admin role in user data from Firestore
        # (Firebase Auth doesn't have roles, we store them in Firestore)
        from app.system.services.firebase_service import UserService
        user_data = UserService.get_user(g.user_id)
        
        if not user_data or user_data.get('subscription_plan', '').lower() not in ['admin', 'admin plan', 'administrator']:
            return jsonify({"error": "Access denied"}), 403
            
        return f(*args, **kwargs)
    
    return decorated_function
