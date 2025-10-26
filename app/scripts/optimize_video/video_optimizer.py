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

            # Fetch transcript (both text and with timestamps)
            # Pass user_id to enable YouTube API transcript fetching for private videos
            transcript_text, transcript_with_timestamps = self._fetch_transcript_with_timestamps(video_id, user_id)

            # Check if transcript is available - REQUIRED for optimization
            if not transcript_text or transcript_text.strip() == "":
                return {
                    'success': False,
                    'error': 'Transcript not available yet',
                    'error_type': 'transcript_unavailable',
                    'message': 'YouTube typically generates transcripts 15-30 minutes after upload. Please try again later.'
                }

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

            # Generate optimized content using existing scripts
            # For descriptions, use full transcript if under 80k chars (roughly <60 min video)
            # For shorts, always use full transcript (under 60 seconds = short transcript)
            use_full_transcript = is_short or len(transcript_text) < 80000

            # Context for title/tags generation
            # For shorts, use full transcript since it's very short (under 60 seconds)
            transcript_for_title = transcript_text if is_short else transcript_text[:2000]

            # Include target keyword if available from Upload Studio
            target_keyword_context = f"\nTarget Keyword: {target_keyword}" if target_keyword else ""

            title_tags_context = f"""
Video Title: {current_title}
Video Description: {current_description[:500]}
Video Transcript: {transcript_for_title}{target_keyword_context}
"""

            # Format timestamps for AI (skip for shorts) - just key timestamps
            timestamps_text = ""
            if not is_short and use_full_transcript and transcript_with_timestamps and len(transcript_with_timestamps) > 0:
                # Extract only 8-10 evenly spaced timestamps for chapter creation
                num_chapters = min(10, max(4, len(transcript_with_timestamps) // 30))  # 1 chapter per ~30 segments
                step = len(transcript_with_timestamps) // num_chapters

                timestamps_text = "\n\nKEY TIMESTAMPS (for chapters - these are actual video times):\n"
                for i in range(0, len(transcript_with_timestamps), step):
                    if i < len(transcript_with_timestamps):
                        seg = transcript_with_timestamps[i]
                        # Only include timestamp and first few words to identify topic
                        timestamps_text += f"{seg['time']}: {seg['text'][:50]}...\n"

                timestamps_text += f"\n(Video is approximately {len(transcript_with_timestamps)} segments long, use timestamps above to create accurate chapters)"

            # Context for description generation (may include full transcript)
            description_context = f"""
Video Title: {current_title}
Video Description: {current_description[:500]}
Video Transcript: {transcript_text if use_full_transcript else transcript_text[:2000]}
Video Length: {'Under 60 minutes' if use_full_transcript else 'Over 60 minutes'}{target_keyword_context}
{timestamps_text}
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
                logger.info("Generating title suggestions...")
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
                logger.info("Generating description...")
                # Use 'short' or 'long' for description generator
                desc_type = 'short' if is_short else 'long'
                description_result = self.description_generator.generate_description(
                    description_context,
                    video_type=desc_type,  # 'short' or 'long'
                    reference_description=current_description,
                    user_id=user_id
                )
                optimized_description = description_result.get('description', current_description)

            # Generate optimized tags with channel keywords
            if 'tags' in selected_optimizations:
                logger.info("Generating tags...")
                # Get channel keywords from user document
                from app.system.services.firebase_service import db

                user_ref = db.collection('users').document(user_id)
                user_doc = user_ref.get()
                channel_keywords = []
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    channel_keywords = user_data.get('youtube_channel_keywords', [])
                    logger.info(f"Retrieved {len(channel_keywords)} channel keywords for tag generation")
                    if channel_keywords:
                        logger.info(f"First 5 keywords: {channel_keywords[:5]}")
                else:
                    logger.warning(f"User document not found for {user_id}")

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
                'transcript_preview': transcript_text[:500] + '...' if len(transcript_text) > 500 else transcript_text,
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

    def _fetch_transcript_youtube_api(self, video_id: str, user_id: str) -> tuple:
        """
        Fetch transcript using official YouTube API (for private/unlisted videos)
        Returns: (transcript_text, transcript_with_timestamps)
        """
        try:
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            from googleapiclient.discovery import build

            # Get YouTube credentials
            yt_analytics = YouTubeAnalytics(user_id)
            if not yt_analytics.credentials:
                logger.info(f"No YouTube API credentials available for user {user_id}")
                return None, None

            # Build YouTube API client
            youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

            # Get captions list
            captions_response = youtube.captions().list(
                part='snippet',
                videoId=video_id
            ).execute()

            if not captions_response.get('items'):
                logger.info(f"No captions available via YouTube API for video {video_id}")
                return None, None

            # Find English caption track
            caption_id = None
            for caption in captions_response['items']:
                lang = caption['snippet'].get('language', '')
                if lang.startswith('en') or lang == 'en':
                    caption_id = caption['id']
                    break

            # Fallback to first available caption
            if not caption_id and captions_response['items']:
                caption_id = captions_response['items'][0]['id']

            if not caption_id:
                return None, None

            # Download caption track
            caption_download = youtube.captions().download(
                id=caption_id,
                tfmt='srt'  # SubRip format with timestamps
            ).execute()

            # Parse SRT format
            transcript_text = ""
            transcript_with_timestamps = []

            # Simple SRT parser
            blocks = caption_download.decode('utf-8').strip().split('\n\n')
            for block in blocks:
                lines = block.split('\n')
                if len(lines) >= 3:
                    # Line 0: sequence number
                    # Line 1: timestamp
                    # Lines 2+: text
                    timestamp = lines[1].split(' --> ')[0].strip()
                    text = ' '.join(lines[2:])

                    transcript_text += text + " "
                    transcript_with_timestamps.append({
                        'time': timestamp,
                        'text': text
                    })

            logger.info(f"Successfully fetched transcript via YouTube API for video {video_id}")
            return transcript_text.strip(), transcript_with_timestamps

        except Exception as e:
            logger.warning(f"Failed to fetch transcript via YouTube API for {video_id}: {e}")
            return None, None

    def _fetch_transcript_with_timestamps(self, video_id: str, user_id: str = None) -> tuple:
        """
        Fetch video transcript with smart fallback:
        1. Try RapidAPI first (free, works for public videos)
        2. Fallback to YouTube API (costs 250 quota units, for private/unlisted videos)
        """
        # Try RapidAPI first (free, no quota cost)
        logger.info(f"Attempting RapidAPI transcript for video {video_id}")
        try:
            import time
            url = f"https://{self.rapidapi_host}/get_transcript"
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }

            # Step 1: Get language menu (with cache-busting)
            params = {"id": video_id, "_t": int(time.time())}
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            language_data = response.json()

            # Extract transcript params
            transcript_params = None
            if 'languageMenu' in language_data and isinstance(language_data['languageMenu'], list):
                # Try to find English transcript first
                for lang_option in language_data['languageMenu']:
                    if isinstance(lang_option, dict) and 'params' in lang_option:
                        title = lang_option.get('title', '').lower()
                        if 'english' in title or 'en' in title:
                            transcript_params = lang_option['params']
                            break

                # Fallback to first available
                if not transcript_params and len(language_data['languageMenu']) > 0:
                    first_option = language_data['languageMenu'][0]
                    if isinstance(first_option, dict) and 'params' in first_option:
                        transcript_params = first_option['params']

            if not transcript_params:
                logger.warning(f"No transcript found for video {video_id}")
                return "", []

            # Step 2: Fetch actual transcript (with cache-busting)
            params = {"id": video_id, "params": transcript_params, "_t": int(time.time())}
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            transcript_data = response.json()

            # Extract transcript text and timestamps
            if 'transcript' in transcript_data:
                segments = transcript_data['transcript']
                if isinstance(segments, list) and len(segments) > 0:
                    text_segments = []
                    timestamp_segments = []

                    for segment in segments:
                        if isinstance(segment, dict) and 'text' in segment:
                            text_segments.append(segment['text'])

                            # Store timestamp info
                            if 'startTime' in segment:
                                timestamp_segments.append({
                                    'time': segment['startTime'],
                                    'text': segment['text']
                                })

                    full_transcript = ' '.join(text_segments)
                    logger.info(f"RapidAPI transcript fetched for {video_id}: {len(full_transcript)} characters")
                    return full_transcript, timestamp_segments

            logger.warning(f"No transcript data in RapidAPI response for video {video_id}")

        except Exception as e:
            logger.warning(f"RapidAPI transcript failed for {video_id}: {e}")

        # Fallback to YouTube API (for private/unlisted videos)
        if user_id:
            logger.info(f"Attempting YouTube API transcript as fallback for video {video_id}")
            yt_transcript, yt_timestamps = self._fetch_transcript_youtube_api(video_id, user_id)
            if yt_transcript:
                logger.info(f"YouTube API transcript fetched for video {video_id} (250 quota units used)")
                return yt_transcript, yt_timestamps

        logger.error(f"Failed to fetch transcript for {video_id} from both RapidAPI and YouTube API")
        return "", []

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

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )

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
            # Fetch transcript with timestamps
            transcript_text, transcript_with_timestamps = self._fetch_transcript_with_timestamps(video_id, user_id)

            if not transcript_text or not transcript_with_timestamps:
                return {
                    'success': False,
                    'error': 'No transcript available for chapter generation',
                    'error_type': 'no_transcript'
                }

            # Group transcript into sections (one chapter every ~2-3 minutes)
            # Average speaking rate: ~150 words per minute
            # So ~300-450 words per chapter
            WORDS_PER_CHAPTER = 350

            # Calculate total words
            total_words = len(transcript_text.split())

            # Determine number of chapters (minimum 3, maximum 12)
            num_chapters = max(3, min(12, total_words // WORDS_PER_CHAPTER))

            # Create evenly spaced chapter start points
            words_per_segment = total_words // num_chapters

            # Group segments into chapters
            chapters_data = []
            current_word_count = 0
            chapter_segments = []

            for seg in transcript_with_timestamps:
                chapter_segments.append(seg)
                current_word_count += len(seg['text'].split())

                # Create chapter when we reach target word count
                if current_word_count >= words_per_segment or seg == transcript_with_timestamps[-1]:
                    # Get timestamp from first segment in this chapter
                    timestamp = chapter_segments[0]['time']

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

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

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
