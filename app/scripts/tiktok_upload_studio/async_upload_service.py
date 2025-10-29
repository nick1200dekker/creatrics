"""
TikTok Async Upload Service
Handles video uploading to TikTok with streaming (no disk storage) and background threading
"""

import requests
import logging
import time
import threading
import io
from werkzeug.datastructures import FileStorage
from app.scripts.tiktok_upload_studio.tiktok_oauth_service import TikTokOAuthService
from app.scripts.tiktok_upload_studio.upload_tracker import UploadTracker

logger = logging.getLogger('tiktok_async_upload')


class TikTokAsyncUploadService:
    """Service for async video uploading to TikTok with streaming"""

    BASE_URL = "https://open.tiktokapis.com/v2/post/publish"

    @staticmethod
    def start_upload(user_id, video_file: FileStorage, title, privacy_level='SELF_ONLY', mode='direct'):
        """
        Start async video upload (returns immediately)

        Args:
            user_id: User's ID
            video_file: Flask FileStorage object (from request.files)
            title: Video caption/title
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY, or FOLLOWER_OF_CREATOR
            mode: 'direct' for direct post, 'inbox' for creator upload

        Returns:
            dict: Result with upload_id and success status
        """
        try:
            # Get file info
            filename = video_file.filename
            video_file.seek(0, io.SEEK_END)
            file_size = video_file.tell()
            video_file.seek(0)  # Reset to beginning

            logger.info(f"Starting async upload for user {user_id}: {filename} ({file_size} bytes)")

            # Create upload tracking record
            upload_id = UploadTracker.create_upload(
                user_id=user_id,
                filename=filename,
                file_size=file_size,
                title=title,
                privacy_level=privacy_level,
                mode=mode
            )

            if not upload_id:
                return {'success': False, 'error': 'Failed to create upload tracking'}

            # Read video data into memory (BytesIO)
            # This is safe because we do it in the request context, then pass to thread
            video_data = video_file.read()
            logger.info(f"Read {len(video_data)} bytes into memory for upload {upload_id}")

            # Start background thread
            thread = threading.Thread(
                target=TikTokAsyncUploadService._upload_worker,
                args=(upload_id, user_id, video_data, file_size, title, privacy_level, mode),
                daemon=True
            )
            thread.start()

            logger.info(f"Started background upload thread for upload {upload_id}")

            return {
                'success': True,
                'upload_id': upload_id,
                'message': 'Upload started'
            }

        except Exception as e:
            logger.error(f"Error starting async upload: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _upload_worker(upload_id, user_id, video_data, file_size, title, privacy_level, mode):
        """
        Background worker that uploads video to TikTok

        Args:
            upload_id: Upload tracking ID
            user_id: User's ID
            video_data: Video file data (bytes)
            file_size: File size in bytes
            title: Video caption/title
            privacy_level: Privacy level
            mode: Upload mode (direct/inbox)
        """
        try:
            logger.info(f"Upload worker started for {upload_id}")

            # Update status to uploading
            UploadTracker.update_status(upload_id, 'initializing', progress=5)

            # Get access token
            access_token = TikTokOAuthService.get_access_token(user_id)
            if not access_token:
                UploadTracker.update_status(upload_id, 'failed', error='Not connected to TikTok')
                return

            # Determine endpoint based on mode
            if mode == 'inbox':
                init_url = f"{TikTokAsyncUploadService.BASE_URL}/inbox/video/init/"
                logger.info(f"Initiating TikTok inbox upload for {upload_id}")
            else:
                init_url = f"{TikTokAsyncUploadService.BASE_URL}/video/init/"
                logger.info(f"Initiating TikTok direct post for {upload_id}")

            # Step 1: Initialize upload
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

            UploadTracker.update_status(upload_id, 'initializing', progress=10)

            init_response = requests.post(init_url, json=init_data, headers=headers, timeout=30)
            logger.info(f"Init response status: {init_response.status_code}")

            init_response.raise_for_status()
            init_result = init_response.json()

            # Check for errors
            if 'error' in init_result:
                error_code = init_result['error'].get('code', 'unknown')
                if error_code != 'ok':
                    error_msg = init_result['error'].get('message', 'Unknown error')
                    logger.error(f"TikTok init error - {error_code}: {error_msg}")
                    UploadTracker.update_status(upload_id, 'failed', error=f"{error_code}: {error_msg}")
                    return

            if 'data' not in init_result:
                logger.error(f"No data in init response")
                UploadTracker.update_status(upload_id, 'failed', error='Invalid response from TikTok')
                return

            upload_url = init_result['data'].get('upload_url')
            publish_id = init_result['data'].get('publish_id')

            if not upload_url or not publish_id:
                logger.error(f"Missing upload_url or publish_id")
                UploadTracker.update_status(upload_id, 'failed', error='Invalid upload response from TikTok')
                return

            logger.info(f"Got upload URL, publish_id: {publish_id}")
            UploadTracker.update_status(upload_id, 'uploading', progress=20, publish_id=publish_id)

            # Step 2: Upload video file (streaming from memory)
            logger.info(f"Uploading video file ({file_size} bytes)")

            upload_headers = {
                'Content-Type': 'video/mp4',
                'Content-Range': f'bytes 0-{file_size-1}/{file_size}',
                'Content-Length': str(file_size)
            }

            # Stream upload with BytesIO
            video_stream = io.BytesIO(video_data)

            upload_response = requests.put(
                upload_url,
                data=video_stream,
                headers=upload_headers,
                timeout=600  # 10 minutes for large files
            )

            logger.info(f"Upload response status: {upload_response.status_code}")
            upload_response.raise_for_status()

            logger.info(f"Video file uploaded successfully")
            UploadTracker.update_status(upload_id, 'processing', progress=60)

            # Step 3: Poll publish status
            status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
            status_data = {
                'publish_id': publish_id
            }

            max_attempts = 30  # Poll for up to 5 minutes
            attempt = 0
            publish_status = 'PROCESSING_UPLOAD'

            while attempt < max_attempts:
                attempt += 1

                logger.info(f"Checking publish status (attempt {attempt}/{max_attempts})")

                status_response = requests.post(status_url, json=status_data, headers=headers, timeout=30)
                status_response.raise_for_status()
                status_result = status_response.json()

                status_data_obj = status_result.get('data', {})
                publish_status = status_data_obj.get('status', 'UNKNOWN')
                fail_reason = status_data_obj.get('fail_reason')

                logger.info(f"Video publish status: {publish_status}")

                # Update progress based on status
                progress = 60 + (attempt * 1)  # Increment slowly from 60 to 90

                # Check for completion based on mode
                is_complete = False
                if mode == 'inbox' and publish_status == 'SEND_TO_USER_INBOX':
                    # Inbox uploads are complete when sent to inbox
                    is_complete = True
                    message = 'Video uploaded to TikTok inbox! Check your TikTok app to complete the post.'
                elif mode == 'direct' and publish_status == 'PUBLISH_COMPLETE':
                    # Direct posts are complete when published
                    is_complete = True
                    message = 'Video published to TikTok successfully!'

                if is_complete:
                    UploadTracker.update_status(
                        upload_id,
                        'completed',
                        progress=100,
                        message=message
                    )
                    logger.info(f"Upload {upload_id} completed successfully (status: {publish_status})")
                    return

                elif publish_status == 'FAILED':
                    error_msg = f'TikTok publish failed: {fail_reason or "Unknown error"}'
                    logger.error(error_msg)
                    UploadTracker.update_status(upload_id, 'failed', error=error_msg)
                    return

                # Still processing
                UploadTracker.update_status(upload_id, 'processing', progress=min(progress, 90))

                if attempt < max_attempts:
                    time.sleep(10)

            # Timeout reached but upload likely succeeded
            logger.warning(f"Publish status check timeout. Last status: {publish_status}")

            if mode == 'inbox':
                message = 'Video uploaded to TikTok inbox. Check your TikTok app to complete the post.'
            else:
                message = 'Video uploaded to TikTok and is still processing. Check your TikTok profile shortly.'

            UploadTracker.update_status(
                upload_id,
                'completed',
                progress=100,
                message=message
            )

        except requests.exceptions.Timeout:
            logger.error(f"Timeout uploading {upload_id}")
            UploadTracker.update_status(upload_id, 'failed', error='Upload timeout - video may be too large')

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error uploading {upload_id}: {str(e)}")
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                except:
                    pass
            UploadTracker.update_status(upload_id, 'failed', error=f'Upload failed: {error_msg}')

        except Exception as e:
            logger.error(f"Unexpected error uploading {upload_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            UploadTracker.update_status(upload_id, 'failed', error=str(e))

    @staticmethod
    def get_upload_status(upload_id):
        """
        Get upload status

        Args:
            upload_id: Upload ID

        Returns:
            dict: Upload status
        """
        return UploadTracker.get_upload(upload_id)
