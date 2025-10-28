"""
TikTok Upload Service
Handles video uploading to TikTok via Content Posting API
"""

import os
import requests
import logging
from app.scripts.tiktok_upload_studio.tiktok_oauth_service import TikTokOAuthService

logger = logging.getLogger('tiktok_upload')


class TikTokUploadService:
    """Service for uploading videos to TikTok"""

    BASE_URL = "https://open.tiktokapis.com/v2/post/publish/inbox"

    @staticmethod
    def upload_video(user_id, video_path, title, privacy_level='SELF_ONLY'):
        """
        Upload video to TikTok

        Args:
            user_id: User's ID
            video_path: Path to video file
            title: Video caption/title
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY, or FOLLOWER_OF_CREATOR

        Returns:
            dict: Result with success status and publish info
        """
        try:
            # Get access token
            access_token = TikTokOAuthService.get_access_token(user_id)
            if not access_token:
                return {'success': False, 'error': 'Not connected to TikTok'}

            # Get video file size
            file_size = os.path.getsize(video_path)

            logger.info(f"Initiating TikTok upload for user {user_id}, file size: {file_size} bytes")

            # Step 1: Initialize upload
            init_url = f"{TikTokUploadService.BASE_URL}/video/init/"

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }

            init_data = {
                'post_info': {
                    'title': title,
                    'privacy_level': privacy_level,
                    'disable_duet': False,
                    'disable_comment': False,
                    'disable_stitch': False,
                    'video_cover_timestamp_ms': 1000
                },
                'source_info': {
                    'source': 'FILE_UPLOAD',
                    'video_size': file_size,
                    'chunk_size': file_size,
                    'total_chunk_count': 1
                }
            }

            logger.info(f"Sending init request to TikTok")
            init_response = requests.post(init_url, json=init_data, headers=headers, timeout=30)

            # Log response for debugging
            logger.info(f"Init response status: {init_response.status_code}")
            logger.info(f"Init response body: {init_response.text}")

            init_response.raise_for_status()
            init_result = init_response.json()

            # Check for errors in response
            if 'error' in init_result:
                error_code = init_result['error'].get('code', 'unknown')
                # TikTok returns error.code='ok' for successful requests
                if error_code != 'ok':
                    error_msg = init_result['error'].get('message', 'Unknown error')
                    logger.error(f"TikTok init error - code: {error_code}, message: {error_msg}")
                    return {'success': False, 'error': f"{error_code}: {error_msg}"}

            # Check if data exists
            if 'data' not in init_result:
                logger.error(f"No data in init response: {init_result}")
                return {'success': False, 'error': 'Invalid response from TikTok'}

            upload_url = init_result['data'].get('upload_url')
            publish_id = init_result['data'].get('publish_id')

            if not upload_url or not publish_id:
                logger.error(f"Missing upload_url or publish_id in response: {init_result}")
                return {'success': False, 'error': 'Invalid upload response from TikTok'}

            logger.info(f"Got upload URL, publish_id: {publish_id}")

            # Step 2: Upload video file
            logger.info(f"Uploading video file ({file_size} bytes)")

            with open(video_path, 'rb') as video_file:
                upload_headers = {
                    'Content-Type': 'video/mp4',
                    'Content-Range': f'bytes 0-{file_size-1}/{file_size}',
                    'Content-Length': str(file_size)
                }

                upload_response = requests.put(
                    upload_url,
                    data=video_file,
                    headers=upload_headers,
                    timeout=300  # 5 minutes for large files
                )

                logger.info(f"Upload response status: {upload_response.status_code}")

                upload_response.raise_for_status()

            logger.info(f"Video file uploaded successfully")

            # Step 3: Check publish status
            status_url = f"{TikTokUploadService.BASE_URL}/status/fetch/"

            status_data = {
                'publish_id': publish_id
            }

            status_response = requests.post(status_url, json=status_data, headers=headers, timeout=30)
            status_response.raise_for_status()
            status_result = status_response.json()

            logger.info(f"Publish status: {status_result}")

            # Get detailed status
            status_data_obj = status_result.get('data', {})
            publish_status = status_data_obj.get('status', 'UNKNOWN')
            fail_reason = status_data_obj.get('fail_reason')

            logger.info(f"Video publish status: {publish_status}, fail_reason: {fail_reason}")

            return {
                'success': True,
                'publish_id': publish_id,
                'status': publish_status,
                'fail_reason': fail_reason,
                'message': f'Video uploaded to TikTok! Status: {publish_status}. Check your TikTok profile (may take a few moments to appear).'
            }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout uploading to TikTok")
            return {'success': False, 'error': 'Upload timeout - video may be too large'}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error uploading to TikTok: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    return {'success': False, 'error': error_msg}
                except:
                    pass
            return {'success': False, 'error': f'Upload failed: {str(e)}'}
        except Exception as e:
            logger.error(f"Unexpected error uploading to TikTok: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @staticmethod
    def check_publish_status(user_id, publish_id):
        """
        Check the status of a published video

        Args:
            user_id: User's ID
            publish_id: Publish ID from upload

        Returns:
            dict: Status result
        """
        try:
            access_token = TikTokOAuthService.get_access_token(user_id)
            if not access_token:
                return {'success': False, 'error': 'Not connected to TikTok'}

            status_url = f"{TikTokUploadService.BASE_URL}/status/fetch/"

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            status_data = {
                'publish_id': publish_id
            }

            response = requests.post(status_url, json=status_data, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()

            if 'error' in result:
                error_code = result['error'].get('code', 'unknown')
                if error_code != 'ok':
                    return {'success': False, 'error': result['error'].get('message')}

            status_data = result.get('data', {})

            return {
                'success': True,
                'status': status_data.get('status'),
                'fail_reason': status_data.get('fail_reason'),
                'publicize_status': status_data.get('publicize_status')
            }

        except Exception as e:
            logger.error(f"Error checking publish status: {str(e)}")
            return {'success': False, 'error': str(e)}
