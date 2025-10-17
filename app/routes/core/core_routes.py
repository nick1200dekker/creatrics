from flask import Blueprint, render_template, redirect, url_for, jsonify, request, g, current_app, make_response, flash
from app.system.auth.supabase import auth_required
from app.system.auth.middleware import set_auth_cookie, clear_auth_cookie, verify_token, get_token_from_cookie, get_token_from_header, optional_auth, COOKIE_NAME, COOKIE_PATH, COOKIE_DOMAIN
from app.system.services.firebase_service import UserService, StorageService
from app.system.services.email_service import email_service
from app.system.services.welcome_email_scheduler import welcome_scheduler
from app.config import get_config
import logging
import jwt
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from functools import wraps

# Setup logger
logger = logging.getLogger('core_routes')

# Create core blueprint
bp = Blueprint('core', __name__)


# Admin required decorator
def admin_required(f):
    """Decorator to require admin privileges
    
    This decorator should be used AFTER @auth_required to ensure the user is authenticated first.
    It checks if the user has an admin subscription plan.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Ensure user is authenticated
        if not g.user:
            logger.warning("Admin check failed - no authenticated user")
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('core.login'))
        
        # Get user's subscription plan - fetch fresh data to avoid timing issues
        user_id = g.user.get('id')
        try:
            from app.system.services.firebase_service import UserService
            user_data = UserService.get_user(user_id)
            subscription_plan = user_data.get('subscription_plan', 'Free Plan') if user_data else 'Free Plan'
            logger.info(f"Admin check for user {user_id}: fetched subscription_plan = '{subscription_plan}'")
        except Exception as e:
            logger.error(f"Admin check failed to fetch user data for {user_id}: {e}")
            subscription_plan = g.user.get('subscription_plan', 'Free Plan')
            logger.info(f"Admin check for user {user_id}: fallback subscription_plan = '{subscription_plan}'")
        
        # Normalize the plan name for comparison
        normalized_plan = subscription_plan.lower().strip()
        
        # Check if user has admin plan
        admin_plans = ['admin', 'admin plan', 'administrator']
        if normalized_plan not in admin_plans:
            logger.warning(f"Admin access denied for user {g.user.get('id')} with plan: {subscription_plan}")
            flash('Admin access required. Please upgrade to an admin plan.', 'error')
            return redirect(url_for('home.dashboard'))
            
        logger.info(f"Admin access granted for user {g.user.get('id')}")
        return f(*args, **kwargs)
    return decorated_function


# Landing and public pages - root route now handled by home blueprint


# Authentication routes
@bp.route('/auth/login')
def login():
    """Render login page"""
    # Get Supabase credentials
    config = get_config()
    supabase_url = config.get('supabase_url', '')
    supabase_key = config.get('supabase_anon_key', '')
    
    logger.info(f"Login page loaded with Supabase URL: {bool(supabase_url)}")
    
    # Get return URL from query params
    return_to = request.args.get('return_to', '/')
    
    return render_template(
        'auth/login.html',
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        return_to=return_to
    )


@bp.route('/auth/register')
def register():
    """Render registration page"""
    # Get Supabase credentials
    config = get_config()
    supabase_url = config.get('supabase_url', '')
    supabase_key = config.get('supabase_anon_key', '')
    
    logger.info(f"Register page loaded with Supabase URL: {bool(supabase_url)}")
    
    return render_template(
        'auth/register.html',
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )


@bp.route('/auth/forgot-password')
def forgot_password():
    """Render forgot password page"""
    # Get Supabase credentials
    config = get_config()
    supabase_url = config.get('supabase_url', '')
    supabase_key = config.get('supabase_anon_key', '')
    
    logger.info(f"Forgot password page loaded with Supabase URL: {bool(supabase_url)}")
    
    return render_template(
        'auth/forgot_password.html',
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )


@bp.route('/auth/reset-password')
def reset_password():
    """Render reset password page"""
    # Get Supabase credentials
    config = get_config()
    supabase_url = config.get('supabase_url', '')
    supabase_key = config.get('supabase_anon_key', '')
    
    logger.info(f"Reset password page loaded with Supabase URL: {bool(supabase_url)}")
    
    return render_template(
        'auth/reset_password.html',
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )


@bp.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    """Handle logout - clear session cookie and redirect to home page"""
    response = make_response(redirect(url_for('home.dashboard')))
    clear_auth_cookie(response)
    logger.info("User logged out")
    return response


@bp.route('/auth/callback')
def auth_callback():
    """Handle authentication callbacks from Supabase"""
    # Simplified callback page that will be handled client-side
    logger.info("Auth callback route accessed")
    return render_template('auth/callback.html')


@bp.route('/auth/session', methods=['POST'])
def create_session():
    """Create a new session with the provided token"""
    try:
        logger.info("Session creation endpoint called")
        
        # Get token from request
        if request.is_json:
            data = request.json
            token = data.get('token')
            return_to = data.get('return_to', '/')
        else:
            token = request.form.get('token')
            return_to = request.form.get('return_to', '/')
        
        if not token:
            logger.warning("No token provided in session creation request")
            return jsonify({"success": False, "error": "No token provided"}), 400
        
        logger.info(f"Processing token for session creation: {token[:10]}...")
        
        # Verify token
        payload = verify_token(token)
        
        if not payload:
            logger.warning("Invalid token for session creation")
            return jsonify({"success": False, "error": "Invalid token"}), 400
        
        user_id = payload.get('sub')
        logger.info(f"Creating session for user: {user_id}")
        
        # Get user metadata
        user_metadata = payload.get('user_metadata', {})
        email = payload.get('email')

        # Get username - try multiple fields (Google OAuth uses full_name, email users use username)
        username = (user_metadata.get('username') or
                    user_metadata.get('full_name') or
                    user_metadata.get('name') or
                    user_metadata.get('display_name'))
        if not username and email:
            username = email.split('@')[0]
        if not username:
            username = f"user_{user_id[:8]}"

        # Extract first name only (for Google OAuth users with full names)
        if username and ' ' in username:
            username = username.split()[0]

        # Check if user exists in Firebase
        user = UserService.get_user(user_id)
        is_new_user = False

        if not user:
            # Create user from token data
            try:
                UserService.create_user(user_id, {
                    'username': username,
                    'email': email,
                    'subscription_plan': user_metadata.get('subscription_plan', 'Free Plan'),
                    'credits': 5  # Give new users 5 credits to start with
                })
                logger.info(f"User {user_id} created in Firebase during session creation")
                is_new_user = True
            except Exception as create_error:
                logger.error(f"Failed to create user in Firebase: {str(create_error)}")
                # Continue anyway - we want the login to succeed
        else:
            logger.info(f"User {user_id} already exists in Firebase")

        # Send welcome email for new users
        if is_new_user and email:
            # Check provider from app_metadata
            provider = payload.get('app_metadata', {}).get('provider', 'email')

            if provider == 'google' or provider == 'oauth':
                # OAuth users (Google) - send welcome email immediately
                try:
                    logger.info(f"Sending immediate welcome email to OAuth user: {email}")
                    email_service.send_welcome_email(email, username)
                except Exception as email_error:
                    logger.error(f"Failed to send welcome email to {email}: {str(email_error)}")
            else:
                # Email/password users - schedule welcome email after 10 minutes
                try:
                    logger.info(f"Scheduling delayed welcome email for email user: {email}")
                    welcome_scheduler.schedule_welcome_email(email, username, delay_seconds=600)
                except Exception as email_error:
                    logger.error(f"Failed to schedule welcome email for {email}: {str(email_error)}")
        
        # Create response with session cookie
        response = make_response(jsonify({
            "success": True, 
            "user_id": user_id,
            "username": username,
            "return_to": return_to
        }))
        
        # Set auth cookie in response
        set_auth_cookie(response, token)
        
        return response
    
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Check if the current request is authenticated"""
    # Get token from cookie or header
    token = get_token_from_cookie() or get_token_from_header()
    
    if not token:
        logger.warning("No token found in check-auth request")
        return jsonify({
            "authenticated": False,
            "error": "No authentication token"
        }), 401
    
    try:
        payload = verify_token(token)
        
        if not payload:
            logger.warning("Invalid token in check-auth")
            return jsonify({
                "authenticated": False,
                "error": "Invalid token",
                "redirect": url_for('core.login', reason='session_expired', _external=True),
                "clearCookies": [{
                    "name": COOKIE_NAME,
                    "path": COOKIE_PATH,
                    "domain": COOKIE_DOMAIN
                }]
            }), 401
        
        user_id = payload.get('sub')
        logger.info(f"Auth check successful for user: {user_id}")
        
        return jsonify({
            "authenticated": True,
            "user_id": user_id,
            "email": payload.get('email'),
            "username": payload.get('user_metadata', {}).get('username')
        })
        
    except Exception as e:
        logger.error(f"Error checking auth: {str(e)}")
        return jsonify({
            "authenticated": False,
            "error": str(e)
        }), 401


