# File: app/routes/accounts/youtube.py
# Clean YouTube route handlers with automatic analytics fetching

from flask import Blueprint, redirect, url_for, request, flash, g, session, jsonify
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import UserService
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from cryptography.fernet import Fernet
import os
import json
import logging
import datetime
import threading
import tempfile

# Setup logger
logger = logging.getLogger('youtube_routes')

# Allow insecure transport for development only
if os.environ.get('FLASK_ENV') == 'development':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Create YouTube blueprint
bp = Blueprint('youtube', __name__, url_prefix='/accounts/youtube')

# YouTube API scopes
YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl',  # Full access (includes readonly)
    'https://www.googleapis.com/auth/yt-analytics.readonly',
    'https://www.googleapis.com/auth/yt-analytics-monetary.readonly'
]

# Configuration - Environment dependent
def get_redirect_uri():
    """Get redirect URI based on environment"""
    base_url = os.environ.get('BASE_URL', 'http://localhost:8080')
    return f"{base_url}/accounts/youtube/callback"

def get_client_secrets_file():
    """Get or create client secrets file from environment variable"""
    # Try to get from environment variable (JSON string)
    client_secrets_json = os.environ.get('YOUTUBE_CLIENT_SECRETS_JSON')
    
    if client_secrets_json:
        # Create temporary file with the JSON content
        try:
            secrets_data = json.loads(client_secrets_json)
            
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(secrets_data, temp_file, indent=2)
            temp_file.close()
            
            logger.info(f"Created temporary client secrets file: {temp_file.name}")
            return temp_file.name
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in YOUTUBE_CLIENT_SECRETS_JSON: {str(e)}")
            return None
    
    # Fallback to file path for local development
    file_path = os.environ.get('YOUTUBE_CLIENT_SECRETS_FILE', 'client_secret.json')
    if os.path.exists(file_path):
        return file_path
    
    logger.error("No YouTube client secrets found in environment or file system")
    return None

def cleanup_temp_file(file_path):
    """Clean up temporary files safely"""
    if file_path and file_path.startswith('/tmp'):
        try:
            os.unlink(file_path)
            logger.debug(f"Cleaned up temporary file: {file_path}")
        except OSError as e:
            logger.warning(f"Could not clean up temporary file {file_path}: {str(e)}")

# Encryption setup
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key()
    os.environ['ENCRYPTION_KEY'] = ENCRYPTION_KEY.decode() if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_token(token_data):
    """Encrypt token data before storing"""
    token_json = json.dumps(token_data)
    encrypted_token = cipher_suite.encrypt(token_json.encode())
    return encrypted_token.decode()

def validate_scopes(received_scopes):
    """Validate that received scopes include required YouTube scopes"""
    if isinstance(received_scopes, str):
        received_scopes = received_scopes.split()
    
    required_scopes = set(YOUTUBE_SCOPES)
    received_scopes_set = set(received_scopes)
    
    # Check if all required scopes are present
    if not required_scopes.issubset(received_scopes_set):
        missing_scopes = required_scopes - received_scopes_set
        logger.error(f"Missing required scopes: {missing_scopes}")
        return False
    
    # Log any additional scopes but don't fail
    additional_scopes = received_scopes_set - required_scopes
    if additional_scopes:
        logger.info(f"Additional scopes granted: {additional_scopes}")
    
    return True

@bp.route('/connect', methods=['GET'])
@auth_required
def connect_youtube():
    """Start YouTube OAuth flow - Separate from login OAuth!"""
    user_id = g.user.get('id')

    # This uses a DIFFERENT OAuth client than login
    client_secrets_file = get_client_secrets_file()
    if not client_secrets_file:
        logger.error("YouTube client secrets not configured")
        flash("YouTube integration not configured. Please contact support.", "error")
        return redirect(url_for('accounts.index'))
    
    try:
        redirect_uri = get_redirect_uri()

        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=YOUTUBE_SCOPES,
            redirect_uri=redirect_uri
        )

        auth_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )

        session['state'] = state
        session['user_id'] = user_id

        logger.info(f"Starting YouTube OAuth flow for user {user_id} with redirect_uri: {redirect_uri}")
        return redirect(auth_url)
    
    except Exception as e:
        logger.error(f"Error starting YouTube OAuth flow: {str(e)}")
        flash("Failed to connect to YouTube. Please try again later.", "error")
        return redirect(url_for('accounts.index'))
    finally:
        # Clean up temporary file if created
        cleanup_temp_file(client_secrets_file)

