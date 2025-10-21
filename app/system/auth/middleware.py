# File: app/system/auth/middleware.py

"""
Authentication middleware for CreatorPal

This module provides middleware functions for centralized authentication
with HTTP-only cookies and simplified route protection.
"""

from flask import request, redirect, url_for, g, current_app, jsonify, make_response
from functools import wraps
import jwt
import logging
import os
from datetime import datetime, timedelta
from app.system.auth.supabase import verify_supabase_token
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger('auth_middleware')

# Default cookie settings
COOKIE_NAME = "auth_session"
COOKIE_PATH = "/"
COOKIE_DOMAIN = None  # Use None for same domain as server
COOKIE_SECURE = True  # HTTPS-only
COOKIE_HTTPONLY = True  # Not accessible from JavaScript
COOKIE_SAMESITE = "Lax"  # Prevents CSRF, allows links
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

def get_token_from_cookie():
    """
    Get JWT token from auth cookie
    
    Returns:
        str or None: The token or None if cookie not found
    """
    return request.cookies.get(COOKIE_NAME)

def get_token_from_header():
    """
    Get JWT token from Authorization header
    
    Returns:
        str or None: The token or None if header not found
    """
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None

def verify_token(token):
    """
    Verify JWT token authenticity and validity
    
    Args:
        token (str): JWT token to verify
        
    Returns:
        dict or None: Token payload or None if invalid
    """
    if not token:
        return None
        
    try:
        # Use Supabase token verification
        payload = verify_supabase_token(token)
        
        if not payload:
            logger.warning("Token verification failed")
            return None
            
        # Check if token is expired
        if 'exp' in payload:
            now = datetime.now().timestamp()
            if payload['exp'] < now:
                logger.warning("Token is expired")
                return None
                
        return payload
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return None

def set_auth_cookie(response, token, max_age=None):
    """
    Set HTTP-only cookie with auth token
    
    Args:
        response (Response): Flask response object
        token (str): JWT token to store in cookie
        max_age (int, optional): Cookie max age in seconds
        
    Returns:
        Response: Modified response with cookie
    """
    if max_age is None:
        max_age = COOKIE_MAX_AGE
        
    expires = datetime.now() + timedelta(seconds=max_age)
    
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        expires=expires,
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE
    )
    
    return response

def clear_auth_cookie(response):
    """
    Clear the auth cookie
    
    Args:
        response (Response): Flask response object
        
    Returns:
        Response: Modified response with deleted cookie
    """
    response.delete_cookie(
        COOKIE_NAME,
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN
    )
    
    return response

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
        # Get token from cookie first, then from header as fallback
        token = get_token_from_cookie() or get_token_from_header()
        
        if os.environ.get('FLASK_ENV') == 'development' and os.environ.get('BYPASS_AUTH') == 'True':
            logger.debug("Bypassing auth in development mode")
            g.user = {
                'id': 'dev_user_id',
                'data': {'email': 'dev@example.com', 'username': 'dev_user'},
                'jwt_claims': {'sub': 'dev_user_id'}
            }
            return f(*args, **kwargs)
        
        payload = verify_token(token)

        if not payload:
            # Log the auth failure with more detail
            logger.warning(f"Authentication failed on path: {request.path}. Token invalid or expired.")

            # API routes return JSON error
            if request.path.startswith('/api/') or '/api/' in request.path:
                return jsonify({"error": "Unauthorized", "reason": "invalid_session"}), 401

            # Create a redirect response to the login page
            response = make_response(redirect(url_for('core.login', reason='session_expired', _external=True)))

            # Clear any existing auth cookies to ensure clean state
            response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, domain=COOKIE_DOMAIN)

            # Set cache headers to prevent browser from caching the redirect
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

            return response

        # Check if g.user was already set by auth_middleware (before_request)
        # If so, don't overwrite it - the middleware has already loaded fresh data from Firebase
        if hasattr(g, 'user') and g.user and g.user.get('id') == payload.get('sub'):
            logger.debug(f"Auth decorator: g.user already set by middleware for {g.user_id}, skipping recreation")
            return f(*args, **kwargs)

        # Store user info in Flask global context (fallback if middleware didn't run)
        g.user_id = payload.get('sub')
        # Try multiple fields for username (Google OAuth uses full_name, email users use username)
        user_metadata = payload.get('user_metadata', {})
        username = (user_metadata.get('username') or
                    user_metadata.get('full_name') or
                    user_metadata.get('name') or
                    user_metadata.get('display_name'))

        g.user = {
            'id': payload.get('sub'),
            'data': {
                'email': payload.get('email'),
                'username': username,
                'subscription_plan': user_metadata.get('subscription_plan', 'Free Plan')
            },
            'jwt_claims': payload,
            'is_guest': False
        }

        logger.debug(f"Auth successful for user {g.user_id} on path: {request.path}")
        return f(*args, **kwargs)
        
    return decorated_function

