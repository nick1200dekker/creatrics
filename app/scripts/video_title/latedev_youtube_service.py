"""
YouTube Upload Service via Late.dev API
Handles YouTube video uploading through Late.dev
"""

import os
import requests
import logging
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

logger = logging.getLogger('youtube_latedev')


class YouTubeLateDevService:
    """Service for uploading videos to YouTube via Late.dev"""

    BASE_URL = "https://getlate.dev/api/v1"
    API_KEY = os.environ.get('LATEDEV_API_KEY')

    @staticmethod
    def upload_video(user_id, media_url, title, description='', tags=None, visibility='private',
                    thumbnail_url=None, schedule_time=None, timezone='UTC', first_comment=None):
        """
        Post to YouTube via Late.dev using a media URL

        Args:
            user_id: User's ID
            media_url: Public URL to video file
            title: Video title
            description: Video description
            tags: List of tags
            visibility: 'public', 'unlisted', or 'private'
            thumbnail_url: Optional custom thumbnail URL
            schedule_time: ISO 8601 datetime string (optional, None for immediate)
            timezone: Timezone for scheduling
            first_comment: Optional first comment to post

        Returns:
            dict: Result with success status and post info
        """
        try:
            if not YouTubeLateDevService.API_KEY:
                return {'success': False, 'error': 'Late.dev API key not configured'}

            # Get YouTube account ID from Late.dev
            account_id = LateDevOAuthService.get_account_id(user_id, 'youtube')
            if not account_id:
                return {'success': False, 'error': 'YouTube account not connected'}

            logger.info(f"Starting YouTube post for user {user_id} with media URL")

            # Create post via Late.dev API
            headers = {
                'Authorization': f'Bearer {YouTubeLateDevService.API_KEY}',
                'Content-Type': 'application/json'
            }

            # Prepare media items
            media_item = {
                'type': 'video',
                'url': media_url
            }

            # Add thumbnail if provided
            if thumbnail_url:
                media_item['thumbnail'] = thumbnail_url

            # Prepare platform-specific data
            platform_data = {
                'title': title,
                'visibility': visibility
            }

            if first_comment:
                platform_data['firstComment'] = first_comment

            post_data = {
                'platforms': [{
                    'platform': 'youtube',
                    'accountId': account_id,
                    'platformSpecificData': platform_data
                }],
                'content': description,
                'mediaItems': [media_item]
            }

            # Add tags if provided
            if tags:
                post_data['tags'] = tags if isinstance(tags, list) else [tags]

            # Handle scheduling
            if schedule_time:
                # Scheduled posts are uploaded as private first, then published at scheduled time
                post_data['scheduledFor'] = schedule_time
                post_data['timezone'] = timezone
                post_data['isDraft'] = False
                logger.info(f"Scheduling YouTube video for {schedule_time} ({timezone})")
            else:
                # Immediate post
                post_data['publishNow'] = True
                logger.info(f"Publishing YouTube video immediately with visibility: {visibility}")

            logger.info(f"Creating YouTube post via Late.dev")
            response = requests.post(
                f"{YouTubeLateDevService.BASE_URL}/posts",
                headers=headers,
                json=post_data,
                timeout=120
            )

            logger.info(f"Late.dev response status: {response.status_code}")
            logger.info(f"Late.dev response: {response.text}")

            if response.status_code in [200, 201, 207]:
                result = response.json()

                # Check for platform-specific errors (207 multi-status)
                if response.status_code == 207:
                    platform_results = result.get('platformResults', [])
                    for platform_result in platform_results:
                        if platform_result.get('platform') == 'youtube' and platform_result.get('status') == 'failed':
                            error = platform_result.get('error', '')
                            logger.error(f"YouTube platform error: {error}")
                            # Check for quota error
                            if 'quota exceeded' in error.lower():
                                return {'success': False, 'error': 'YouTube API quota exceeded. Please try again tomorrow.'}
                            return {'success': False, 'error': error}

                post = result.get('post', {})
                post_id = post.get('_id') or post.get('id') or result.get('_id') or result.get('id')

                if schedule_time:
                    status_message = 'Video scheduled successfully on YouTube'
                else:
                    status_message = 'Video uploaded to YouTube successfully'

                logger.info(f"YouTube post created: {post_id}")
                return {
                    'success': True,
                    'post_id': post_id,
                    'message': status_message,
                    'scheduled_for': schedule_time if schedule_time else None
                }
            else:
                error_msg = response.text
                logger.error(f"Failed to create YouTube post: {response.status_code} - {error_msg}")
                return {'success': False, 'error': f'Failed to create post: {error_msg}'}

        except Exception as e:
            logger.error(f"Error in YouTube post: {str(e)}")
            return {'success': False, 'error': str(e)}