@bp.route('/callback', methods=['GET'])
def youtube_callback():
    """Handle OAuth callback and fetch initial analytics"""
    state = session.get('state')
    user_id = session.get('user_id')

    if not state or not user_id:
        flash("Authentication failed: Session expired", "error")
        return redirect(url_for('accounts.index'))

    client_secrets_file = get_client_secrets_file()
    if not client_secrets_file:
        logger.error("YouTube client secrets not configured during callback")
        flash("Configuration error during authentication", "error")
        return redirect(url_for('accounts.index'))

    try:
        redirect_uri = get_redirect_uri()

        # Exchange authorization code for credentials
        flow = Flow.from_client_secrets_file(
            client_secrets_file,
            scopes=YOUTUBE_SCOPES,
            redirect_uri=redirect_uri,
            state=state
        )

        # Construct proper HTTPS callback URL for Cloud Run
        callback_url = request.url
        if callback_url.startswith('http://') and os.environ.get('BASE_URL', '').startswith('https://'):
            callback_url = callback_url.replace('http://', 'https://', 1)

        flow.fetch_token(authorization_response=callback_url)
        credentials = flow.credentials
        
        # Validate scopes (but don't fail if additional scopes are present)
        if credentials.scopes:
            if not validate_scopes(credentials.scopes):
                logger.warning(f"Scope validation failed, but continuing with authentication")
        
        # Prepare and encrypt credentials
        creds_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }
        
        encrypted_creds = encrypt_token(creds_dict)
        
        # Get YouTube channel info
        youtube = build('youtube', 'v3', credentials=credentials)
        try:
            channels_response = youtube.channels().list(part='snippet', mine=True).execute()
        except Exception as channel_error:
            error_str = str(channel_error).lower()
            if 'quota' in error_str or 'quotaexceeded' in error_str:
                flash("Daily YouTube API quota limit hit. We've requested more quota from YouTube. Resets at midnight Pacific Time.", "error")
                return redirect(url_for('accounts.index'))
            raise  # Re-raise other errors to be caught by outer try-except

        if not channels_response.get('items'):
            flash("No YouTube channel found for this account", "error")
            return redirect(url_for('accounts.index'))
        
        channel_title = channels_response['items'][0]['snippet']['title']
        channel_id = channels_response['items'][0]['id']
        
        # Store YouTube credentials and channel info
        UserService.update_user(user_id, {
            'youtube_account': channel_title,
            'youtube_channel_id': channel_id,
            'youtube_credentials': encrypted_creds,
            'youtube_connected_at': datetime.datetime.now().isoformat(),
            'youtube_setup_complete': False
        })
        
        # Clear session data
        session.pop('state', None)
        session.pop('user_id', None)
        
        # Fetch initial analytics in background
        def fetch_initial_analytics():
            try:
                from app.scripts.accounts.youtube_analytics import fetch_youtube_analytics
                logger.info(f"Fetching initial YouTube analytics for user {user_id}")
                fetch_youtube_analytics(user_id)
                logger.info(f"Initial YouTube analytics fetched successfully for user {user_id}")
                # Mark setup as complete
                UserService.update_user(user_id, {'youtube_setup_complete': True})
            except Exception as e:
                logger.error(f"Error fetching initial YouTube analytics: {str(e)}")
                # Mark setup as complete even on error so modal closes
                UserService.update_user(user_id, {'youtube_setup_complete': True})

        # Start analytics fetch in background
        thread = threading.Thread(target=fetch_initial_analytics)
        thread.daemon = True
        thread.start()

        logger.info(f"Successfully connected YouTube channel: {channel_title}")
        flash(f"Successfully connected YouTube channel: {channel_title}", "success")
        return redirect(url_for('accounts.index'))
    
    except Exception as e:
        logger.error(f"Error in YouTube callback: {str(e)}")
        flash("Failed to complete YouTube connection. Please try again.", "error")
        return redirect(url_for('accounts.index'))
    finally:
        # Clean up temporary file if created
        cleanup_temp_file(client_secrets_file)

