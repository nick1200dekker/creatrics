"""
TikTok OAuth Service
Handles OAuth flow and token management (similar to YouTube)
"""

import os
import requests
import logging
import secrets
from cryptography.fernet import Fernet
from app.system.services.firebase_service import UserService

logger = logging.getLogger('tiktok_oauth')


class TikTokOAuthService:
    """Service for managing TikTok OAuth tokens"""

    # TikTok OAuth endpoints
    AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"

    # Required scopes
    SCOPES = [
        'user.info.basic',
        'video.upload',
        'video.publish'
    ]

    @staticmethod
    def _get_cipher():
        """Get encryption cipher for tokens"""
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY not set in environment")
        return Fernet(key.encode())

    @staticmethod
    def _encrypt_token(token):
        """Encrypt OAuth token"""
        try:
            cipher = TikTokOAuthService._get_cipher()
            return cipher.encrypt(token.encode()).decode()
        except Exception as e:
            logger.error(f"Error encrypting token: {str(e)}")
            return None

    @staticmethod
    def _decrypt_token(encrypted_token):
        """Decrypt OAuth token"""
        try:
            cipher = TikTokOAuthService._get_cipher()
            return cipher.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            logger.error(f"Error decrypting token: {str(e)}")
            return None

    @staticmethod
    def get_authorization_url(user_id):
        """
        Generate TikTok authorization URL

        Args:
            user_id: User's ID

        Returns:
            str: Authorization URL
        """
        try:
            client_key = os.environ.get('TIKTOK_CLIENT_KEY')
            redirect_uri = os.environ.get('TIKTOK_REDIRECT_URI', 'https://creatrics.com/tiktok/callback')

            if not client_key:
                raise ValueError("TIKTOK_CLIENT_KEY not set")

            # Generate CSRF token
            csrf_token = secrets.token_urlsafe(32)

            # Store CSRF token in user data
            UserService.update_user(user_id, {
                'tiktok_oauth_state': csrf_token
            })

            # Build authorization URL
            scopes = ','.join(TikTokOAuthService.SCOPES)
            auth_url = (
                f"{TikTokOAuthService.AUTH_URL}?"
                f"client_key={client_key}&"
                f"scope={scopes}&"
                f"response_type=code&"
                f"redirect_uri={redirect_uri}&"
                f"state={csrf_token}"
            )

            logger.info(f"Generated TikTok auth URL for user {user_id}")
            return auth_url

        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            raise

    @staticmethod
    def handle_callback(user_id, code, state):
        """
        Handle OAuth callback and exchange code for tokens

        Args:
            user_id: User's ID
            code: Authorization code from TikTok
            state: CSRF state token

        Returns:
            dict: Result with success status
        """
        try:
            # Verify CSRF token
            user_data = UserService.get_user(user_id)
            stored_state = user_data.get('tiktok_oauth_state')

            if state != stored_state:
                logger.error(f"CSRF token mismatch for user {user_id}")
                return {'success': False, 'error': 'Invalid state token'}

            # Exchange code for access token
            client_key = os.environ.get('TIKTOK_CLIENT_KEY')
            client_secret = os.environ.get('TIKTOK_CLIENT_SECRET')
            redirect_uri = os.environ.get('TIKTOK_REDIRECT_URI', 'https://creatrics.com/tiktok/callback')

            if not client_key or not client_secret:
                raise ValueError("TikTok credentials not set")

            token_data = {
                'client_key': client_key,
                'client_secret': client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }

            logger.info(f"Exchanging code for token for user {user_id}")
            response = requests.post(
                TikTokOAuthService.TOKEN_URL,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            response.raise_for_status()

            token_response = response.json()

            # Check for errors
            if 'error' in token_response:
                logger.error(f"TikTok token error: {token_response.get('error')}")
                return {'success': False, 'error': token_response.get('error_description', 'Token exchange failed')}

            # Extract tokens
            access_token = token_response.get('access_token')
            refresh_token = token_response.get('refresh_token')
            expires_in = token_response.get('expires_in')
            open_id = token_response.get('open_id')

            if not access_token:
                return {'success': False, 'error': 'No access token received'}

            # Encrypt tokens
            encrypted_access_token = TikTokOAuthService._encrypt_token(access_token)
            encrypted_refresh_token = TikTokOAuthService._encrypt_token(refresh_token) if refresh_token else None

            if not encrypted_access_token:
                return {'success': False, 'error': 'Failed to encrypt tokens'}

            # Store encrypted tokens in Firebase
            UserService.update_user(user_id, {
                'tiktok_access_token_encrypted': encrypted_access_token,
                'tiktok_refresh_token_encrypted': encrypted_refresh_token,
                'tiktok_expires_in': expires_in,
                'tiktok_open_id': open_id,
                'tiktok_connected': True,
                'tiktok_oauth_state': None  # Clear CSRF token
            })

            logger.info(f"TikTok tokens stored successfully for user {user_id}")

            return {'success': True, 'message': 'TikTok connected successfully'}

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error in TikTok callback: {str(e)}")
            return {'success': False, 'error': 'Failed to connect to TikTok'}
        except Exception as e:
            logger.error(f"Error in TikTok callback: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_access_token(user_id):
        """
        Get decrypted access token for user

        Args:
            user_id: User's ID

        Returns:
            str: Decrypted access token or None
        """
        try:
            user_data = UserService.get_user(user_id)
            if not user_data:
                return None

            encrypted_token = user_data.get('tiktok_access_token_encrypted')
            if not encrypted_token:
                return None

            return TikTokOAuthService._decrypt_token(encrypted_token)

        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None

    @staticmethod
    def is_connected(user_id):
        """
        Check if user has TikTok connected

        Args:
            user_id: User's ID

        Returns:
            bool: True if connected
        """
        try:
            user_data = UserService.get_user(user_id)
            if not user_data:
                return False

            return user_data.get('tiktok_connected', False)

        except Exception as e:
            logger.error(f"Error checking TikTok connection: {str(e)}")
            return False

    @staticmethod
    def disconnect(user_id):
        """
        Disconnect TikTok account

        Args:
            user_id: User's ID

        Returns:
            dict: Result with success status
        """
        try:
            # Remove TikTok tokens
            UserService.update_user(user_id, {
                'tiktok_access_token_encrypted': None,
                'tiktok_refresh_token_encrypted': None,
                'tiktok_expires_in': None,
                'tiktok_open_id': None,
                'tiktok_connected': False,
                'tiktok_oauth_state': None
            })

            logger.info(f"TikTok disconnected for user {user_id}")
            return {'success': True, 'message': 'TikTok disconnected'}

        except Exception as e:
            logger.error(f"Error disconnecting TikTok: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_user_info(user_id):
        """
        Get TikTok user info

        Args:
            user_id: User's ID

        Returns:
            dict: User info from TikTok or None
        """
        try:
            access_token = TikTokOAuthService.get_access_token(user_id)
            if not access_token:
                return None

            # Fetch user info from TikTok
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                TikTokOAuthService.USER_INFO_URL,
                headers=headers,
                params={'fields': 'open_id,union_id,avatar_url,display_name'},
                timeout=10
            )
            response.raise_for_status()

            result = response.json()

            if 'error' in result:
                logger.error(f"TikTok user info error: {result.get('error')}")
                return None

            user_data = result.get('data', {}).get('user', {})

            return {
                'open_id': user_data.get('open_id'),
                'display_name': user_data.get('display_name'),
                'avatar_url': user_data.get('avatar_url')
            }

        except Exception as e:
            logger.error(f"Error getting TikTok user info: {str(e)}")
            return None

    @staticmethod
    def refresh_access_token(user_id):
        """
        Refresh TikTok access token

        Args:
            user_id: User's ID

        Returns:
            dict: Result with success status
        """
        try:
            user_data = UserService.get_user(user_id)
            if not user_data:
                return {'success': False, 'error': 'User not found'}

            encrypted_refresh_token = user_data.get('tiktok_refresh_token_encrypted')
            if not encrypted_refresh_token:
                return {'success': False, 'error': 'No refresh token'}

            refresh_token = TikTokOAuthService._decrypt_token(encrypted_refresh_token)
            if not refresh_token:
                return {'success': False, 'error': 'Failed to decrypt refresh token'}

            client_key = os.environ.get('TIKTOK_CLIENT_KEY')
            client_secret = os.environ.get('TIKTOK_CLIENT_SECRET')

            token_data = {
                'client_key': client_key,
                'client_secret': client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }

            response = requests.post(
                TikTokOAuthService.TOKEN_URL,
                json=token_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()

            token_response = response.json()

            if 'error' in token_response:
                return {'success': False, 'error': token_response.get('error_description')}

            # Encrypt new tokens
            new_access_token = token_response.get('access_token')
            new_refresh_token = token_response.get('refresh_token')

            encrypted_access = TikTokOAuthService._encrypt_token(new_access_token)
            encrypted_refresh = TikTokOAuthService._encrypt_token(new_refresh_token) if new_refresh_token else encrypted_refresh_token

            # Update tokens
            UserService.update_user(user_id, {
                'tiktok_access_token_encrypted': encrypted_access,
                'tiktok_refresh_token_encrypted': encrypted_refresh,
                'tiktok_expires_in': token_response.get('expires_in')
            })

            logger.info(f"TikTok token refreshed for user {user_id}")
            return {'success': True, 'message': 'Token refreshed'}

        except Exception as e:
            logger.error(f"Error refreshing TikTok token: {str(e)}")
            return {'success': False, 'error': str(e)}
