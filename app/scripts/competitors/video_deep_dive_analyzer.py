"""
Video Deep Dive Analyzer
Analyzes individual competitor videos for insights
"""
import os
import re
import requests
import logging
from typing import Dict, Any
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider
from app.system.credits.credits_manager import CreditsManager

logger = logging.getLogger(__name__)

class VideoDeepDiveAnalyzer:
    """Analyzes a single video for deep insights"""

    def __init__(self):
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.rapidapi_host = "yt-api.p.rapidapi.com"

    def analyze_video(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """
        Perform deep dive analysis on a video

        Args:
            video_id: YouTube video ID
            user_id: User ID for credit deduction

        Returns:
            Dict with analysis results
        """
        try:
            # Fetch video info
            video_info = self._fetch_video_info(video_id)
            if not video_info:
                return {'success': False, 'error': 'Failed to fetch video info'}

            # Fetch transcript
            transcript_text = self._fetch_transcript(video_id)

            # Generate summary from transcript
            summary = self._generate_summary(transcript_text, user_id)

            # Analyze with AI
            analysis_result = self._analyze_with_ai(video_info, transcript_text, user_id)

            if not analysis_result.get('success'):
                return analysis_result

            # Format the data
            view_count = int(video_info.get('viewCount', 0)) if video_info.get('viewCount') else 0
            like_count = int(video_info.get('likeCount', 0)) if video_info.get('likeCount') else 0
            length_seconds = int(video_info.get('lengthSeconds', 0)) if video_info.get('lengthSeconds') else 0

            # Format duration
            duration = self._format_duration(length_seconds)

            # Format publish date
            publish_date = self._format_date(video_info.get('publishDate', ''))

            # Clean analysis markdown
            analysis_html = self._format_analysis(analysis_result.get('analysis', ''))

            # Prepare response
            return {
                'success': True,
                'data': {
                    'video_info': {
                        'title': video_info.get('title', ''),
                        'description': video_info.get('description', '').strip(),  # Strip whitespace
                        'keywords': video_info.get('keywords', [])[:15],
                        'view_count': f"{view_count:,}",
                        'like_count': f"{like_count:,}",
                        'duration': duration,
                        'publish_date': publish_date,
                        'channel_title': video_info.get('channelTitle', ''),
                        'thumbnail': f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                    },
                    'transcript_preview': transcript_text,
                    'summary': summary,
                    'analysis': analysis_html
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing video {video_id}: {e}")
            return {'success': False, 'error': str(e)}

    def _fetch_video_info(self, video_id: str) -> Dict:
        """Fetch video information from RapidAPI"""
        try:
            url = f"https://{self.rapidapi_host}/video/info"
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host
            }

            response = requests.get(url, headers=headers, params={"id": video_id})
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Error fetching video info for {video_id}: {e}")
            return {}

    def _fetch_transcript(self, video_id: str) -> str:
        """Fetch video transcript from RapidAPI - two-step process"""
        try:
            url = f"https://{self.rapidapi_host}/get_transcript"
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host
            }

            # Step 1: Get language menu to find transcript params
            response = requests.get(url, headers=headers, params={"id": video_id})
            response.raise_for_status()

            language_data = response.json()
            logger.info(f"Transcript language menu response keys: {language_data.keys()}")

            # Extract params from languageMenu
            transcript_params = None
            if 'languageMenu' in language_data and isinstance(language_data['languageMenu'], list):
                # Try to find English transcript first, otherwise use first available
                for lang_option in language_data['languageMenu']:
                    if isinstance(lang_option, dict) and 'params' in lang_option:
                        title = lang_option.get('title', '').lower()
                        if 'english' in title or 'en' in title:
                            transcript_params = lang_option['params']
                            logger.info(f"Found English transcript params")
                            break

                # If no English found, use first available
                if not transcript_params and len(language_data['languageMenu']) > 0:
                    first_option = language_data['languageMenu'][0]
                    if isinstance(first_option, dict) and 'params' in first_option:
                        transcript_params = first_option['params']
                        logger.info(f"Using first available transcript: {first_option.get('title', 'unknown')}")

            if not transcript_params:
                logger.warning(f"No transcript params found for video {video_id}")
                return ""

            # Step 2: Fetch actual transcript using params
            response = requests.get(url, headers=headers, params={"id": video_id, "params": transcript_params})
            response.raise_for_status()

            transcript_data = response.json()
            logger.info(f"Transcript data response keys: {transcript_data.keys()}")

            # Extract transcript text
            if 'transcript' in transcript_data:
                segments = transcript_data['transcript']
                if isinstance(segments, list) and len(segments) > 0:
                    # Take ALL segments for complete transcript
                    text_segments = []
                    for segment in segments:
                        if isinstance(segment, dict) and 'text' in segment:
                            text_segments.append(segment['text'])

                    if text_segments:
                        transcript_text = " ".join(text_segments)
                        logger.info(f"Successfully extracted FULL transcript: {len(transcript_text)} characters from {len(text_segments)} segments")
                        return transcript_text

            logger.warning(f"No transcript text found in final response for video {video_id}")
            return ""

        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return ""

    def _analyze_with_ai(self, video_info: Dict, transcript_text: str, user_id: str) -> Dict:
        """Analyze video with AI"""
        try:
            ai_provider = get_ai_provider()

            # Prepare data
            title = video_info.get('title', '')
            description = video_info.get('description', '')[:1000]  # First 1000 chars
            keywords = video_info.get('keywords', [])[:15]  # First 15 keywords
            view_count = int(video_info.get('viewCount', 0)) if video_info.get('viewCount') else 0
            like_count = int(video_info.get('likeCount', 0)) if video_info.get('likeCount') else 0

            # Build analysis prompt - SHORT bullet-point focused
            # Use full transcript for complete analysis
            full_transcript = transcript_text if transcript_text else "No transcript available"

            prompt = f"""Analyze this YouTube video. Keep it SHORT and bullet-point focused.

Title: {title}
Views: {view_count:,} | Likes: {like_count:,}

Full Video Transcript: {full_transcript}

Provide analysis in this EXACT format. Use simple bullet points (just dashes), NO bold text, NO extra symbols like ** or ###.

## Hook Strategy
- What hook/opening does this use
- Why it works (1 sentence max)

## Title Strategy
- Key element 1 that makes it clickable
- Key element 2 that makes it clickable
- Key element 3 that makes it clickable (optional)

## Content Insights
- Quick observation 1 about pacing/structure/engagement
- Quick observation 2
- Quick observation 3
- Quick observation 4 (optional)

## SEO Analysis
- What's working well (1-2 items)
- What could improve (1 item)

## Quick Wins
- Actionable takeaway 1
- Actionable takeaway 2
- Actionable takeaway 3

IMPORTANT RULES:
- Keep UNDER 250 words total
- Use ONLY simple dashes for bullets (-)
- NO bold markers like ** or __
- NO extra symbols or emojis
- Each bullet should be ONE short sentence
- Be direct and scannable"""

            system_prompt = "You are a YouTube analyst. Provide SHORT bullet points in plain text format. Do NOT use markdown bold (**), do NOT use extra formatting. Simple dashes only for bullets."

            # Call AI - increased max_tokens to handle longer transcripts
            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            analysis = response.get('content', '') if isinstance(response, dict) else str(response)
            usage = response.get('usage', {})

            # Deduct credits
            credits_manager = CreditsManager()
            credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=response.get('model', 'unknown'),
                input_tokens=usage.get('input_tokens', 0),
                output_tokens=usage.get('output_tokens', 0),
                description=f"Video Deep Dive Analysis - {title[:50]}"
            )

            return {
                'success': True,
                'analysis': analysis
            }

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {'success': False, 'error': str(e)}

    def _generate_summary(self, transcript_text: str, user_id: str) -> str:
        """Generate a detailed summary of the video from transcript"""
        if not transcript_text:
            return "No transcript available for this video."

        try:
            ai_provider = get_ai_provider()

            # Use full transcript for comprehensive summary
            prompt = f"""Summarize this YouTube video in a detailed paragraph (4-6 sentences).

Focus on:
1. What is the main topic/subject of this video?
2. What are the key points, strategies, or insights discussed?
3. What specific examples, demonstrations, or highlights are shown?
4. What value does this provide to viewers?

Full Video Transcript:
{transcript_text}

Write an engaging, informative summary that captures the essence and best parts of the video."""

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": "You are a YouTube video analyst. Create detailed, informative summaries that capture key points and value."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=250
            )

            summary = response.get('content', '') if isinstance(response, dict) else str(response)
            usage = response.get('usage', {})

            # Deduct credits
            credits_manager = CreditsManager()
            credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=response.get('model', 'unknown'),
                input_tokens=usage.get('input_tokens', 0),
                output_tokens=usage.get('output_tokens', 0),
                description="Video Summary Generation"
            )

            return summary.strip()

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Summary not available."

    def _format_duration(self, seconds: int) -> str:
        """Format seconds into MM:SS or HH:MM:SS"""
        if seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}:{secs:02d}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}:{minutes:02d}:{secs:02d}"

    def _format_date(self, date_string: str) -> str:
        """Format ISO date to readable format"""
        if not date_string:
            return "Unknown"

        try:
            # Parse ISO format: 2025-09-25T16:31:40-07:00
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return dt.strftime("%B %d, %Y")  # e.g., "September 25, 2025"
        except Exception as e:
            logger.error(f"Error formatting date {date_string}: {e}")
            return date_string

    def _format_analysis(self, analysis_text: str) -> str:
        """Convert markdown analysis to clean HTML"""
        if not analysis_text:
            return ""

        # Remove the title if present
        analysis_text = re.sub(r'^#\s+YouTube Video Analysis:.*?\n\n', '', analysis_text, flags=re.MULTILINE)

        # Convert ## headers to h4 tags
        analysis_text = re.sub(r'^##\s+(.+)$', r'<h4>\1</h4>', analysis_text, flags=re.MULTILINE)

        # Convert bullet points to list items
        lines = analysis_text.split('\n')
        formatted_lines = []
        in_list = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('- '):
                if not in_list:
                    formatted_lines.append('<ul>')
                    in_list = True
                formatted_lines.append(f"<li>{stripped[2:]}</li>")
            else:
                if in_list:
                    formatted_lines.append('</ul>')
                    in_list = False
                if stripped:
                    formatted_lines.append(f"<p>{stripped}</p>")

        if in_list:
            formatted_lines.append('</ul>')

        return '\n'.join(formatted_lines)