@bp.route('/auth/setup-profile')
@auth_required
def setup_profile():
    """Show the profile setup page for users without a username"""
    # Check if user already has a username
    if g.user and g.user.get('data', {}).get('username'):
        # User already has a username, redirect to dashboard
        return redirect(url_for('home.dashboard'))

    # Get Supabase credentials for the page
    config = get_config()
    supabase_url = config.get('supabase_url', '')
    supabase_key = config.get('supabase_anon_key', '')

    return render_template(
        'auth/setup_profile.html',
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )


@bp.route('/auth/setup-profile', methods=['POST'])
@auth_required
def setup_profile_post():
    """Handle profile setup form submission"""
    import requests
    import json

    try:
        # Get the JSON data from the request
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        username = data.get('username', '').strip()
        display_name = data.get('display_name', '').strip() or username

        # Validate username
        if not username:
            return jsonify({"success": False, "error": "Username is required"}), 400

        if len(username) < 2 or len(username) > 20:
            return jsonify({"success": False, "error": "Username must be between 2-20 characters"}), 400

        import re
        if not re.match(r'^[a-zA-Z0-9]+$', username):
            return jsonify({"success": False, "error": "Username can only contain letters and numbers"}), 400

        # Update the user's metadata in Supabase
        config = get_config()
        user_id = g.user.get('id')

        # Use Supabase Admin API to update user metadata
        update_url = f"{config['supabase_url']}/auth/v1/admin/users/{user_id}"
        headers = {
            'Authorization': f"Bearer {config['supabase_service_key']}",
            'apikey': config['supabase_service_key'],
            'Content-Type': 'application/json'
        }

        update_data = {
            'user_metadata': {
                'username': username,
                'display_name': display_name
            }
        }

        response = requests.put(update_url, headers=headers, json=update_data)

        if response.status_code != 200:
            logger.error(f"Failed to update user metadata: {response.text}")
            return jsonify({"success": False, "error": "Failed to update profile"}), 500

        # Also update in Firebase for consistency
        try:
            user_data = UserService.get_user(user_id)
            if user_data:
                user_data['username'] = username
                user_data['display_name'] = display_name
                UserService.update_user(user_id, user_data)
        except Exception as e:
            logger.warning(f"Failed to update Firebase user data: {str(e)}")
            # Continue anyway as Supabase is the source of truth

        # Return success with redirect URL
        return jsonify({
            "success": True,
            "message": "Profile updated successfully!",
            "redirect": url_for('home.dashboard')
        })

    except Exception as e:
        logger.error(f"Error setting up profile: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Configuration endpoint
@bp.route('/config/public-keys')
def public_keys():
    """Return public keys for client-side auth"""
    try:
        config = get_config()
        result = {
            "supabase_url": config.get('supabase_url', ''),
            "supabase_key": config.get('supabase_anon_key', ''),
            "firebase_bucket": config.get('firebase_storage_bucket', '').replace('gs://', '')
        }
        
        logger.debug(f"Returning public keys: {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in public_keys endpoint: {str(e)}")
        return jsonify({
            "error": "Configuration error", 
            "message": str(e),
            "supabase_url": "",
            "supabase_key": ""
        }), 500


# User profile API
@bp.route('/users/profile', methods=['GET'])
# @auth_required - Removed since middleware now handles authentication
def get_profile():
    """Get current user info"""
    # Check if user is guest
    if g.user and g.user.get('is_guest'):
        return jsonify({"error": "Please login to access profile"}), 401
        
    user_id = g.user.get('id')
    logger.info(f"Profile request for user: {user_id}")
    
    # Log user info from auth
    logger.debug(f"User data from auth: {g.user}")
    
    try:
        # Check if user exists in Firestore
        user = UserService.get_user(user_id)
        
        # If user doesn't exist in Firestore, create them
        if not user:
            logger.info(f"User {user_id} not found in Firestore, creating new user")
            
            # Extract user data from JWT claims
            user_data = g.user.get('jwt_claims', {})
            user_metadata = user_data.get('user_metadata', {})
            email = user_data.get('email')

            logger.debug(f"JWT claims: {user_data}")
            logger.debug(f"User metadata: {user_metadata}")

            # Get username - try multiple fields (Google OAuth uses full_name, email users use username)
            username = (user_metadata.get('username') or
                        user_metadata.get('full_name') or
                        user_metadata.get('name') or
                        user_metadata.get('display_name'))
            if not username and email:
                username = email.split('@')[0]
            if not username:
                username = f"user_{user_id[:8]}"

            # Extract first name only (for Google OAuth users with full names)
            if username and ' ' in username:
                username = username.split()[0]

            logger.info(f"Using username: {username}")
            
            try:
                # Create user in Firestore
                user = UserService.create_user(user_id, {
                    'username': username,
                    'email': email,
                    'subscription_plan': user_metadata.get('subscription_plan', 'Free Plan'),
                    'credits': 5  # Give new users 5 credits to start
                })
                logger.info(f"User {user_id} created successfully in Firestore")
            except Exception as create_error:
                logger.error(f"Error creating user {user_id} in Firestore: {str(create_error)}")
                user = {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'subscription_plan': 'Free Plan',
                    'credits': 0,
                    'error': str(create_error)
                }
        else:
            logger.info(f"User {user_id} found in Firestore")
        
        # IMPORTANT: Override the subscription_plan from Firestore with the one from middleware
        # This ensures we always use the most up-to-date plan from Firebase auth
        if g.user and g.user.get('subscription_plan'):
            user['subscription_plan'] = g.user.get('subscription_plan')
            logger.info(f"Overriding subscription plan from middleware: {user['subscription_plan']}")
            
        return jsonify(user)
    except Exception as e:
        logger.error(f"Error in profile endpoint for user {user_id}: {str(e)}")
        return jsonify({'error': str(e), 'id': user_id}), 500


# Credit transactions API
@bp.route('/api/credit-transactions', methods=['GET'])
@auth_required
def get_credit_transactions():
    """Get credit transaction history for the current user"""
    try:
        from app.system.credits.credits_manager import CreditsManager
        
        user_id = g.user.get('id')
        limit = request.args.get('limit', 20, type=int)
        
        # Get transaction history
        credits_manager = CreditsManager()
        transactions = credits_manager.get_transaction_history(user_id, limit)
        
        # Log the transactions for debugging
        logger.info(f"Retrieved {len(transactions)} transactions for user {user_id}")
        
        return jsonify({
            "success": True,
            "transactions": transactions,
            "current_balance": credits_manager.get_user_credits(user_id)
        })
    except Exception as e:
        logger.error(f"Error getting credit transactions: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# Admin API endpoint example
@bp.route('/api/admin/stats', methods=['GET'])
@auth_required
@admin_required
def get_admin_stats():
    """Get admin statistics - only accessible by admin users"""
    try:
        # Example admin-only endpoint
        # You would implement actual admin statistics here
        logger.info(f"Admin stats requested by user {g.user.get('id')}")
        
        return jsonify({
            "success": True,
            "message": "Admin statistics endpoint",
            "user_count": 0,  # Placeholder
            "total_credits_used": 0,  # Placeholder
            "active_subscriptions": 0,  # Placeholder
        })
    except Exception as e:
        logger.error(f"Error getting admin stats: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# File management APIs
@bp.route('/files', methods=['GET'])
@auth_required
def list_files():
    """List files in a user's directory"""
    user_id = g.user.get('id')
    directory = request.args.get('directory', 'data')
    files = StorageService.list_files(user_id, directory)
    return jsonify(files)


@bp.route('/files/upload', methods=['POST'])
@auth_required
def upload_file():
    """Upload a file to the user's directory"""
    user_id = g.user.get('id')
    directory = request.form.get('directory', 'data')
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    filename = secure_filename(file.filename)

    # Upload the file
    result = StorageService.upload_file(
        user_id, 
        directory,
        filename,
        file
    )

    return jsonify({
        "success": True, 
        "filename": filename,
        "path": result['path'],
        "url": result['url']
    })


@bp.route('/files', methods=['DELETE'])
@auth_required
def delete_file():
    """Delete a file from user's directory"""
    user_id = g.user.get('id')
    directory = request.args.get('directory', 'data')
    filename = request.args.get('filename')
    
    if not filename:
        return jsonify({"error": "Filename is required"}), 400
        
    success = StorageService.delete_file(user_id, directory, filename)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "File not found"}), 404


@bp.route('/files/config', methods=['GET'])
@auth_required
def get_config_file():
    """Get configuration for the current user"""
    user_id = g.user.get('id')
    config_name = request.args.get('name', 'settings.json')
    config = StorageService.get_config_file(user_id, config_name)
    
    if config is None:
        return jsonify({"error": "Config not found"}), 404
        
    return jsonify(config)


@bp.route('/files/config', methods=['POST'])
@auth_required
def save_config_file():
    """Save configuration for the current user"""
    user_id = g.user.get('id')
    config_name = request.form.get('name', 'settings.json')
    
    # Get configuration data
    if request.is_json:
        config_data = request.json
    else:
        config_data = request.form.get('data')

    # Save the configuration
    url = StorageService.save_config_file(
        user_id,
        config_name,
        config_data
    )

    return jsonify({"success": True, "url": url})


# Legal pages routes
@bp.route('/privacy-policy')
def privacy_policy():
    """Render privacy policy page"""
    return render_template('auth/privacy-policy.html')


@bp.route('/terms-conditions')
def terms_conditions():
    """Render terms and conditions page"""
    return render_template('auth/terms-conditions.html')