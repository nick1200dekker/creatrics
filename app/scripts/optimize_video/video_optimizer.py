"""
Video Optimizer
Optimizes user's own YouTube videos with AI recommendations
"""
import os
import logging
from pathlib import Path
import requests
from typing import Dict, Any
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
from app.scripts.video_title.video_description import VideoDescriptionGenerator
from app.scripts.video_title.video_tags import VideoTagsGenerator
from app.scripts.optimize_video.caption_correction import CaptionCorrector
from app.scripts.optimize_video.pinned_comment_generator import PinnedCommentGenerator
from app.scripts.optimize_video.prompts import load_prompt

logger = logging.getLogger(__name__)

class VideoOptimizer:
    """Optimizes user's videos with AI recommendations"""

    def __init__(self):
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.rapidapi_host = "yt-api.p.rapidapi.com"
        self.title_generator = VideoTitleGenerator()
        self.description_generator = VideoDescriptionGenerator()
        self.tags_generator = VideoTagsGenerator()
        self.caption_corrector = CaptionCorrector()
        self.pinned_comment_generator = PinnedCommentGenerator(video_optimizer_instance=self)

    def get_video_info(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """
        Fetch basic video information without optimizing

        Args:
            video_id: YouTube video ID
            user_id: User ID for YouTube API access if needed

        Returns:
            Dict with video information (title, thumbnail, views, published_time, etc.)
        """
        try:
            # Fetch video info - try RapidAPI first, fallback to YouTube API for private videos
            video_info = self._fetch_video_info(video_id)

            # Check if video_info has required fields (RapidAPI returns incomplete data for private videos)
            has_required_fields = video_info and video_info.get('title') and video_info.get('lengthSeconds')

            if not has_required_fields:
                # Try YouTube API for private/unlisted videos
                logger.info(f"RapidAPI returned incomplete data for {video_id}, trying YouTube API for private video")
                video_info = self._fetch_video_info_youtube_api(video_id, user_id)
                if not video_info or not video_info.get('title'):
                    return None

            # Return normalized video info
            return {
                'title': video_info.get('title', ''),
                'thumbnail': video_info.get('thumbnail', [{}])[0].get('url', '') if video_info.get('thumbnail') else '',
                'view_count': video_info.get('viewCount', '0'),
                'published_time': video_info.get('publishDate', ''),
                'video_id': video_id
            }

        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
            return None

    def optimize_video(self, video_id: str, user_id: str, user_subscription: str = None, selected_optimizations: list = None) -> Dict[str, Any]:
        """
        Optimize a video with AI-powered recommendations

        Args:
            video_id: YouTube video ID
            user_id: User ID for credit deduction
            user_subscription: User's subscription plan for AI provider selection
            selected_optimizations: List of optimizations to run (e.g., ['title', 'description', 'tags', 'captions', 'pinned_comment'])

        Returns:
            Dict with optimization results
        """
        # Default to basic optimizations if not specified
        if selected_optimizations is None:
            selected_optimizations = ['title', 'description', 'tags']

        logger.info(f"Running optimizations: {selected_optimizations}")
        try:
            # Fetch video info - try RapidAPI first, fallback to YouTube API for private videos
            video_info = self._fetch_video_info(video_id)

            # Check if video_info has required fields (RapidAPI returns incomplete data for private videos)
            has_required_fields = video_info and video_info.get('title') and video_info.get('lengthSeconds')

            if not has_required_fields:
                # Try YouTube API for private/unlisted videos
                logger.info(f"RapidAPI returned incomplete data for {video_id}, trying YouTube API for private video")
                video_info = self._fetch_video_info_youtube_api(video_id, user_id)
                if not video_info or not video_info.get('title'):
                    return {'success': False, 'error': 'Failed to fetch video information'}

            # Fetch and parse VTT (downloads once, caches, returns all 3 formats)
            vtt_data = self._fetch_and_cache_vtt(video_id, user_id)

            # Check if transcript is available - REQUIRED for optimization
            if not vtt_data['plain_text'] or vtt_data['plain_text'].strip() == "":
                return {
                    'success': False,
                    'error': 'Transcript not available yet',
                    'error_type': 'transcript_unavailable',
                    'message': 'YouTube typically generates transcripts 15-30 minutes after upload. Please try again later.'
                }

            # Extract the 3 formats
            plain_text = vtt_data['plain_text']  # For title/tags
            segments_with_time = vtt_data['segments_with_time']  # For description/chapters
            per_word = vtt_data['per_word']  # For captions

            logger.info("=" * 80)
            logger.info("VTT DATA DISTRIBUTION FOR OPTIMIZATION:")
            logger.info("=" * 80)
            logger.info(f"✓ TITLE/TAGS will receive: Plain text ({len(plain_text)} chars)")
            logger.info(f"✓ DESCRIPTION will receive: Segments with timestamps ({len(segments_with_time)} segments)")
            logger.info(f"✓ CAPTIONS will receive: Per-word timestamps ({len(per_word)} words)")
            logger.info(f"✓ Selected optimizations: {selected_optimizations}")
            logger.info("=" * 80)

            # Check if video was uploaded via Upload Studio and has stored metadata
            from app.system.services.firebase_service import db

            target_keyword = None
            stored_thumbnail = None

            try:
                uploaded_video_ref = db.collection('users').document(user_id).collection('uploaded_videos').document(video_id)
                uploaded_video_doc = uploaded_video_ref.get()

                if uploaded_video_doc.exists:
                    video_metadata = uploaded_video_doc.to_dict()
                    target_keyword = video_metadata.get('target_keyword')
                    stored_thumbnail = video_metadata.get('thumbnail_url')

                    if target_keyword:
                        logger.info(f"Using stored target keyword from Upload Studio: {target_keyword}")
                    if stored_thumbnail:
                        logger.info(f"Using stored thumbnail URL from Upload Studio")
            except Exception as e:
                logger.warning(f"Could not retrieve stored video metadata: {e}")

            # Get current metadata
            current_title = video_info.get('title', '')
            current_description = video_info.get('description', '')
            current_tags = video_info.get('keywords', [])

            # Get thumbnail URL - prefer stored thumbnail from Upload Studio, then API, then default
            thumbnail_url = stored_thumbnail or video_info.get('thumbnail_url', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg")

            # Detect if video is a short (under 60 seconds)
            video_duration = int(video_info.get('lengthSeconds', 0))
            is_short = video_duration <= 60
            video_type = 'shorts' if is_short else 'long_form'  # Use 'shorts' (plural) for title generator

            logger.info(f"Video duration: {video_duration}s, is_short: {is_short}, video_type: {video_type}")

            # Generate optimized content using parsed VTT formats
            # For shorts, always use full transcript (under 60 seconds = short transcript)
            use_full_transcript = is_short or len(plain_text) < 80000

            # Context for title/tags generation - use plain text only
            transcript_for_title = plain_text if is_short else plain_text[:2000]

            # Include target keyword if available from Upload Studio
            target_keyword_context = f"\nTarget Keyword: {target_keyword}" if target_keyword else ""

            title_tags_context = f"""
Video Title: {current_title}
Video Description: {current_description[:500]}
Video Transcript: {transcript_for_title}{target_keyword_context}
"""

            # Format segment timestamps for description/chapters (AI-friendly format)
            from app.scripts.optimize_video.vtt_parser import VTTParser

            timestamps_text = ""
            if not is_short and segments_with_time and len(segments_with_time) > 0:
                # For description: use all segments with timestamps
                # Format: 00:00:00.120 --> 00:00:01.990 I hired the coach in Clash Royale and
                timestamps_text = "\n\nTIMESTAMPED TRANSCRIPT (for chapters):\n"
                formatted_segments = VTTParser.format_segments_for_ai(segments_with_time, max_segments=None)
                timestamps_text += formatted_segments

                logger.info("=" * 80)
                logger.info("FORMATTED SEGMENTS FOR DESCRIPTION (first 500 chars):")
                logger.info("=" * 80)
                logger.info(formatted_segments[:500])
                logger.info("=" * 80)

            # Context for description generation (includes timestamped segments for chapters)
            description_context = f"""
Video Title: {current_title}
Video Description: {current_description[:500]}
Video Length: {'Short' if is_short else 'Long'}{target_keyword_context}
{timestamps_text if not is_short else ''}
"""

            # Initialize results
            title_result = {}
            title_suggestions = []
            optimized_titles = current_title
            description_result = {}
            optimized_description = current_description
            tags_result = {}
            optimized_tags = current_tags

            # Generate optimized title suggestions (1 AI call generates 10 titles)
            if 'title' in selected_optimizations:
                logger.info("=" * 80)
                logger.info("TITLE GENERATION - AI INPUT:")
                logger.info("=" * 80)
                logger.info(f"Video Type: {video_type}")
                logger.info(f"Context sent to AI (first 1000 chars):\n{title_tags_context[:1000]}")
                logger.info("=" * 80)

                title_result = self.title_generator.generate_titles(
                    title_tags_context,
                    video_type=video_type,  # 'short' or 'long_form'
                    user_id=user_id
                )

                # Get all 10 titles from the result
                all_titles = title_result.get('titles', [])
                if len(all_titles) >= 10:
                    title_suggestions = all_titles[:10]
                else:
                    # Fallback if not enough titles generated
                    title_suggestions = all_titles + [current_title] * (10 - len(all_titles))

                optimized_titles = title_suggestions[0] if title_suggestions else current_title  # Keep first for backward compatibility

            # Generate optimized description (with full transcript if short video)
            if 'description' in selected_optimizations:
                logger.info("=" * 80)
                logger.info("DESCRIPTION GENERATION - AI INPUT:")
                logger.info("=" * 80)
                logger.info(f"Video Type: {'short' if is_short else 'long'}")
                logger.info(f"Total segments with timestamps: {len(segments_with_time)}")
                logger.info(f"Context sent to AI (first 2000 chars):\n{description_context[:2000]}")
                if len(description_context) > 2000:
                    logger.info(f"... (truncated, total length: {len(description_context)} chars)")
                logger.info("=" * 80)

                # Use 'short' or 'long' for description generator
                desc_type = 'short' if is_short else 'long'
                description_result = self.description_generator.generate_description(
                    description_context,
                    video_type=desc_type,  # 'short' or 'long'
                    reference_description=current_description,
                    user_id=user_id
                )
                optimized_description = description_result.get('description', current_description)

                # Auto-generate chapters for long videos and append to description
                if not is_short:
                    logger.info("=" * 80)
                    logger.info("AUTO-GENERATING CHAPTERS FOR LONG VIDEO")
                    logger.info("=" * 80)

                    chapters_result = self.generate_chapters(
                        video_id=video_id,
                        user_id=user_id,
                        target_keyword=target_keyword,
                        user_subscription=user_subscription
                    )

                    if chapters_result.get('success'):
                        chapters_format = chapters_result.get('description_format', '')

                        # Append chapters to description
                        if chapters_format:
                            optimized_description = f"{optimized_description}\n\n{chapters_format}"
                            logger.info(f"✓ Added {chapters_result.get('num_chapters', 0)} chapters to description")

                        # Add chapter generation token usage for credit deduction
                        if chapters_result.get('token_usage'):
                            all_token_usages = all_token_usages if 'all_token_usages' in locals() else []
                            all_token_usages.append({
                                'operation': 'Chapter Generation',
                                **chapters_result.get('token_usage', {})
                            })
                    else:
                        logger.warning(f"Chapter generation failed: {chapters_result.get('error', 'Unknown error')}")

                    logger.info("=" * 80)

            # Generate optimized tags with channel keywords
            if 'tags' in selected_optimizations:
                logger.info("=" * 80)
                logger.info("TAGS GENERATION - AI INPUT:")
                logger.info("=" * 80)

                # Get channel keywords from user document
                from app.system.services.firebase_service import db

                user_ref = db.collection('users').document(user_id)
                user_doc = user_ref.get()
                channel_keywords = []
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    channel_keywords = user_data.get('youtube_channel_keywords', [])
                    logger.info(f"Channel keywords: {channel_keywords[:10]}")
                else:
                    logger.warning(f"User document not found for {user_id}")

                logger.info(f"Context sent to AI (first 1000 chars):\n{title_tags_context[:1000]}")
                logger.info("=" * 80)

                tags_result = self.tags_generator.generate_tags(
                    title_tags_context,
                    user_id=user_id,
                    channel_keywords=channel_keywords
                )
                optimized_tags = tags_result.get('tags', current_tags)

            # Skip recommendations generation - not displayed in UI and wastes credits
            # recommendations = self._generate_recommendations(...)
            recommendations = {}
            recommendations_token_usage = {}

            # Collect all token usage for credit deduction
            all_token_usages = []

            # Add title generation tokens
            if title_result.get('token_usage', {}).get('input_tokens', 0) > 0:
                all_token_usages.append({
                    'operation': 'Title Generation',
                    **title_result.get('token_usage', {})
                })

            # Add description generation tokens
            if description_result.get('token_usage', {}).get('input_tokens', 0) > 0:
                all_token_usages.append({
                    'operation': 'Description Generation',
                    **description_result.get('token_usage', {})
                })

            # Add tags generation tokens
            if tags_result.get('token_usage', {}).get('input_tokens', 0) > 0:
                all_token_usages.append({
                    'operation': 'Tags Generation',
                    **tags_result.get('token_usage', {})
                })

            # Skip recommendations tokens (disabled above)
            # if recommendations_token_usage.get('input_tokens', 0) > 0:
            #     all_token_usages.append({
            #         'operation': 'SEO Recommendations',
            #         **recommendations_token_usage
            #     })

            # Handle captions - correct and upload
            corrected_captions_result = None
            if 'captions' in selected_optimizations:
                logger.info("Running caption correction...")
                try:
                    caption_result = self.caption_corrector.correct_english_captions(
                        video_id=video_id,
                        user_id=user_id,
                        user_subscription=user_subscription
                    )

                    if caption_result.get('success'):
                        logger.info(f"Caption correction successful: {caption_result.get('message')}")
                        corrected_captions_result = caption_result

                        # Add token usage for credit deduction
                        if caption_result.get('token_usage'):
                            all_token_usages.append({
                                'operation': 'Caption Correction',
                                **caption_result['token_usage']
                            })
                    else:
                        logger.warning(f"Caption correction failed: {caption_result.get('error')}")
                        corrected_captions_result = caption_result
                except Exception as e:
                    logger.error(f"Error running caption correction: {e}")
                    corrected_captions_result = {'success': False, 'error': str(e)}

            # Handle pinned comment - generate and post
            pinned_comment_result = None
            if 'pinned_comment' in selected_optimizations:
                logger.info("Generating and posting pinned comment...")
                try:
                    pinned_result = self.pinned_comment_generator.generate_and_post_pinned_comment(
                        video_id=video_id,
                        user_id=user_id,
                        video_title=current_title,
                        target_keyword=None,  # Could extract from optimization context if needed
                        user_subscription=user_subscription
                    )

                    if pinned_result.get('success'):
                        logger.info(f"Pinned comment posted successfully")
                        pinned_comment_result = pinned_result

                        # Add token usage for credit deduction
                        if pinned_result.get('token_usage'):
                            all_token_usages.append({
                                'operation': 'Pinned Comment',
                                **pinned_result['token_usage']
                            })
                    else:
                        logger.warning(f"Pinned comment failed: {pinned_result.get('error')}")
                        pinned_comment_result = pinned_result
                except Exception as e:
                    logger.error(f"Error generating pinned comment: {e}")
                    pinned_comment_result = {'success': False, 'error': str(e)}

            # Prepare response
            return {
                'success': True,
                'video_info': {
                    'title': current_title,
                    'channel_title': video_info.get('channelTitle', ''),
                    'view_count': f"{int(video_info.get('viewCount', 0)):,}",
                    'like_count': f"{int(video_info.get('likeCount', 0)):,}",
                    'thumbnail': thumbnail_url,
                    'published_time': video_info.get('publishDate', '')
                },
                'current_title': current_title,
                'current_description': current_description,
                'current_tags': current_tags,
                'transcript_preview': plain_text[:500] + '...' if len(plain_text) > 500 else plain_text,
                'optimized_title': optimized_titles,
                'title_suggestions': title_suggestions,  # Return all 10 suggestions
                'optimized_description': optimized_description,
                'optimized_tags': optimized_tags,
                'recommendations': recommendations,
                'all_token_usages': all_token_usages,  # Return all token usages for credit deduction
                'corrected_captions_result': corrected_captions_result,  # Caption correction result
                'pinned_comment_result': pinned_comment_result  # Pinned comment result
            }

        except Exception as e:
            logger.error(f"Error optimizing video {video_id}: {e}")

            # Check for YouTube quota exceeded error
            error_str = str(e)
            if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
                return {
                    'success': False,
                    'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                    'error_type': 'quota_exceeded'
                }

            return {'success': False, 'error': str(e)}

    def _fetch_video_info(self, video_id: str) -> Dict:
        """Fetch video information from RapidAPI"""
        try:
            url = f"https://{self.rapidapi_host}/video/info"
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host
            }

            params = {
                "id": video_id,
                "extend": "2"
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Error fetching video info for {video_id}: {e}")
            return {}

    def _fetch_video_info_youtube_api(self, video_id: str, user_id: str) -> Dict:
        """
        Fetch video information using official YouTube API (for private/unlisted videos)
        Returns normalized video info matching RapidAPI format
        """
        try:
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            from googleapiclient.discovery import build

            # Get user's YouTube credentials
            yt_analytics = YouTubeAnalytics(user_id)
            if not yt_analytics.credentials:
                logger.warning(f"No YouTube credentials for user {user_id}")
                return {}

            # Build YouTube Data API client
            youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

            # Fetch video details
            video_response = youtube.videos().list(
                part='snippet,statistics,contentDetails,status',
                id=video_id
            ).execute()

            if not video_response.get('items'):
                logger.warning(f"No video found with ID {video_id}")
                return {}

            video = video_response['items'][0]
            snippet = video.get('snippet', {})
            statistics = video.get('statistics', {})
            content_details = video.get('contentDetails', {})

            # Parse duration (ISO 8601 format like PT1M30S)
            import re
            duration_str = content_details.get('duration', 'PT0S')
            duration_seconds = 0
            try:
                hours = re.search(r'(\d+)H', duration_str)
                minutes = re.search(r'(\d+)M', duration_str)
                seconds = re.search(r'(\d+)S', duration_str)

                if hours:
                    duration_seconds += int(hours.group(1)) * 3600
                if minutes:
                    duration_seconds += int(minutes.group(1)) * 60
                if seconds:
                    duration_seconds += int(seconds.group(1))
            except:
                duration_seconds = 0

            # Get best available thumbnail
            thumbnails = snippet.get('thumbnails', {})
            thumbnail_url = (
                thumbnails.get('maxres', {}).get('url') or
                thumbnails.get('high', {}).get('url') or
                thumbnails.get('medium', {}).get('url') or
                thumbnails.get('default', {}).get('url') or
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            )

            # Normalize to match RapidAPI format
            normalized_info = {
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'keywords': snippet.get('tags', []),
                'channelTitle': snippet.get('channelName', snippet.get('channelTitle', '')),
                'viewCount': statistics.get('viewCount', '0'),
                'likeCount': statistics.get('likeCount', '0'),
                'publishDate': snippet.get('publishedAt', ''),
                'lengthSeconds': duration_seconds,
                'thumbnail_url': thumbnail_url
            }

            logger.info(f"Fetched video info via YouTube API for {video_id}: {normalized_info['title']}")
            return normalized_info

        except Exception as e:
            logger.error(f"Error fetching video info via YouTube API for {video_id}: {e}")
            return {}

    def _fetch_vtt_youtube_api(self, video_id: str, user_id: str) -> str:
        """
        Fetch VTT captions using official YouTube API (for private/unlisted videos)
        Returns: Raw VTT string
        """
        try:
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            from googleapiclient.discovery import build

            # Get YouTube credentials
            yt_analytics = YouTubeAnalytics(user_id)
            if not yt_analytics.credentials:
                logger.info(f"No YouTube API credentials available for user {user_id}")
                return None

            # Build YouTube API client
            youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

            # Get captions list (50 units)
            captions_response = youtube.captions().list(
                part='snippet',
                videoId=video_id
            ).execute()

            if not captions_response.get('items'):
                logger.info(f"No captions available via YouTube API for video {video_id}")
                return None

            # Find English ASR (auto-generated) caption track
            caption_id = None
            for caption in captions_response['items']:
                lang = caption['snippet'].get('language', '')
                track_kind = caption['snippet'].get('trackKind', '')

                # Prefer ASR (auto-generated) tracks with per-word timestamps
                if (lang.startswith('en') or lang == 'en') and track_kind.lower() == 'asr':
                    caption_id = caption['id']
                    logger.info(f"Found ASR caption track: {caption['snippet'].get('name', '')}")
                    break

            # Fallback to any English caption
            if not caption_id:
                for caption in captions_response['items']:
                    lang = caption['snippet'].get('language', '')
                    if lang.startswith('en') or lang == 'en':
                        caption_id = caption['id']
                        logger.info(f"Using non-ASR caption track: {caption['snippet'].get('name', '')}")
                        break

            # Final fallback to first available caption
            if not caption_id and captions_response['items']:
                caption_id = captions_response['items'][0]['id']
                logger.info(f"Using first available caption track")

            if not caption_id:
                return None

            # Download caption track as VTT (200 units)
            caption_download = youtube.captions().download(
                id=caption_id,
                tfmt='vtt'  # WebVTT format with per-word timestamps
            ).execute()

            vtt_content = caption_download.decode('utf-8')
            logger.info(f"Successfully fetched VTT via YouTube API for video {video_id} ({len(vtt_content)} chars)")
            return vtt_content

        except Exception as e:
            logger.warning(f"Failed to fetch VTT via YouTube API for {video_id}: {e}")
            return None

    def _fetch_and_cache_vtt(self, video_id: str, user_id: str = None) -> Dict[str, Any]:
        """
        Fetch VTT captions with smart caching and fallback:
        1. Check Firestore cache first (7-day TTL)
        2. Try RapidAPI (free, works for public videos)
        3. Fallback to YouTube API (costs 250 quota units, for private videos)
        4. Parse VTT into 3 formats (per_word, segments_with_time, plain_text)
        5. Cache in Firestore for future use

        Returns:
            Dict with parsed VTT data:
            {
                'per_word': [...],  # For captions
                'segments_with_time': [...],  # For description/chapters
                'plain_text': '...',  # For title/tags
                'has_per_word_timestamps': True/False
            }
        """
        from app.system.services.firebase_service import db
        from datetime import datetime, timedelta, timezone
        from app.scripts.optimize_video.vtt_parser import VTTParser

        # Step 1: Check cache
        try:
            cache_ref = db.collection('users').document(user_id).collection('video_transcripts').document(video_id)
            cache_doc = cache_ref.get()

            if cache_doc.exists:
                cache_data = cache_doc.to_dict()
                expires_at = cache_data.get('expires_at')

                # Check if cache is still valid (handle timezone-aware datetime from Firestore)
                if expires_at:
                    # Make current time timezone-aware (UTC) to match Firestore timestamp
                    now_utc = datetime.now(timezone.utc)

                    # If expires_at is naive, make it UTC-aware
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)

                    if expires_at > now_utc:
                        logger.info(f"✓ Using cached VTT for video {video_id}")
                        return {
                            'per_word': cache_data.get('per_word', []),
                            'segments_with_time': cache_data.get('segments_with_time', []),
                            'plain_text': cache_data.get('plain_text', ''),
                            'has_per_word_timestamps': cache_data.get('has_per_word_timestamps', False)
                        }
                    else:
                        logger.info(f"Cache expired for video {video_id}, re-fetching")
        except Exception as e:
            logger.warning(f"Could not check cache for video {video_id}: {e}")

        # Step 2: Fetch VTT from RapidAPI (free, public videos only)
        vtt_content = None
        logger.info(f"Attempting RapidAPI VTT fetch for video {video_id}")

        try:
            url = "https://yt-api.p.rapidapi.com/subtitles"
            querystring = {"id": video_id, "format": "vtt"}
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host
            }

            response = requests.get(url, headers=headers, params=querystring, timeout=30)

            if response.status_code == 200:
                data = response.json()
                subtitles = data.get('subtitles', [])

                # Find English auto-generated caption
                for sub in subtitles:
                    lang_name = sub.get('languageName', '')
                    if 'English' in lang_name and 'auto-generated' in lang_name.lower():
                        vtt_url = sub['url']
                        vtt_response = requests.get(vtt_url, timeout=30)

                        if vtt_response.status_code == 200:
                            vtt_content = vtt_response.text
                            logger.info(f"✓ Fetched VTT from RapidAPI for {video_id} ({len(vtt_content)} chars)")
                            break

        except Exception as e:
            logger.warning(f"RapidAPI VTT fetch failed for {video_id}: {e}")

        # Step 3: Fallback to YouTube API (private/unlisted videos)
        if not vtt_content and user_id:
            logger.info(f"Attempting YouTube API VTT fetch for video {video_id} (250 quota units)")
            vtt_content = self._fetch_vtt_youtube_api(video_id, user_id)

        if not vtt_content:
            logger.error(f"Failed to fetch VTT for {video_id} from both RapidAPI and YouTube API")
            return {
                'per_word': [],
                'segments_with_time': [],
                'plain_text': '',
                'has_per_word_timestamps': False
            }

        # Step 4: Parse VTT into all formats
        logger.info("=" * 80)
        logger.info("VTT PARSING:")
        logger.info("=" * 80)
        logger.info(f"VTT content length: {len(vtt_content)} chars")
        logger.info(f"First 500 chars of VTT:\n{vtt_content[:500]}")
        logger.info("=" * 80)

        parsed_data = VTTParser.parse_vtt(vtt_content)

        logger.info("=" * 80)
        logger.info("PARSED VTT RESULTS:")
        logger.info("=" * 80)
        logger.info(f"✓ Per-word timestamps: {len(parsed_data['per_word'])} words")
        logger.info(f"✓ Segments with time: {len(parsed_data['segments_with_time'])} segments")
        logger.info(f"✓ Plain text length: {len(parsed_data['plain_text'])} chars")
        logger.info(f"✓ Has per-word timestamps: {parsed_data['has_per_word_timestamps']}")

        if parsed_data['per_word']:
            logger.info(f"First 5 per-word entries: {parsed_data['per_word'][:5]}")

        if parsed_data['segments_with_time']:
            logger.info(f"First 3 segments: {parsed_data['segments_with_time'][:3]}")

        logger.info(f"Plain text preview (first 200 chars): {parsed_data['plain_text'][:200]}")
        logger.info("=" * 80)

        # Step 5: Cache parsed data in Firestore (7-day TTL)
        try:
            now_utc = datetime.now(timezone.utc)
            cache_data = {
                'video_id': video_id,
                'per_word': parsed_data['per_word'],
                'segments_with_time': parsed_data['segments_with_time'],
                'plain_text': parsed_data['plain_text'],
                'has_per_word_timestamps': parsed_data['has_per_word_timestamps'],
                'created_at': now_utc,
                'expires_at': now_utc + timedelta(days=7)
            }

            cache_ref = db.collection('users').document(user_id).collection('video_transcripts').document(video_id)
            cache_ref.set(cache_data)
            logger.info(f"✓ Cached VTT data for video {video_id} (expires in 7 days)")

        except Exception as e:
            logger.warning(f"Could not cache VTT data for {video_id}: {e}")

        return parsed_data

    def _generate_recommendations(
        self,
        video_info: Dict,
        transcript: str,
        current_title: str,
        current_description: str,
        current_tags: list,
        optimized_title: str,
        optimized_description: str,
        optimized_tags: list,
        user_id: str,
        user_subscription: str = None
    ) -> Dict:
        """Generate overall video optimization recommendations"""
        try:
            ai_provider = get_ai_provider(
                script_name='optimize_video/video_optimizer',
                user_subscription=user_subscription
            )
            if not ai_provider:
                return {'error': 'AI provider not available'}

            # Build analysis prompt
            now = datetime.now()

            system_prompt_template = load_prompt('generate_recommendations_system.txt')
            system_prompt = system_prompt_template.format(
                current_date=now.strftime('%B %d, %Y'),
                current_year=now.year
            )

            user_prompt_template = load_prompt('generate_recommendations_user.txt')
            prompt = user_prompt_template.format(
                current_title=current_title,
                current_description=current_description[:500],
                current_tags=', '.join(current_tags[:15]),
                view_count=video_info.get('viewCount', 0),
                like_count=video_info.get('likeCount', 0),
                comment_count=video_info.get('commentCount', 0),
                transcript_preview=transcript[:1500],
                optimized_title=optimized_title,
                optimized_description_preview=f"{optimized_description[:300]}...",
                optimized_tags=', '.join(optimized_tags[:15])
            )

            # ASYNC AI call #1 - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=7000
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

            recommendations_text = response.get('content', '') if isinstance(response, dict) else str(response)

            # Get token usage from response (don't deduct here - will be handled centrally)
            usage = response.get('usage', {})
            provider_enum = response.get('provider_enum')
            token_usage = {
                'model': response.get('model', None),
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'provider_enum': provider_enum.value if provider_enum else None
            }

            return {
                'overview': recommendations_text,
                'title_comparison': f"Current: {current_title}\nOptimized: {optimized_title}",
                'has_improvements': True,
                'token_usage': token_usage
            }

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return {'error': str(e)}

    def correct_english_captions(self, video_id: str, user_id: str, user_subscription: str = None) -> Dict[str, Any]:
        """
        Download English captions, correct grammar/remove filler words, and re-upload
        Delegates to CaptionCorrector class

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication
            user_subscription: User's subscription plan for AI provider selection

        Returns:
            Dict with success status and details
        """
        return self.caption_corrector.correct_english_captions(video_id, user_id, user_subscription)

    def generate_chapters(self, video_id: str, user_id: str, target_keyword: str = None, user_subscription: str = None) -> Dict[str, Any]:
        """
        Generate chapters/timestamps from video transcript

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication and credits
            target_keyword: Optional target keyword for SEO optimization

        Returns:
            Dict with chapters list and description format
        """
        try:
            # Fetch VTT (uses cache if available, avoiding redundant API calls)
            logger.info("=" * 80)
            logger.info("CHAPTER GENERATION - FETCHING VTT DATA:")
            logger.info("=" * 80)

            vtt_data = self._fetch_and_cache_vtt(video_id, user_id)

            if not vtt_data['segments_with_time']:
                return {
                    'success': False,
                    'error': 'No transcript available for chapter generation',
                    'error_type': 'no_transcript'
                }

            segments_with_time = vtt_data['segments_with_time']
            plain_text = vtt_data['plain_text']

            logger.info(f"✓ Using VTT data: {len(segments_with_time)} segments, {len(plain_text)} chars plain text")
            logger.info("=" * 80)

            # Group segments into chapters (one chapter every ~2-3 minutes)
            # Average speaking rate: ~150 words per minute
            # So ~300-450 words per chapter
            WORDS_PER_CHAPTER = 350

            # Calculate total words
            total_words = len(plain_text.split())

            # Determine number of chapters (minimum 3, maximum 12)
            num_chapters = max(3, min(12, total_words // WORDS_PER_CHAPTER))

            # Create evenly spaced chapter start points
            words_per_segment = total_words // num_chapters

            # Group segments into chapters
            chapters_data = []
            current_word_count = 0
            chapter_segments = []

            for seg in segments_with_time:
                chapter_segments.append(seg)
                current_word_count += len(seg['text'].split())

                # Create chapter when we reach target word count
                if current_word_count >= words_per_segment or seg == segments_with_time[-1]:
                    # Get timestamp from first segment in this chapter (use 'start' field)
                    timestamp = chapter_segments[0]['start']

                    # Combine text for this chapter
                    chapter_text = ' '.join([s['text'] for s in chapter_segments])

                    chapters_data.append({
                        'timestamp': timestamp,
                        'text': chapter_text
                    })

                    # Reset for next chapter
                    chapter_segments = []
                    current_word_count = 0

            # Generate SEO-optimized chapter titles using AI
            logger.info(f"Generating {len(chapters_data)} chapter titles for video {video_id}")

            chapter_titles, token_usage = self._generate_chapter_titles(chapters_data, target_keyword, user_id, user_subscription)

            if not chapter_titles or len(chapter_titles) != len(chapters_data):
                return {
                    'success': False,
                    'error': 'Failed to generate chapter titles'
                }

            # Combine timestamps with titles
            chapters = []
            for i, (data, title) in enumerate(zip(chapters_data, chapter_titles)):
                chapters.append({
                    'timestamp': data['timestamp'],
                    'title': title
                })

            # Format for YouTube description (chapters must start at 0:00)
            description_format = self._format_chapters_for_description(chapters)

            return {
                'success': True,
                'chapters': chapters,
                'description_format': description_format,
                'num_chapters': len(chapters),
                'token_usage': token_usage  # For credit deduction
            }

        except Exception as e:
            logger.error(f"Error generating chapters for video {video_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_chapter_titles(self, chapters_data: list, target_keyword: str, user_id: str, user_subscription: str = None) -> tuple:
        """Use AI to generate SEO-optimized chapter titles. Returns (titles, token_usage)"""
        try:
            ai_provider = get_ai_provider(
                script_name='optimize_video/chapter_generation',
                user_subscription=user_subscription
            )
            if not ai_provider:
                logger.error("AI provider not available for chapter generation")
                return None, None

            # Build prompt with all chapters
            chapters_text = ""
            for i, chapter in enumerate(chapters_data, 1):
                chapters_text += f"\nChapter {i} ({chapter['timestamp']}):\n{chapter['text'][:300]}...\n"

            keyword_context = f"{target_keyword}" if target_keyword else ""

            system_prompt_template = load_prompt('chapter_generation_system.txt')
            user_prompt_template = load_prompt('chapter_generation_user.txt')

            system_prompt = system_prompt_template
            user_prompt = user_prompt_template.format(
                target_keyword=keyword_context,
                chapters_text=chapters_text,
                num_chapters=len(chapters_data)
            )

            # ASYNC AI call #2 - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=7000
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

            titles_text = response.get('content', '') if isinstance(response, dict) else str(response)

            # Parse titles (one per line, may have numbers)
            import re
            lines = titles_text.strip().split('\n')
            titles = []

            for line in lines:
                # Remove numbering (1., 1), Chapter 1:, etc.)
                clean_line = re.sub(r'^\d+[\.):\-\s]+', '', line.strip())
                clean_line = re.sub(r'^Chapter\s+\d+[\:\-\s]*', '', clean_line, flags=re.IGNORECASE)

                if clean_line:
                    titles.append(clean_line)

            # Get token usage (don't deduct here - will be handled centrally)
            usage = response.get('usage', {})
            provider_enum = response.get('provider_enum')
            token_usage = {
                'model': response.get('model', None),
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'provider_enum': provider_enum.value if provider_enum else None
            }

            return titles[:len(chapters_data)], token_usage  # Return exact number needed

        except Exception as e:
            logger.error(f"Error generating chapter titles: {e}")
            return None, None

    def _format_chapters_for_description(self, chapters: list) -> str:
        """Format chapters for YouTube description"""
        lines = []

        for chapter in chapters:
            # Convert timestamp to YouTube format (0:00 or 0:00:00)
            timestamp = chapter['timestamp']

            # Handle different timestamp formats
            if isinstance(timestamp, str):
                # May be in format HH:MM:SS,mmm or MM:SS or HH:MM:SS
                timestamp = timestamp.split(',')[0]  # Remove milliseconds if present

                # Convert to YouTube format (remove leading zeros from hours)
                parts = timestamp.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    h, m, s = parts
                    if int(h) == 0:
                        timestamp = f"{int(m)}:{s}"
                    else:
                        timestamp = f"{int(h)}:{m}:{s}"
                elif len(parts) == 2:  # MM:SS
                    m, s = parts
                    timestamp = f"{int(m)}:{s}"

            lines.append(f"{timestamp} {chapter['title']}")

        return '\n'.join(lines)

    def generate_and_post_pinned_comment(self, video_id: str, user_id: str, video_title: str = None, target_keyword: str = None, user_subscription: str = None) -> Dict[str, Any]:
        """
        Generate an engaging pinned comment and post it to the video
        Delegates to PinnedCommentGenerator class

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication and credits
            video_title: Optional video title for context
            target_keyword: Optional target keyword for SEO
            user_subscription: User's subscription plan for AI provider selection

        Returns:
            Dict with success status and comment text
        """
        return self.pinned_comment_generator.generate_and_post_pinned_comment(video_id, user_id, video_title, target_keyword, user_subscription)