def optional_auth(f):
    """
    Decorator for routes where authentication is optional
    
    Similar to auth_required but doesn't redirect if not authenticated
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_cookie() or get_token_from_header()
        
        if os.environ.get('FLASK_ENV') == 'development' and os.environ.get('BYPASS_AUTH') == 'True':
            logger.debug("Bypassing auth in development mode")
            g.user = {
                'id': 'dev_user_id',
                'data': {'email': 'dev@example.com', 'username': 'dev_user'},
                'jwt_claims': {'sub': 'dev_user_id'}
            }
            return f(*args, **kwargs)
        
        if token:
            payload = verify_token(token)
            
            if payload:
                g.user_id = payload.get('sub')
                # Try multiple fields for username (Google OAuth uses full_name, email users use username)
                user_metadata = payload.get('user_metadata', {})
                username = (user_metadata.get('username') or
                            user_metadata.get('full_name') or
                            user_metadata.get('name') or
                            user_metadata.get('display_name'))

                g.user = {
                    'id': payload.get('sub'),
                    'data': {
                        'email': payload.get('email'),
                        'username': username
                    },
                    'jwt_claims': payload,
                    'is_guest': False
                }
                logger.debug(f"Optional auth successful for user {g.user_id}")
            else:
                g.user = None
                g.user_id = None
        else:
            g.user = None
            g.user_id = None
            
        return f(*args, **kwargs)
    
    return decorated_function

def auth_middleware():
    """
    Global middleware for non-decorator based auth check
    
    Only used for global auth checks. Individual route protection
    should use the auth_required decorator instead.
    
    Returns:
        Response or None: Redirect response if auth fails, None to continue request
    """
    # Skip for webhook, callback, and cron endpoints
    if (request.path.startswith('/payment/webhook') or 
        request.path.startswith('/music/suno/callback') or
        request.path.startswith('/cron/')):
        logger.debug(f"Skipping auth for system endpoint: {request.path}")
        return None
        
    # Define public paths (no authentication required)
    public_paths = [
        '/auth/login',
        '/auth/register',
        '/auth/forgot-password',  # Allow access to forgot password page
        '/auth/reset-password',   # Allow access to reset password page
        '/auth/callback',
        '/auth/session',
        '/api/check-auth',
        '/config/public-keys',
        '/privacy-policy',
        '/terms-conditions',
        '/sitemap.xml',  # Allow access to sitemap.xml at root
        '/robots.txt',   # Also allow robots.txt
        '/favicon.ico',  # Allow access to favicon at root for browsers/crawlers
        '/shared/note/',  # Allow public access to shared notes
    ]
    
    # Define guest-accessible paths and API endpoints
    guest_accessible_paths = [
        '/',  # Home page accessible to everyone (shows different content based on auth)
        '/create-meme/',
        '/create-meme/api/templates',
        '/create-meme/api/trending-templates',
        '/create-meme/api/meme-db-templates',
        '/create-meme/api/template-details/',
        '/meme-3-2-1/',  # Add Meme 3-2-1 as guest accessible
        '/gifs/',  # Add GIFs as guest accessible
        '/gifs/api/search',
        '/gifs/api/trending',
        '/gifs/api/categories',
        '/gifs/api/category/',
        '/gifs/api/search-suggestions',
        '/meme-to-video/',  # Add Meme to Video as guest accessible
        '/trending-x/',  # Add Trending X as guest accessible
        '/trending-x/api/trends/',  # Allow guest access to view trending data
        '/trending-x/api/countries',  # Allow guest access to country list
        '/saved/',  # Add Saved Memes as guest accessible
        '/blog/',  # Add Blog as guest accessible for SEO
        '/player-stats/',  # Add Player Stats as guest accessible
        '/player-stats/api/',  # Allow guest access to player stats API
    ]
    
    # Skip auth check for public routes and static files
    if request.path in public_paths or request.path.startswith('/static/'):
        return None
    
    # Check if path is guest-accessible
    is_guest_path = any(request.path.startswith(path) for path in guest_accessible_paths)
    
    # Get token
    token = get_token_from_cookie() or get_token_from_header()
    
    if not token:
        # For guest-accessible paths, set guest user
        if is_guest_path:
            g.user_id = 'guest'
            g.user = {
                'id': 'guest',
                'data': {
                    'email': None,
                    'username': 'Guest',
                    'subscription_plan': 'Guest'
                },
                'is_guest': True
            }
            logger.debug(f"Guest access allowed for path: {request.path}")
            return None
        
        logger.warning(f"No valid auth token for path: {request.path}")
        
        # For API paths, return JSON 401 response
        if request.path.startswith('/api/') or '/api/' in request.path:
            return jsonify({"error": "Unauthorized", "reason": "missing_token"}), 401
            
        # For other paths, redirect to login
        return redirect(url_for('core.login', reason='unauthorized'))
    
    payload = verify_token(token)
    
    if not payload:
        # For guest-accessible paths, set guest user even with invalid token
        if is_guest_path:
            g.user_id = 'guest'
            g.user = {
                'id': 'guest',
                'data': {
                    'email': None,
                    'username': 'Guest',
                    'subscription_plan': 'Guest'
                },
                'is_guest': True
            }
            logger.debug(f"Guest access allowed for path (invalid token): {request.path}")
            return None
            
        logger.warning(f"Invalid token for path: {request.path}")
        
        # For API paths, return JSON 401 response
        if request.path.startswith('/api/') or '/api/' in request.path:
            return jsonify({"error": "Unauthorized", "reason": "invalid_token"}), 401
            
        # For other paths, redirect to login
        return redirect(url_for('core.login', reason='invalid'))
    
    # Store user info in g for the request
    g.user_id = payload.get('sub')

    # Initialize basic user data from JWT
    # Try multiple fields for username (Google OAuth uses full_name, email users use username)
    user_metadata = payload.get('user_metadata', {})
    username = (user_metadata.get('username') or
                user_metadata.get('full_name') or
                user_metadata.get('name') or
                payload.get('user_metadata', {}).get('display_name'))

    g.user = {
        'id': payload.get('sub'),
        'data': {
            'email': payload.get('email'),
            'username': username,
            'subscription_plan': user_metadata.get('subscription_plan', 'Free Plan')
        },
        'jwt_claims': payload,
        'is_guest': False
    }

    # IMPORTANT - Load user data from Firebase immediately to ensure correct subscription plan
    try:
        # Import here to avoid circular imports
        from app.system.services.firebase_service import UserService, db

        # Get user data directly from Firebase
        user_data = UserService.get_user(g.user_id)

        if user_data and isinstance(user_data, dict):
            # Create data dict if not exists
            if 'data' not in g.user:
                g.user['data'] = {}

            # Update all user data in g.user
            if 'subscription_plan' in user_data:
                # CRITICAL: Set both in the nested dict and directly to ensure template access
                g.user['data']['subscription_plan'] = user_data['subscription_plan']
                g.user['subscription_plan'] = user_data['subscription_plan']

            if 'credits' in user_data:
                g.user['data']['credits'] = user_data['credits']
                g.user['credits'] = user_data['credits']

            if 'name' in user_data:
                g.user['data']['name'] = user_data['name']
                g.user['name'] = user_data['name']

            if 'username' in user_data:
                g.user['data']['username'] = user_data['username']
                g.user['username'] = user_data['username']

        # Check for active workspace from cookie/session
        workspace_id = request.cookies.get('active_workspace_id', g.user_id)

        # Verify access to workspace if not own workspace
        if workspace_id and workspace_id != g.user_id:
            # Check if user is a team member with active status
            if db:
                membership_query = db.collection('team_members') \
                    .where(filter=FieldFilter('member_id', '==', g.user_id)) \
                    .where(filter=FieldFilter('owner_id', '==', workspace_id)) \
                    .where(filter=FieldFilter('status', '==', 'active')) \
                    .limit(1).get()

                membership_list = list(membership_query)
                if membership_list:
                    membership = membership_list[0].to_dict()
                    g.active_workspace_id = workspace_id
                    g.workspace_permissions = membership.get('permissions', {})
                    g.workspace_role = membership.get('role', 'member')

                    # Load workspace owner data for credits and subscription
                    workspace_user_data = UserService.get_user(workspace_id)
                    if workspace_user_data:
                        g.workspace_data = {
                            'credits': workspace_user_data.get('credits'),
                            'subscription_plan': workspace_user_data.get('subscription_plan'),
                            'email': workspace_user_data.get('email', '')
                        }
                else:
                    # No access, use own workspace
                    g.active_workspace_id = g.user_id
                    g.workspace_permissions = {}
                    g.workspace_role = 'owner'
            else:
                g.active_workspace_id = g.user_id
                g.workspace_permissions = {}
                g.workspace_role = 'owner'
        else:
            g.active_workspace_id = g.user_id
            g.workspace_permissions = {}
            g.workspace_role = 'owner'

    except Exception as e:
        logger.warning(f"Failed to fetch additional user data from Firebase: {str(e)}")
        # Continue without additional data - we already have basic info from JWT
        g.active_workspace_id = g.user_id
        g.workspace_permissions = {}
        g.workspace_role = 'owner'
    
    logger.debug(f"Auth middleware successful for user {g.user_id} on path: {request.path}")

    # Check if user needs to set up their profile (no username)
    # Skip this check for auth routes, API routes, and the setup-profile route itself
    if (not request.path.startswith('/auth/') and
        not request.path.startswith('/api/') and
        not request.path.startswith('/static/') and
        not request.path.startswith('/config/') and
        not request.path.startswith('/payment/webhook')):

        # Check if user has a username
        username = g.user.get('data', {}).get('username')
        if not username:
            logger.info(f"User {g.user_id} needs to set up username, redirecting to setup-profile")
            # Redirect to profile setup page
            return redirect(url_for('core.setup_profile'))

    return None