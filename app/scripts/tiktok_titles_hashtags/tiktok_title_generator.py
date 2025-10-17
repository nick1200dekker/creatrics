"""
TikTok Title & Hashtags Generator Module
Generates TikTok titles with hooks and hashtags based on keywords
"""
import os
import logging
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from app.system.ai_provider.ai_provider import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TikTokTitleGenerator:
    """TikTok Title Generator with AI support and web analysis"""

    def __init__(self):
        pass

    def generate_titles(self, keywords: str, video_input: str = '',
                       user_id: str = None) -> Dict:
        """
        Generate TikTok titles with hooks and hashtags

        Args:
            keywords: Target keywords (comma-separated)
            video_input: Optional video description/script
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated titles
        """
        try:
            # Parse keywords
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]

            if not keyword_list:
                return {
                    'success': False,
                    'error': 'No valid keywords provided',
                    'titles': []
                }

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # Build the prompt
                    prompt = self._build_prompt(keyword_list, video_input)

                    # System prompt
                    system_prompt = f"""You are a TikTok content expert specializing in viral titles and hashtags.
Current date: {now.strftime('%B %d, %Y')}. Current year: {now.year}.

Your task is to create engaging TikTok titles that:
1. START with the target keyword (properly capitalized)
2. Include an attention-grabbing hook
3. End with 3 relevant hashtags

Format: "[Keyword] [Hook] #hashtag1 #hashtag2 #hashtag3"

Example: "Battlefield 6 This hidden weapon changed everything #battlefield #battlefield6 #gaming"

Always return exactly 10 titles in a JSON array format.
Use {now.year} for any year references."""

                    # Log the prompt
                    logger.info(f"=== TIKTOK TITLE GENERATION PROMPT ===")
                    logger.info(f"Keywords: {keywords}")
                    logger.info(f"Video Input: {video_input[:100] if video_input else 'None'}...")
                    logger.info("=== END PROMPT ===")

                    # Generate using AI provider
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.9,
                        max_tokens=1000
                    )

                    # Extract titles from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    titles = self._parse_ai_response(response_content)

                    return {
                        'success': True,
                        'titles': titles,
                        'used_ai': True,
                        'token_usage': {
                            'model': 'ai_provider',
                            'input_tokens': len(prompt.split()),
                            'output_tokens': len(' '.join(titles).split())
                        }
                    }

                except Exception as e:
                    logger.error(f"AI generation failed: {e}")
                    # Fall through to fallback

            # Fallback: Generate without AI
            titles = self._generate_fallback_titles(keyword_list, video_input)

            return {
                'success': True,
                'titles': titles,
                'used_ai': False,
                'token_usage': {
                    'model': 'fallback',
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            }

        except Exception as e:
            logger.error(f"Error generating TikTok titles: {e}")
            return {
                'success': False,
                'error': str(e),
                'titles': []
            }

    def _build_prompt(self, keyword_list: List[str], video_input: str) -> str:
        """Build the AI prompt for title generation"""

        # Format keywords
        keywords_formatted = '\n'.join([f"- {kw}" for kw in keyword_list])

        prompt = f"""Generate 10 viral TikTok titles based on these target keywords:

{keywords_formatted}

"""

        if video_input:
            prompt += f"""
Video Context:
{video_input}

"""

        prompt += """
IMPORTANT: Use trending TikTok title patterns:
- Use curiosity-driven hooks (e.g., "This moment...", "When I realized...", "POV:", "The time when...")
- Include emotional triggers (shock, surprise, relatability)
- Keep it conversational and authentic
- Use current slang and trends when appropriate

"""

        prompt += """
Requirements for EACH title:
1. MUST start with one of the target keywords (properly capitalized for brands/proper nouns)
2. Include an engaging hook that creates curiosity or emotion
3. End with exactly 3 relevant hashtags (no more, no less)
4. Keep total length under 150 characters
5. Make it feel natural and TikTok-native

Format: "[Keyword] [Hook] #hashtag1 #hashtag2 #hashtag3"

Examples:
- "Battlefield 6 The moment that made everyone stop scrolling #battlefield #battlefield6 #gaming"
- "Gaming Tips This trick pros don't want you to know #gamingtips #protips #gaming"
- "FPS Gameplay POV: You just discovered the meta weapon #fps #gameplay #gaming"

Return ONLY a JSON array of 10 titles, nothing else.
"""

        return prompt

    def _parse_ai_response(self, response: str) -> List[str]:
        """Parse AI response to extract titles"""
        try:
            logger.info(f"=== AI RESPONSE (first 500 chars) ===")
            logger.info(response[:500])

            # Try to extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                titles = json.loads(json_match.group())
                if isinstance(titles, list):
                    # Clean and validate titles
                    clean_titles = []
                    for title in titles:
                        if isinstance(title, str) and title.strip():
                            clean_titles.append(title.strip())

                    if clean_titles:
                        logger.info(f"Successfully parsed {len(clean_titles)} titles")
                        return clean_titles[:10]

            # Fallback: Try line-by-line parsing
            lines = response.strip().split('\n')
            titles = []
            for line in lines:
                # Remove numbering, quotes, etc.
                clean_line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
                clean_line = clean_line.strip('"\'')

                # Check if it looks like a title (has hashtags)
                if clean_line and '#' in clean_line:
                    titles.append(clean_line)

            if titles:
                logger.info(f"Parsed {len(titles)} titles from lines")
                return titles[:10]

            logger.warning("Could not parse titles from AI response")
            return []

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return []

    def _generate_fallback_titles(self, keyword_list: List[str], video_input: str) -> List[str]:
        """Generate fallback titles without AI"""
        titles = []

        # Common TikTok hooks
        hooks = [
            "This moment changed everything",
            "POV: You just discovered this",
            "The secret everyone's talking about",
            "This trick will blow your mind",
            "When I realized this was possible",
            "Nobody talks about this enough",
            "This is actually insane",
            "You need to see this",
            "The truth about this",
            "This is what pros do"
        ]

        # Generate titles for each keyword
        for i, keyword in enumerate(keyword_list):
            if i < len(hooks):
                # Create hashtags from keyword
                hashtag_base = keyword.lower().replace(' ', '')
                titles.append(f"{keyword} {hooks[i]} #{hashtag_base} #viral #fyp")

        # Fill remaining slots with variations
        while len(titles) < 10:
            idx = len(titles) % len(keyword_list)
            keyword = keyword_list[idx]
            hook_idx = len(titles) % len(hooks)
            hashtag_base = keyword.lower().replace(' ', '')
            titles.append(f"{keyword} {hooks[hook_idx]} #{hashtag_base} #trending #foryou")

        return titles[:10]
