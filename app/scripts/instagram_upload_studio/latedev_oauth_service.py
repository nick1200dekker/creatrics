"""
Late.dev OAuth Service
Handles Instagram account connection via Late.dev API
"""

import os
import requests
import logging
from app.system.services.firebase_service import UserService

logger = logging.getLogger('latedev_oauth')

class LateDevOAuthService:
    """Service for managing Instagram OAuth via Late.dev"""

    BASE_URL = "https://getlate.dev/api/v1"
    API_KEY = os.environ.get('LATEDEV_API_KEY')

    @staticmethod
    def _map_platform_name(platform):
        """Map internal platform names to Late.dev API platform names"""
        if platform in ['x', 'twitter']:
            return 'twitter'
        return platform

    @staticmethod
    def get_authorization_url(user_id, platform='instagram'):
        """
        Get Late.dev authorization URL for connecting Instagram

        Args:
            user_id: User's ID
            platform: Social platform (instagram, tiktok, x, etc.)

        Returns:
            str: Authorization URL to redirect user to
        """
        if not LateDevOAuthService.API_KEY:
            raise ValueError("LATEDEV_API_KEY not configured")

        try:
            # Get or create profile for this user
            profile_id = LateDevOAuthService._get_or_create_profile(user_id)

            # Build callback URL based on platform
            callback_url = os.environ.get('BASE_URL', 'http://localhost:8080')

            # Map platform to Late.dev API name
            api_platform = LateDevOAuthService._map_platform_name(platform)

            # Build callback URL based on platform
            if platform == 'tiktok':
                redirect_url = f"{callback_url}/tiktok-upload-studio/callback"
            elif platform in ['x', 'twitter']:
                redirect_url = f"{callback_url}/x_post_editor/callback"
            elif platform == 'youtube':
                redirect_url = f"{callback_url}/video-title-tags/callback"
            else:
                redirect_url = f"{callback_url}/instagram-upload-studio/callback"

            # Call Late.dev API to get the auth URL
            headers = {
                'Authorization': f'Bearer {LateDevOAuthService.API_KEY}',
                'Content-Type': 'application/json'
            }

            connect_url = f"{LateDevOAuthService.BASE_URL}/connect/{api_platform}"
            params = {
                'profileId': profile_id,
                'redirect_url': redirect_url
            }

            print(f"=== LATE.DEV DEBUG ===")
            print(f"Calling Late.dev connect API for user {user_id}, platform {platform}")
            print(f"URL: {connect_url}")
            print(f"Params: {params}")
            print(f"Profile ID: {profile_id}")
            print(f"=== END DEBUG ===")

            logger.info(f"Calling Late.dev connect API for user {user_id}, platform {platform}")
            logger.info(f"URL: {connect_url}")
            logger.info(f"Params: {params}")
            logger.info(f"Profile ID: {profile_id}")

            response = requests.get(
                connect_url,
                headers=headers,
                params=params,
                timeout=10
            )

            print(f"=== LATE.DEV RESPONSE ===")
            print(f"Status: {response.status_code}")
            print(f"Response URL: {response.url}")
            print(f"Response body: {response.text}")
            print(f"=== END RESPONSE ===")

            logger.info(f"Late.dev connect response: {response.status_code}")
            logger.info(f"Response URL: {response.url}")
            logger.info(f"Response body: {response.text}")

            if response.status_code == 200:
                data = response.json()
                auth_url = data.get('authUrl')

                if auth_url:
                    logger.info(f"Got auth URL from Late.dev: {auth_url}")
                    return auth_url
                else:
                    logger.error(f"No authUrl in response: {data}")
                    raise Exception("Late.dev did not return an authUrl")
            elif response.status_code == 404 and 'Profile not found' in response.text:
                # Profile not found - it was probably deleted from Late.dev dashboard
                # Clear the stored profile_id and try creating a new one
                print(f"=== PROFILE NOT FOUND - CLEARING AND RETRYING ===")
                logger.warning(f"Profile {profile_id} not found in Late.dev, clearing stored ID and retrying")
                UserService.update_user(user_id, {
                    'latedev_profile_id': None
                })
                # Recursively call to create new profile
                return LateDevOAuthService.get_authorization_url(user_id, platform)
            else:
                logger.error(f"Failed to get auth URL: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get auth URL from Late.dev: {response.status_code}")


        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            raise

    @staticmethod
    def _get_or_create_profile(user_id):
        """
        Get or create Late.dev profile for a specific user
        Each user in your app gets their own Late.dev profile
        """
        try:
            logger.info(f"Getting or creating Late.dev profile for user {user_id}")

            # Check if user already has profile_id stored in Firebase
            user_data = UserService.get_user(user_id)
            if user_data and user_data.get('latedev_profile_id'):
                profile_id = user_data.get('latedev_profile_id')
                logger.info(f"User {user_id} already has profile_id: {profile_id}")
                return profile_id

            logger.info(f"No existing profile found for user {user_id}, creating new profile via Late.dev API")

            # Create new profile via Late.dev API
            headers = {
                'Authorization': f'Bearer {LateDevOAuthService.API_KEY}',
                'Content-Type': 'application/json'
            }

            # Use user's username or email as profile name
            profile_name = user_data.get('username', f'User {user_id[:8]}') if user_data else f'User {user_id[:8]}'

            response = requests.post(
                f"{LateDevOAuthService.BASE_URL}/profiles",
                headers=headers,
                json={'name': profile_name},
                timeout=10
            )

            logger.info(f"Late.dev profile creation response: {response.status_code}")
            logger.info(f"Response body: {response.text}")

            if response.status_code == 201:
                profile_data = response.json()
                # Late.dev returns profile in 'profile' key with '_id' field
                profile = profile_data.get('profile', {})
                profile_id = profile.get('_id') or profile.get('id')

                # Store profile_id in user's Firebase document
                UserService.update_user(user_id, {
                    'latedev_profile_id': profile_id
                })

                logger.info(f"Created Late.dev profile {profile_id} for user {user_id}")
                return profile_id
            else:
                error_body = response.json() if response.text else {}
                logger.error(f"Failed to create profile: {response.status_code} - {response.text}")

                # Check if it's a profile limit error
                if response.status_code == 403 and 'limit' in response.text.lower():
                    raise Exception(f"Profile limit reached on Late.dev Free plan. Upgrade at https://getlate.dev/dashboard/profiles")

                raise Exception(f"Failed to create Late.dev profile: {response.status_code}")

        except Exception as e:
            logger.error(f"Error getting/creating profile: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def is_connected(user_id, platform='instagram'):
        """
        Check if user has connected their Instagram account via Late.dev

        Args:
            user_id: User's ID
            platform: Social platform

        Returns:
            bool: True if connected
        """
        try:
            account_info = LateDevOAuthService.get_account_info(user_id, platform)
            return account_info is not None

        except Exception as e:
            logger.error(f"Error checking connection: {str(e)}")
            return False

    @staticmethod
    def get_account_info(user_id, platform='instagram'):
        """
        Get connected account info from Late.dev

        Args:
            user_id: User's ID
            platform: Social platform

        Returns:
            dict: Account info or None
        """
        try:
            user_data = UserService.get_user(user_id)
            if not user_data or not user_data.get('latedev_profile_id'):
                return None

            profile_id = user_data.get('latedev_profile_id')

            headers = {
                'Authorization': f'Bearer {LateDevOAuthService.API_KEY}'
            }

            # Map platform to Late.dev API name
            api_platform = LateDevOAuthService._map_platform_name(platform)

            print(f"=== CHECKING ACCOUNT CONNECTION ===")
            print(f"Profile ID: {profile_id}")
            print(f"Platform (internal): {platform}")
            print(f"Platform (API): {api_platform}")

            response = requests.get(
                f"{LateDevOAuthService.BASE_URL}/accounts",
                headers=headers,
                params={'profileId': profile_id},
                timeout=10
            )

            print(f"Accounts API response: {response.status_code}")
            print(f"Response body: {response.text}")

            if response.status_code == 200:
                response_data = response.json()
                accounts = response_data.get('accounts', response_data.get('data', []))
                print(f"Found {len(accounts)} accounts")
                # Find matching account
                for account in accounts:
                    print(f"Account: platform={account.get('platform')}, username={account.get('username')}")
                    if account.get('platform') == api_platform:
                        result = {
                            'username': account.get('username'),
                            'account_id': account.get('_id') or account.get('id'),
                            'profile_picture': account.get('profilePicture')
                        }
                        print(f"Found matching account: {result}")
                        return result

            print("No matching account found")
            return None

        except Exception as e:
            logger.error(f"Error getting account info: {str(e)}")
            return None

    @staticmethod
    def disconnect(user_id, platform='instagram'):
        """
        Disconnect Instagram account from Late.dev

        Args:
            user_id: User's ID
            platform: Social platform

        Returns:
            dict: Result with success status
        """
        try:
            account_info = LateDevOAuthService.get_account_info(user_id, platform)
            if not account_info:
                return {'success': False, 'error': 'Account not connected'}

            account_id = account_info.get('account_id')

            headers = {
                'Authorization': f'Bearer {LateDevOAuthService.API_KEY}'
            }

            logger.info(f"Attempting to disconnect {platform} account {account_id}")

            response = requests.delete(
                f"{LateDevOAuthService.BASE_URL}/accounts/{account_id}",
                headers=headers,
                timeout=10
            )

            logger.info(f"Disconnect response: {response.status_code}")
            logger.info(f"Disconnect response body: {response.text}")

            if response.status_code in [200, 204]:
                logger.info(f"Disconnected {platform} for user {user_id}")
                return {'success': True}
            else:
                logger.error(f"Failed to disconnect: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'Failed to disconnect account: {response.text}'}

        except Exception as e:
            logger.error(f"Error disconnecting account: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def delete_profile(user_id):
        """
        Delete the entire Late.dev profile for a user.
        IMPORTANT: Must disconnect all accounts BEFORE deleting the profile.
        Called when a user downgrades from Premium to Free plan.

        Args:
            user_id: User's ID

        Returns:
            dict: Result with success status
        """
        try:
            # Get user's profile ID from Firebase
            user_data = UserService.get_user(user_id)
            if not user_data or not user_data.get('latedev_profile_id'):
                logger.info(f"No Late.dev profile found for user {user_id}")
                return {'success': True, 'message': 'No profile to delete'}

            profile_id = user_data.get('latedev_profile_id')
            logger.info(f"Deleting Late.dev profile {profile_id} for user {user_id}")

            headers = {
                'Authorization': f'Bearer {LateDevOAuthService.API_KEY}'
            }

            # Step 1: Get all connected accounts for this profile
            try:
                accounts_response = requests.get(
                    f"{LateDevOAuthService.BASE_URL}/accounts",
                    headers=headers,
                    params={'profileId': profile_id},
                    timeout=10
                )

                if accounts_response.status_code == 200:
                    accounts = accounts_response.json().get('accounts', [])
                    logger.info(f"Found {len(accounts)} connected accounts for profile {profile_id}")

                    # Step 2: Disconnect each account
                    for account in accounts:
                        account_id = account.get('id')
                        platform = account.get('platform', 'unknown')
                        try:
                            delete_response = requests.delete(
                                f"{LateDevOAuthService.BASE_URL}/accounts/{account_id}",
                                headers=headers,
                                timeout=10
                            )
                            if delete_response.status_code in [200, 204]:
                                logger.info(f"✅ Disconnected {platform} account {account_id}")
                            else:
                                logger.warning(f"⚠️ Failed to disconnect {platform} account: {delete_response.status_code}")
                        except Exception as e:
                            logger.error(f"Error disconnecting {platform} account: {str(e)}")
                            # Continue with other accounts
                else:
                    logger.warning(f"Could not fetch accounts: {accounts_response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching/disconnecting accounts: {str(e)}")
                # Continue to profile deletion anyway

            # Step 3: Delete the profile (must be done AFTER disconnecting all accounts)
            response = requests.delete(
                f"{LateDevOAuthService.BASE_URL}/profiles/{profile_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 204]:
                # Remove profile ID from Firebase
                UserService.update_user(user_id, {
                    'latedev_profile_id': None
                })
                logger.info(f"✅ Deleted Late.dev profile {profile_id} for user {user_id}")
                return {'success': True, 'message': 'Profile and all accounts deleted successfully'}
            else:
                logger.error(f"Failed to delete profile: {response.status_code} - {response.text}")
                # Even if API call fails, clear the profile ID from Firebase
                UserService.update_user(user_id, {
                    'latedev_profile_id': None
                })
                return {'success': False, 'error': f'Failed to delete profile: {response.status_code}', 'message': 'Profile ID cleared from database'}

        except Exception as e:
            logger.error(f"Error deleting Late.dev profile: {str(e)}")
            # Clear profile ID even on error
            try:
                UserService.update_user(user_id, {
                    'latedev_profile_id': None
                })
            except:
                pass
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_account_id(user_id, platform='instagram'):
        """
        Get Late.dev account ID for a platform

        Args:
            user_id: User's ID
            platform: Social platform

        Returns:
            str: Account ID or None
        """
        account_info = LateDevOAuthService.get_account_info(user_id, platform)
        if account_info:
            return account_info.get('account_id')
        return None
