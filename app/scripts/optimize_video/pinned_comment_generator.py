"""
Pinned Comment Generator Module
Generates and posts engaging pinned comments to YouTube videos using AI
"""
import logging
from typing import Dict, Any, Tuple, Optional
from app.system.ai_provider.ai_provider import get_ai_provider
from app.scripts.optimize_video.prompts import load_prompt

logger = logging.getLogger(__name__)


class PinnedCommentGenerator:
    """Generates engaging pinned comments for YouTube videos using AI"""

    def __init__(self, video_optimizer_instance=None):
        """
        Initialize with optional reference to VideoOptimizer for accessing helper methods

        Args:
            video_optimizer_instance: Reference to VideoOptimizer instance to access _fetch_video_info, etc.
        """
        self.video_optimizer = video_optimizer_instance

    def generate_and_post_pinned_comment(self, video_id: str, user_id: str, video_title: str = None,
                                        target_keyword: str = None, user_subscription: str = None,
                                        preview_only: bool = True) -> Dict[str, Any]:
        """
        Generate an engaging pinned comment and optionally post it to the video

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication and credits
            video_title: Optional video title for context
            target_keyword: Optional target keyword for SEO
            user_subscription: User's subscription plan for AI provider selection
            preview_only: If True, only generate comment without posting (default: True)

        Returns:
            Dict with success status and comment text
        """
        try:
            from app.utils.youtube_client import get_user_youtube_client

            # Get authenticated YouTube client
            youtube = get_user_youtube_client(user_id)
            if not youtube:
                return {
                    'success': False,
                    'error': 'YouTube account not connected',
                    'error_type': 'no_youtube_connection'
                }

            # Get video info if title not provided
            if not video_title and self.video_optimizer:
                video_info = self.video_optimizer._fetch_video_info(video_id)
                if not video_info:
                    video_info = self.video_optimizer._fetch_video_info_youtube_api(video_id, user_id)

                video_title = video_info.get('title', '') if video_info else ''

            # Get transcript for context (use cached VTT data)
            transcript_text = ''
            if self.video_optimizer:
                vtt_data = self.video_optimizer._fetch_and_cache_vtt(video_id, user_id)
                transcript_text = vtt_data.get('plain_text', '')

            # Generate engaging pinned comment
            logger.info(f"Generating pinned comment for video {video_id}")
            comment_text, token_usage = self._generate_pinned_comment_text(
                video_title,
                transcript_text[:1000] if transcript_text else '',
                target_keyword,
                user_id,
                user_subscription
            )

            if not comment_text:
                return {
                    'success': False,
                    'error': 'Failed to generate comment text'
                }

            # If preview_only, return the comment without posting
            if preview_only:
                logger.info(f"Preview mode: Returning pinned comment without posting")
                return {
                    'success': True,
                    'preview': True,
                    'message': 'Pinned comment generated (preview mode)',
                    'comment_text': comment_text,
                    'quota_used': 0,  # No quota used for preview
                    'token_usage': token_usage  # For credit deduction
                }

            # Check video privacy status before posting - private videos don't support comments
            try:
                video_response = youtube.videos().list(
                    part='status',
                    id=video_id
                ).execute()

                if video_response.get('items'):
                    privacy_status = video_response['items'][0]['status'].get('privacyStatus', 'private')

                    if privacy_status == 'private':
                        logger.info(f"Video {video_id} is private - comment generated but cannot be posted yet")
                        return {
                            'success': True,
                            'preview': True,
                            'is_private': True,
                            'message': 'Comment generated! Note: Your video is currently private. You can apply this comment after publishing your video.',
                            'comment_text': comment_text,
                            'quota_used': 0,  # No quota used since we didn't post
                            'token_usage': token_usage  # For credit deduction
                        }
            except Exception as e:
                logger.warning(f"Could not check video privacy status: {e}")

            # Otherwise, post comment to YouTube (50 units)
            logger.info(f"Posting pinned comment to YouTube...")
            comment_response = youtube.commentThreads().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'topLevelComment': {
                            'snippet': {
                                'textOriginal': comment_text
                            }
                        }
                    }
                }
            ).execute()

            comment_id = comment_response['id']
            logger.info(f"Posted comment {comment_id} to video {video_id}")

            # Set as pinned comment - this is done by updating the comment's moderationStatus
            # Note: Pinning is done via the YouTube Studio UI, not directly via API
            # The API only allows setting moderation status
            # So we'll just return success and instruct user to pin manually if needed

            return {
                'success': True,
                'preview': False,
                'message': 'Comment posted successfully',
                'comment_text': comment_text,
                'comment_id': comment_id,
                'note': 'Pin this comment in YouTube Studio for best results',
                'quota_used': 50,
                'token_usage': token_usage  # For credit deduction
            }

        except Exception as e:
            logger.error(f"Error posting pinned comment for video {video_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def apply_pinned_comment(self, video_id: str, user_id: str, comment_text: str) -> Dict[str, Any]:
        """
        Post a previously generated pinned comment to YouTube

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication
            comment_text: The comment text to post

        Returns:
            Dict with success status and details
        """
        try:
            from app.utils.youtube_client import get_user_youtube_client

            # Get authenticated YouTube client
            youtube = get_user_youtube_client(user_id)
            if not youtube:
                return {
                    'success': False,
                    'error': 'YouTube account not connected',
                    'error_type': 'no_youtube_connection'
                }

            # Check video privacy status - private videos don't support comments
            try:
                video_response = youtube.videos().list(
                    part='status',
                    id=video_id
                ).execute()

                if video_response.get('items'):
                    privacy_status = video_response['items'][0]['status'].get('privacyStatus', 'private')

                    if privacy_status == 'private':
                        return {
                            'success': False,
                            'error': 'Your video is currently private. Please change it to unlisted or public before applying the pinned comment.',
                            'error_type': 'private_video'
                        }
            except Exception as e:
                logger.warning(f"Could not check video privacy status: {e}")

            # Post comment to YouTube (50 units)
            logger.info(f"Posting pinned comment to video {video_id}")
            comment_response = youtube.commentThreads().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'topLevelComment': {
                            'snippet': {
                                'textOriginal': comment_text
                            }
                        }
                    }
                }
            ).execute()

            comment_id = comment_response['id']
            logger.info(f"Posted comment {comment_id} to video {video_id}")

            return {
                'success': True,
                'message': 'Comment posted successfully',
                'comment_id': comment_id,
                'note': 'Pin this comment in YouTube Studio for best results',
                'quota_used': 50
            }

        except Exception as e:
            logger.error(f"Error posting comment to video {video_id}: {e}")

            # Check for YouTube quota exceeded error
            error_str = str(e)
            if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
                return {
                    'success': False,
                    'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                    'error_type': 'quota_exceeded'
                }

            return {
                'success': False,
                'error': str(e)
            }

    def _generate_pinned_comment_text(self, video_title: str, transcript_preview: str,
                                     target_keyword: str, user_id: str,
                                     user_subscription: str = None) -> Tuple[Optional[str], Optional[Dict]]:
        """Use AI to generate engaging pinned comment. Returns (comment_text, token_usage)"""
        try:
            ai_provider = get_ai_provider(
                script_name='optimize_video/pinned_comment_generator',
                user_subscription=user_subscription
            )
            if not ai_provider:
                logger.error("AI provider not available for comment generation")
                return None, None

            keyword_context = f"{target_keyword}" if target_keyword else ""

            system_prompt_template = load_prompt('pinned_comment_system.txt')
            user_prompt_template = load_prompt('pinned_comment_user.txt')

            system_prompt = system_prompt_template
            user_prompt = user_prompt_template.format(
                video_title=video_title,
                target_keyword=keyword_context,
                transcript_preview=transcript_preview
            )

            # ASYNC AI call - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.8,
                    max_tokens=7000
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

            comment_text = response.get('content', '') if isinstance(response, dict) else str(response)

            # Remove quotes if AI wrapped the comment
            comment_text = comment_text.strip().strip('"\'')

            # Get token usage (don't deduct here - will be handled centrally)
            usage = response.get('usage', {})
            provider_enum = response.get('provider_enum')
            token_usage = {
                'model': response.get('model', None),
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'provider_enum': provider_enum.value if provider_enum else None
            }

            return comment_text, token_usage

        except Exception as e:
            logger.error(f"Error generating pinned comment text: {e}")
            return None, None
