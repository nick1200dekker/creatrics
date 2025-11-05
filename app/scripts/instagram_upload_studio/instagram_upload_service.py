"""
Instagram Upload Service  
Handles media uploading to Instagram via Late.dev API with scheduling
"""

import os
import requests
import logging
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

logger = logging.getLogger('instagram_upload')


class InstagramUploadService:
    """Service for uploading media to Instagram via Late.dev"""

    BASE_URL = "https://getlate.dev/api/v1"
    API_KEY = os.environ.get('LATEDEV_API_KEY')

    @staticmethod
    def upload_media_from_url(user_id, media_url, caption, schedule_time=None, timezone='UTC'):
        """
        Post to Instagram via Late.dev using a media URL

        Args:
            user_id: User's ID
            media_url: Public URL to media file
            caption: Post caption with hashtags
            schedule_time: ISO 8601 datetime string (optional, None for immediate)
            timezone: Timezone for scheduling

        Returns:
            dict: Result with success status and post info
        """
        try:
            if not InstagramUploadService.API_KEY:
                return {'success': False, 'error': 'Late.dev API key not configured'}

            # Get Instagram account ID from Late.dev
            account_id = LateDevOAuthService.get_account_id(user_id, 'instagram')
            if not account_id:
                return {'success': False, 'error': 'Instagram account not connected'}

            logger.info(f"Starting Instagram post for user {user_id} with media URL")

            # Create post via Late.dev API with media URL
            headers = {
                'Authorization': f'Bearer {InstagramUploadService.API_KEY}',
                'Content-Type': 'application/json'
            }

            # Determine media type from URL extension
            media_type = 'video' if any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi']) else 'image'

            post_data = {
                'platforms': [{
                    'platform': 'instagram',
                    'accountId': account_id
                }],
                'content': caption,
                'mediaItems': [{
                    'type': media_type,
                    'url': media_url
                }]
            }

            # Add scheduling if specified
            if schedule_time:
                post_data['scheduledFor'] = schedule_time
                post_data['timezone'] = timezone
            else:
                post_data['publishNow'] = True

            logger.info(f"Creating Instagram post via Late.dev (media_type: {media_type})")
            response = requests.post(
                f"{InstagramUploadService.BASE_URL}/posts",
                headers=headers,
                json=post_data,
                timeout=120  # 2 minutes timeout
            )

            logger.info(f"Late.dev response status: {response.status_code}")
            logger.info(f"Late.dev response: {response.text}")

            if response.status_code in [200, 201]:
                result = response.json()
                # Late.dev returns post data in 'post' key
                post = result.get('post', {})
                post_id = post.get('_id') or post.get('id') or result.get('_id') or result.get('id')

                status_message = 'Post scheduled successfully' if schedule_time else 'Post published successfully'

                logger.info(f"Instagram post created: {post_id}")
                return {
                    'success': True,
                    'post_id': post_id,
                    'message': status_message,
                    'scheduled_for': schedule_time
                }
            else:
                error_msg = response.text
                logger.error(f"Failed to create post: {response.status_code} - {error_msg}")
                return {'success': False, 'error': f'Failed to create post: {error_msg}'}

        except Exception as e:
            logger.error(f"Error in Instagram post: {str(e)}")
            return {'success': False, 'error': str(e)}
