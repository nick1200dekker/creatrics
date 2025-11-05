"""
TikTok Upload Service via Late.dev API
Handles TikTok OAuth and video uploading through Late.dev
Reuses the same Late.dev profile as Instagram
"""

import os
import requests
import logging
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService

logger = logging.getLogger('tiktok_latedev')


class TikTokLateDevService:
    """Service for uploading videos to TikTok via Late.dev"""

    BASE_URL = "https://getlate.dev/api/v1"
    API_KEY = os.environ.get('LATEDEV_API_KEY')

    @staticmethod
    def upload_video(user_id, media_url, title, mode='direct', privacy_level='PUBLIC_TO_EVERYONE', schedule_time=None, timezone='UTC'):
        """
        Post to TikTok via Late.dev using a media URL

        Args:
            user_id: User's ID
            media_url: Public URL to video file
            title: Video title/caption
            mode: 'direct' for direct post, 'inbox' for creator inbox, 'scheduled' for scheduled post
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, SELF_ONLY
            schedule_time: ISO 8601 datetime string (optional, None for immediate)
            timezone: Timezone for scheduling

        Returns:
            dict: Result with success status and post info
        """
        try:
            if not TikTokLateDevService.API_KEY:
                return {'success': False, 'error': 'Late.dev API key not configured'}

            # Get TikTok account ID from Late.dev
            account_id = LateDevOAuthService.get_account_id(user_id, 'tiktok')
            if not account_id:
                return {'success': False, 'error': 'TikTok account not connected'}

            logger.info(f"Starting TikTok post for user {user_id} with media URL (mode: {mode})")

            # Create post via Late.dev API
            headers = {
                'Authorization': f'Bearer {TikTokLateDevService.API_KEY}',
                'Content-Type': 'application/json'
            }

            post_data = {
                'platforms': [{
                    'platform': 'tiktok',
                    'accountId': account_id,
                    'platformSpecificData': {
                        'tiktokSettings': {
                            'privacy_level': privacy_level,
                            'disable_duet': False,
                            'disable_comment': False,
                            'disable_stitch': False,
                            'video_cover_timestamp_ms': 1000
                        }
                    }
                }],
                'content': title,
                'mediaItems': [{
                    'type': 'video',
                    'url': media_url
                }]
            }

            # Handle different modes
            if mode == 'inbox':
                # For inbox mode, set as draft (TikTok will send to creator inbox)
                post_data['isDraft'] = True
            elif mode == 'scheduled' and schedule_time:
                # For scheduled mode, set schedule time
                post_data['scheduledFor'] = schedule_time
                post_data['timezone'] = timezone
                post_data['isDraft'] = False
            else:
                # For direct post, publish immediately
                post_data['publishNow'] = True

            logger.info(f"Creating TikTok post via Late.dev (mode: {mode})")
            response = requests.post(
                f"{TikTokLateDevService.BASE_URL}/posts",
                headers=headers,
                json=post_data,
                timeout=120
            )

            logger.info(f"Late.dev response status: {response.status_code}")
            logger.info(f"Late.dev response: {response.text}")

            if response.status_code in [200, 201]:
                result = response.json()
                post = result.get('post', {})
                post_id = post.get('_id') or post.get('id') or result.get('_id') or result.get('id')

                if mode == 'inbox':
                    status_message = 'Video sent to TikTok inbox successfully'
                elif mode == 'scheduled':
                    status_message = 'Video scheduled successfully'
                else:
                    status_message = 'Video posted to TikTok successfully'

                logger.info(f"TikTok post created: {post_id}")
                return {
                    'success': True,
                    'post_id': post_id,
                    'message': status_message,
                    'scheduled_for': schedule_time if mode == 'scheduled' else None
                }
            else:
                error_msg = response.text
                logger.error(f"Failed to create TikTok post: {response.status_code} - {error_msg}")
                return {'success': False, 'error': f'Failed to create post: {error_msg}'}

        except Exception as e:
            logger.error(f"Error in TikTok post: {str(e)}")
            return {'success': False, 'error': str(e)}
