"""
TikTok Title & Hashtags Generator Module
Generates TikTok titles with hooks and hashtags based on keywords
"""
import os
import logging
from pathlib import Path
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from app.system.ai_provider.ai_provider import get_ai_provider


# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

def load_prompt(filename: str, section: str = None) -> str:
    """Load a prompt from text file, optionally extracting a specific section"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # If no section specified, return full content
        if not section:
            return content.strip()

        # Extract specific section
        section_marker = f"############# {section} #############"
        if section_marker not in content:
            logger.error(f"Section '{section}' not found in {filename}")
            raise ValueError(f"Section '{section}' not found")

        # Find the start of this section
        start_idx = content.find(section_marker)
        if start_idx == -1:
            raise ValueError(f"Section '{section}' not found")

        # Skip past the section marker and newline
        content_start = start_idx + len(section_marker)
        if content_start < len(content) and content[content_start] == '\n':
            content_start += 1

        # Find the next section marker (if any)
        next_section = content.find("\n#############", content_start)

        if next_section == -1:
            # This is the last section
            section_content = content[content_start:]
        else:
            # Extract until next section
            section_content = content[content_start:next_section]

        return section_content.strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}, section {section}: {e}")
        raise
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TikTokTitleGenerator:
    """TikTok Title Generator with AI support and web analysis"""

    def __init__(self):
        pass

    def generate_titles(self, keywords: str, video_input: str = '',
                       user_id: str = None, user_subscription: str = None) -> Dict:
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
            ai_provider = get_ai_provider(
                script_name='tiktok_titles_hashtags/tiktok_title_generator',
                user_subscription=user_subscription
            )

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # Build the prompt
                    prompt = self._build_prompt(keyword_list, video_input)

                    # System prompt
                    system_prompt_template = load_prompt('prompts.txt', 'SYSTEM_PROMPT')
                    system_prompt = system_prompt_template.format(
                        current_date=now.strftime('%B %d, %Y'),
                        current_year=now.year
                    )

                    # Log the prompt
                    logger.info(f"=== TIKTOK TITLE GENERATION PROMPT ===")
                    logger.info(f"Keywords: {keywords}")
                    logger.info(f"Video Input: {video_input[:100] if video_input else 'None'}...")
                    logger.info("=== END PROMPT ===")

                    # Generate using AI provider
                    # ASYNC AI call - thread is freed during AI generation!
                    import asyncio

                    async def _call_ai_async():
                        """Wrapper to call async AI in thread pool - frees main thread!"""
                        return await ai_provider.create_completion_async(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.9,
                            max_tokens=7000
                        )

                    # Run async call - thread is freed via run_in_executor internally
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        response = loop.run_until_complete(_call_ai_async())
                    finally:
                        loop.close()

                    # Extract titles from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    titles = self._parse_ai_response(response_content)

                    # Get actual token usage from AI provider response
                    token_usage = response.get('usage', {}) if isinstance(response, dict) else {}

                    return {
                        'success': True,
                        'titles': titles,
                        'used_ai': True,
                        'token_usage': {
                            'model': response.get('model', 'ai_provider') if isinstance(response, dict) else 'ai_provider',
                            'input_tokens': token_usage.get('input_tokens', 0),
                            'output_tokens': token_usage.get('output_tokens', 0),
                            'provider_enum': response.get('provider_enum') if isinstance(response, dict) else None
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
                    'output_tokens': 0,
                    'provider_enum': None
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

        # Format video context if provided
        video_context = ""
        if video_input:
            video_context = f"""Video Context:
{video_input}
"""

        user_prompt_template = load_prompt('prompts.txt', 'USER_PROMPT')
        return user_prompt_template.format(
            keywords_formatted=keywords_formatted,
            video_context=video_context
        )

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
