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


# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

def load_prompt(filename: str) -> str:
    """Load a prompt from text file"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        raise
logger = logging.getLogger(__name__)

class VideoOptimizer:
    """Optimizes user's videos with AI recommendations"""

    def __init__(self):
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.rapidapi_host = "yt-api.p.rapidapi.com"
        self.title_generator = VideoTitleGenerator()
        self.description_generator = VideoDescriptionGenerator()
        self.tags_generator = VideoTagsGenerator()

    def optimize_video(self, video_id: str, user_id: str, user_subscription: str = None) -> Dict[str, Any]:
        """
        Optimize a video with AI-powered recommendations

        Args:
            video_id: YouTube video ID
            user_id: User ID for credit deduction
            user_subscription: User's subscription plan for AI provider selection

        Returns:
            Dict with optimization results
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
                    return {'success': False, 'error': 'Failed to fetch video information'}

            # Fetch transcript (both text and with timestamps)
            # Pass user_id to enable YouTube API transcript fetching for private videos
            transcript_text, transcript_with_timestamps = self._fetch_transcript_with_timestamps(video_id, user_id)

            # Get current metadata
            current_title = video_info.get('title', '')
            current_description = video_info.get('description', '')
            current_tags = video_info.get('keywords', [])

            # Get thumbnail URL - use from API if available, otherwise use default YouTube URL
            thumbnail_url = video_info.get('thumbnail_url', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg")

            # Detect if video is a short (under 60 seconds)
            video_duration = int(video_info.get('lengthSeconds', 0))
            is_short = video_duration <= 60
            video_type = 'shorts' if is_short else 'long_form'  # Use 'shorts' (plural) for title generator

            logger.info(f"Video duration: {video_duration}s, is_short: {is_short}, video_type: {video_type}")

            # Generate optimized content using existing scripts
            # For descriptions, use full transcript if under 20k chars (roughly <15 min video)
            # For shorts, always use full transcript (under 60 seconds = short transcript)
            use_full_transcript = is_short or len(transcript_text) < 20000

            # Context for title/tags generation
            # For shorts, use full transcript since it's very short (under 60 seconds)
            transcript_for_title = transcript_text if is_short else transcript_text[:2000]

            title_tags_context = f"""
Video Title: {current_title}
Video Description: {current_description[:500]}
Video Transcript: {transcript_for_title}
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
Video Length: {'Under 15 minutes' if use_full_transcript else 'Over 15 minutes'}
{timestamps_text}
"""

            # Generate optimized title suggestions (1 AI call generates 10 titles)
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
            # Use 'short' or 'long' for description generator
            desc_type = 'short' if is_short else 'long'
            description_result = self.description_generator.generate_description(
                description_context,
                video_type=desc_type,  # 'short' or 'long'
                reference_description=current_description,
                user_id=user_id
            )
            optimized_description = description_result.get('description', current_description)

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

            # Generate optimized tags with channel keywords
            tags_result = self.tags_generator.generate_tags(
                title_tags_context,
                user_id=user_id,
                channel_keywords=channel_keywords
            )
            optimized_tags = tags_result.get('tags', current_tags)

            # Generate overall recommendations
            recommendations = self._generate_recommendations(
                video_info,
                transcript_text,
                current_title,
                current_description,
                current_tags,
                optimized_titles,
                optimized_description,
                optimized_tags,
                user_id,
                user_subscription
            )

            # Get recommendations token usage
            recommendations_token_usage = recommendations.get('token_usage', {})

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

            # Add recommendations tokens
            if recommendations_token_usage.get('input_tokens', 0) > 0:
                all_token_usages.append({
                    'operation': 'SEO Recommendations',
                    **recommendations_token_usage
                })

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
                'title_suggestions': title_suggestions,  # Return all 5 suggestions
                'optimized_description': optimized_description,
                'optimized_tags': optimized_tags,
                'recommendations': recommendations,
                'all_token_usages': all_token_usages  # Return all token usages for credit deduction
            }

        except Exception as e:
            logger.error(f"Error optimizing video {video_id}: {e}")
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
        1. Try YouTube API first (for private videos)
        2. Fallback to RapidAPI (for public videos)
        """
        # Try YouTube API first if user_id provided
        if user_id:
            yt_transcript, yt_timestamps = self._fetch_transcript_youtube_api(video_id, user_id)
            if yt_transcript:
                logger.info(f"Using YouTube API transcript for video {video_id}")
                return yt_transcript, yt_timestamps

        # Fallback to RapidAPI
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
                    logger.info(f"Fetched transcript for {video_id}: {len(full_transcript)} characters")
                    return full_transcript, timestamp_segments

            return "", []

        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
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
