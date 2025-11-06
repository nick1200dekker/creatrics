"""
Instagram Caption & Hashtags Generator Module
Generates Instagram captions with hashtags based on keywords
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

class InstagramTitleGenerator:
    """Instagram Caption Generator with AI support"""

    def __init__(self):
        pass

    def generate_captions(self, keywords: str, content_description: str = '',
                       user_id: str = None, user_subscription: str = None) -> Dict:
        """
        Generate Instagram captions with hashtags

        Args:
            keywords: Target keywords (comma-separated)
            content_description: Optional content description
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated captions
        """
        try:
            # Parse keywords
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]

            if not keyword_list:
                return {
                    'success': False,
                    'error': 'No valid keywords provided',
                    'captions': []
                }

            # Get AI provider
            ai_provider = get_ai_provider(
                script_name='instagram_upload_studio/instagram_title_generator',
                user_subscription=user_subscription
            )

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # Build the prompt
                    prompt = self._build_prompt(keyword_list, content_description)

                    # System prompt
                    system_prompt_template = load_prompt('prompts.txt', 'SYSTEM_PROMPT')
                    system_prompt = system_prompt_template.format(
                        current_date=now.strftime('%B %d, %Y'),
                        current_year=now.year
                    )

                    # Log the prompt
                    logger.info(f"=== INSTAGRAM CAPTION GENERATION PROMPT ===")
                    logger.info(f"Keywords: {keywords}")
                    logger.info(f"Content Description: {content_description[:100] if content_description else 'None'}...")
                    logger.info("=== END PROMPT ===")

                    # Generate using AI provider
                    import asyncio

                    async def _call_ai_async():
                        """Wrapper to call async AI in thread pool"""
                        return await ai_provider.create_completion_async(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.9,
                            max_tokens=7000
                        )

                    # Run async call
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        response = loop.run_until_complete(_call_ai_async())
                    finally:
                        loop.close()

                    # Extract captions from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    captions = self._parse_ai_response(response_content)

                    # Get actual token usage from AI provider response
                    token_usage = response.get('usage', {}) if isinstance(response, dict) else {}

                    return {
                        'success': True,
                        'captions': captions,
                        'used_ai': True,
                        'token_usage': token_usage
                    }

                except Exception as ai_error:
                    logger.error(f"AI generation error: {str(ai_error)}")
                    return {
                        'success': False,
                        'error': f'AI generation failed: {str(ai_error)}',
                        'captions': []
                    }

            # Fallback if no AI provider
            return {
                'success': False,
                'error': 'AI provider not available',
                'captions': []
            }

        except Exception as e:
            logger.error(f"Error in caption generation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'captions': []
            }

    def _build_prompt(self, keyword_list: List[str], content_description: str) -> str:
        """Build the prompt for caption generation"""
        try:
            # Load user prompt template
            user_prompt_template = load_prompt('prompts.txt', 'USER_PROMPT')

            # Format keywords
            keywords_str = ', '.join(keyword_list)

            # Format the prompt
            prompt = user_prompt_template.format(
                keywords=keywords_str,
                content_description=content_description if content_description else "No additional description provided."
            )

            return prompt

        except Exception as e:
            logger.error(f"Error building prompt: {str(e)}")
            raise

    def _parse_ai_response(self, response_text: str) -> List[Dict]:
        """Parse AI response and extract captions"""
        try:
            captions = []

            # Try to find JSON in response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                    if isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict) and 'caption' in item:
                                # New format: caption includes hashtags
                                captions.append({
                                    'caption': item.get('caption', '')
                                })
                        if captions:
                            logger.info(f"Parsed {len(captions)} captions from JSON")
                            return captions
                except json.JSONDecodeError:
                    pass

            # Fallback: Parse text format (each line is a caption)
            lines = response_text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Skip lines that look like headers or markers
                if line.startswith('Caption') or line.startswith('**Caption') or line.startswith('---'):
                    continue

                # If line contains hashtags, it's likely a caption
                if '#' in line:
                    # Remove any numbering (1., 2., etc.)
                    clean_line = re.sub(r'^\d+[\.\)]\s*', '', line)
                    clean_line = clean_line.strip('"\'')
                    if clean_line:
                        captions.append({'caption': clean_line})

            logger.info(f"Parsed {len(captions)} captions from text")
            return captions

        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return []