@bp.route('/analytics', methods=['GET'])
@auth_required
def get_analytics():
    """Get YouTube analytics data"""
    user_id = g.user.get('id')
    
    user_data = UserService.get_user(user_id)
    if not user_data or not user_data.get('youtube_credentials'):
        return jsonify({'error': 'YouTube account not connected'}), 400
    
    try:
        from google.cloud import firestore
        import firebase_admin
        
        # Initialize Firestore if needed
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get analytics from subcollection
        analytics_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('metrics')
        analytics_doc = analytics_ref.get()
        
        if analytics_doc.exists:
            analytics = analytics_doc.to_dict()
            last_updated = analytics.get('timestamp')
            
            # If analytics were updated in the last 4 hours, return cached data
            if last_updated:
                try:
                    last_update_time = datetime.datetime.fromisoformat(last_updated)
                    if (datetime.datetime.now() - last_update_time).total_seconds() < 14400:  # 4 hours
                        return jsonify({'data': analytics, 'source': 'cache'})
                except (ValueError, TypeError):
                    pass
        
        # Fetch fresh data if no recent cache
        try:
            from app.scripts.accounts.youtube_analytics import fetch_youtube_analytics
            analytics_data = fetch_youtube_analytics(user_id)
            
            if analytics_data:
                return jsonify({'data': analytics_data, 'source': 'fresh'})
            else:
                return jsonify({'error': 'Failed to fetch analytics data'}), 500
        except Exception as e:
            logger.error(f"Error fetching fresh analytics: {str(e)}")
            return jsonify({'error': f'Analytics fetch failed: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Error in get_analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics data'}), 500

@bp.route('/disconnect', methods=['POST'])
@auth_required
def disconnect_youtube():
    """Disconnect YouTube account and clean up all data"""
    user_id = g.user.get('id')
    
    try:
        logger.info(f"Disconnecting YouTube account for user {user_id}")
        
        # Clean up analytics data first
        try:
            from app.scripts.accounts.youtube_analytics import clean_youtube_user_data
            cleanup_success = clean_youtube_user_data(user_id)
            if cleanup_success:
                logger.info(f"YouTube analytics data cleaned successfully for user {user_id}")
            else:
                logger.warning(f"YouTube analytics data cleanup had issues for user {user_id}")
        except Exception as e:
            logger.error(f"Error cleaning YouTube analytics data: {str(e)}")
            cleanup_success = False
        
        # Remove YouTube credentials and info from user document
        # CRITICAL: Use DELETE_FIELD to physically remove tokens from storage (YouTube API compliance)
        from google.cloud import firestore as fs
        UserService.update_user(user_id, {
            'youtube_account': fs.DELETE_FIELD,
            'youtube_channel_id': fs.DELETE_FIELD,
            'youtube_credentials': fs.DELETE_FIELD,
            'youtube_connected_at': fs.DELETE_FIELD,
            'youtube_setup_complete': fs.DELETE_FIELD,
            'youtube_channel_keywords': fs.DELETE_FIELD
        })
        
        if cleanup_success:
            flash("YouTube account disconnected successfully", "success")
        else:
            flash("YouTube account disconnected (some data cleanup issues)", "warning")
        
        return redirect(url_for('accounts.index'))
        
    except Exception as e:
        logger.error(f"Error disconnecting YouTube: {str(e)}")
        flash("Error disconnecting YouTube account", "error")
        return redirect(url_for('accounts.index'))

@bp.route('/test-config', methods=['GET'])
def test_config():
    """Test endpoint to verify YouTube configuration"""
    client_secrets_file = get_client_secrets_file()
    redirect_uri = get_redirect_uri()
    
    config_status = {
        'client_secrets_configured': client_secrets_file is not None,
        'redirect_uri': redirect_uri,
        'base_url': os.environ.get('BASE_URL', 'Not set'),
        'environment': os.environ.get('FLASK_ENV', 'production'),
        'has_client_secrets_json': bool(os.environ.get('YOUTUBE_CLIENT_SECRETS_JSON')),
        'has_client_secrets_file': bool(os.environ.get('YOUTUBE_CLIENT_SECRETS_FILE')),
        'encryption_key_configured': bool(os.environ.get('ENCRYPTION_KEY'))
    }
    
    # Clean up test file if created
    cleanup_temp_file(client_secrets_file)
    
    return jsonify(config_status)