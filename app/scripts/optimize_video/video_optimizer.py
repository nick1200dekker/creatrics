"""
Video Optimizer
Optimizes user's own YouTube videos with AI recommendations
"""
import os
import logging
import requests
from typing import Dict, Any
from app.system.ai_provider.ai_provider import get_ai_provider
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
from app.scripts.video_description.video_description import VideoDescriptionGenerator
from app.scripts.video_tags.video_tags import VideoTagsGenerator
from app.scripts.optimize_video.thumbnail_analyzer import ThumbnailAnalyzer

logger = logging.getLogger(__name__)

class VideoOptimizer:
    """Optimizes user's videos with AI recommendations"""

    def __init__(self):
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.rapidapi_host = "yt-api.p.rapidapi.com"
        self.title_generator = VideoTitleGenerator()
        self.description_generator = VideoDescriptionGenerator()
        self.tags_generator = VideoTagsGenerator()
        self.thumbnail_analyzer = ThumbnailAnalyzer()

    def optimize_video(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """
        Optimize a video with AI-powered recommendations

        Args:
            video_id: YouTube video ID
            user_id: User ID for credit deduction

        Returns:
            Dict with optimization results
        """
        try:
            # Fetch video info
            video_info = self._fetch_video_info(video_id)
            if not video_info:
                return {'success': False, 'error': 'Failed to fetch video information'}

            # Fetch transcript
            transcript_text = self._fetch_transcript(video_id)

            # Get current metadata
            current_title = video_info.get('title', '')
            current_description = video_info.get('description', '')
            current_tags = video_info.get('keywords', [])

            # Get thumbnail URL
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

            # Generate optimized content using existing scripts
            # Combine transcript and current title/description for context
            optimization_context = f"""
Video Title: {current_title}
Video Description: {current_description[:500]}
Video Transcript: {transcript_text[:2000]}
"""

            # Generate 5 optimized title suggestions
            title_suggestions = []
            for i in range(5):
                title_result = self.title_generator.generate_titles(
                    optimization_context,
                    video_type='long_form',
                    user_id=user_id
                )
                if title_result.get('titles'):
                    title_suggestions.append(title_result.get('titles')[0])

            # Fallback if not enough titles generated
            if len(title_suggestions) < 5:
                title_suggestions.extend([current_title] * (5 - len(title_suggestions)))

            optimized_titles = title_suggestions[0]  # Keep first for backward compatibility

            # Generate optimized description
            description_result = self.description_generator.generate_description(
                optimization_context,
                video_type='long',
                reference_description=current_description,
                user_id=user_id
            )
            optimized_description = description_result.get('description', current_description)

            # Generate optimized tags
            tags_result = self.tags_generator.generate_tags(
                optimization_context,
                user_id=user_id
            )
            optimized_tags = tags_result.get('tags', current_tags)

            # Analyze thumbnail with Claude Vision
            thumbnail_analysis = self.thumbnail_analyzer.analyze_thumbnail(
                thumbnail_url,
                current_title,
                user_id
            )

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
                thumbnail_analysis,
                user_id
            )

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
                'thumbnail_analysis': thumbnail_analysis.get('analysis', ''),
                'recommendations': recommendations
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

            response = requests.get(url, headers=headers, params={"id": video_id, "extend": "2"})
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Error fetching video info for {video_id}: {e}")
            return {}

    def _fetch_transcript(self, video_id: str) -> str:
        """Fetch video transcript from RapidAPI"""
        try:
            url = f"https://{self.rapidapi_host}/get_transcript"
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host
            }

            # Step 1: Get language menu
            response = requests.get(url, headers=headers, params={"id": video_id})
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
                return ""

            # Step 2: Fetch actual transcript
            response = requests.get(url, headers=headers, params={"id": video_id, "params": transcript_params})
            response.raise_for_status()

            transcript_data = response.json()

            # Extract transcript text
            if 'transcript' in transcript_data:
                segments = transcript_data['transcript']
                if isinstance(segments, list) and len(segments) > 0:
                    text_segments = []
                    for segment in segments:
                        if isinstance(segment, dict) and 'text' in segment:
                            text_segments.append(segment['text'])

                    full_transcript = ' '.join(text_segments)
                    logger.info(f"Fetched transcript for {video_id}: {len(full_transcript)} characters")
                    return full_transcript

            return ""

        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return ""

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
        thumbnail_analysis: Dict,
        user_id: str
    ) -> Dict:
        """Generate overall video optimization recommendations"""
        try:
            ai_provider = get_ai_provider()
            if not ai_provider:
                return {'error': 'AI provider not available'}

            # Deduct credits
            credits_manager = CreditsManager()
            if not credits_manager.deduct_credits(user_id, 10):
                return {'error': 'Insufficient credits'}

            # Build analysis prompt
            prompt = f"""Analyze this YouTube video and provide optimization recommendations.

CURRENT METADATA:
Title: {current_title}
Description: {current_description[:500]}
Tags: {', '.join(current_tags[:15])}

VIDEO STATS:
Views: {video_info.get('viewCount', 0)}
Likes: {video_info.get('likeCount', 0)}
Comments: {video_info.get('commentCount', 0)}

TRANSCRIPT PREVIEW:
{transcript[:1500]}

OPTIMIZED SUGGESTIONS:
New Title: {optimized_title}
New Description: {optimized_description[:300]}...
New Tags: {', '.join(optimized_tags[:15])}

THUMBNAIL ANALYSIS:
{thumbnail_analysis.get('analysis', 'No thumbnail analysis available')}

Provide specific recommendations in these areas:
1. Title Optimization - Compare current vs optimized
2. Description Improvements - Key changes needed
3. Tags Strategy - SEO improvements
4. Thumbnail Recommendations - Visual improvements
5. Content Insights - What's working and what could improve

Format as clear, actionable bullet points for each section."""

            system_prompt = """You are a YouTube optimization expert. Provide specific, actionable recommendations
            to improve video performance. Focus on SEO, engagement, and discoverability."""

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )

            recommendations_text = response.get('content', '') if isinstance(response, dict) else str(response)

            return {
                'overview': recommendations_text,
                'title_comparison': f"Current: {current_title}\nOptimized: {optimized_title}",
                'has_improvements': True
            }

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return {'error': str(e)}
