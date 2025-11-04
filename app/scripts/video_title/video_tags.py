"""
Video Tags Generator Module
Handles YouTube tags generation optimized for 400-500 characters
"""
import os
import logging
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from app.system.ai_provider.ai_provider import get_ai_provider
from app.scripts.keyword_research import KeywordResearcher


# Get prompts directory (now in video_title folder)
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

class VideoTagsGenerator:
    """Video Tags Generator with AI support"""

    def __init__(self):
        self.max_tags_length = 500  # YouTube's limit
        self.optimal_min_length = 400
        self.optimal_max_length = 450
        self.max_tags_count = 20  # 15-20 tags target

    def get_prompt_template(self) -> str:
        """Get the prompt template for video tags generation"""
        try:
            return load_prompt('video_tags_prompts.txt', 'USER_PROMPT')
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return self.get_fallback_prompt()

    def generate_tags(self, input_text: str, user_id: str = None, channel_keywords: List[str] = None, user_subscription: str = None) -> Dict:
        """
        Generate YouTube tags using AI

        Args:
            input_text: Video description or script
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated tags
        """
        try:
            # Get AI provider with script-specific preferences
            ai_provider = get_ai_provider(
                script_name='video_title/video_tags',
                user_subscription=user_subscription
            )

            if ai_provider:
                try:
                    # Get current date info
                    now = datetime.now()
                    current_date = now.strftime("%B %d, %Y")
                    current_year = now.year

                    # Get the prompt template
                    prompt_template = self.get_prompt_template()

                    # Build channel keywords section
                    channel_keywords_text = ""
                    if channel_keywords and len(channel_keywords) > 0:
                        channel_keywords_text = f"""

CHANNEL KEYWORDS (Your YouTube channel's keywords):
{', '.join(channel_keywords[:15])}

IMPORTANT: These are your channel's keywords. Include 3-5 of these that are relevant to this specific video.
This helps with channel branding and ensures consistency across your content.
Only use the ones that make sense for THIS video - don't force irrelevant ones."""

                    # Format the prompt with user input and channel keywords
                    prompt = f"""{channel_keywords_text}

{prompt_template.format(
    input=input_text,
    current_date=current_date,
    current_year=current_year
)}"""

                    # System prompt to ensure correct format
                    system_prompt_template = load_prompt('video_tags_prompts.txt', 'SYSTEM_PROMPT')
                    system_prompt = system_prompt_template.format(
                        current_date=now.strftime('%B %d, %Y'),
                        current_year=now.year
                    )

                    # Generate using AI provider
                    # For tags, we need a short response (just comma-separated tags)
                    # But Google Gemini has issues with low max_tokens, so use 4096 to be safe
                    # ASYNC AI call - thread is freed during AI generation!
                    import asyncio

                    async def _call_ai_async():
                        """Wrapper to call async AI in thread pool - frees main thread!"""
                        return await ai_provider.create_completion_async(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7,
                            max_tokens=7000  # Increased to 20000 to avoid Google Gemini MAX_TOKENS errors
                        )

                    # Run async call - thread is freed via run_in_executor internally
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        response = loop.run_until_complete(_call_ai_async())
                    finally:
                        loop.close()

                    # Extract tags from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    tags = self.parse_ai_response(response_content)

                    # Optimize tags to fit within 400-500 characters
                    optimized_tags = self.optimize_tags_length(tags)

                    # Get actual token usage from AI provider response
                    token_usage = response.get('usage', {}) if isinstance(response, dict) else {}

                    return {
                        'success': True,
                        'tags': optimized_tags,
                        'used_ai': True,
                        'total_characters': sum(len(tag) for tag in optimized_tags) + (len(optimized_tags) - 1) * 2,  # Include commas
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
            tags = self.generate_fallback_tags(input_text)
            optimized_tags = self.optimize_tags_length(tags)

            return {
                'success': True,
                'tags': optimized_tags,
                'used_ai': False,
                'total_characters': sum(len(tag) for tag in optimized_tags) + (len(optimized_tags) - 1) * 2,
                'token_usage': {
                    'model': 'fallback',
                    'input_tokens': 0,
                    'output_tokens': 0,
                            'provider_enum': response.get('provider_enum') if isinstance(response, dict) else None
                }
            }

        except Exception as e:
            logger.error(f"Error generating tags: {e}")
            return {
                'success': False,
                'error': str(e),
                'tags': []
            }

    def parse_ai_response(self, response: str) -> List[str]:
        """Parse AI response to extract tags"""
        try:
            # Try to extract JSON array first
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                try:
                    tags = json.loads(json_match.group())
                    if isinstance(tags, list):
                        # Clean and filter tags
                        return [self.clean_tag(tag) for tag in tags if tag]
                except:
                    pass

            # Split by commas or newlines
            if ',' in response:
                tags = response.split(',')
            else:
                tags = response.split('\n')

            # Clean and filter tags
            cleaned_tags = []
            for tag in tags:
                # Remove common prefixes like "1.", "•", "-", "#"
                cleaned = re.sub(r'^[\d\.\-\•\*\#]+\s*', '', tag.strip())
                # Remove quotes
                cleaned = cleaned.strip('"\'')
                # Remove extra spaces
                cleaned = ' '.join(cleaned.split())

                if cleaned and len(cleaned) > 2:
                    cleaned_tags.append(cleaned)

            return cleaned_tags[:20]  # Limit to 20 tags max

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return self.generate_fallback_tags("")

    def clean_tag(self, tag: str) -> str:
        """Clean a single tag"""
        # Remove hashtags
        tag = tag.replace('#', '')
        # Remove extra spaces
        tag = ' '.join(tag.split())
        # Strip quotes
        tag = tag.strip('"\'')
        return tag.strip()

    def optimize_tags_length(self, tags: List[str]) -> List[str]:
        """Optimize tags to fit within 450 characters AND max 15 tags"""
        if not tags:
            return []

        # Calculate current total length
        def calculate_total_length(tag_list):
            if not tag_list:
                return 0
            # Join with ", " separator
            return len(', '.join(tag_list))

        # First, enforce max tag count
        tags = tags[:self.max_tags_count]

        current_length = calculate_total_length(tags)

        # If already in optimal range, return as is
        if self.optimal_min_length <= current_length <= self.optimal_max_length:
            return tags

        # If too long, remove tags from the end
        if current_length > self.optimal_max_length:
            optimized = []
            for tag in tags:
                test_list = optimized + [tag]
                if calculate_total_length(test_list) <= self.optimal_max_length:
                    optimized.append(tag)
                else:
                    break
            return optimized

        # If too short, just return what we have - AI knows best
        # Don't add generic filler tags
        return tags

    def generate_fallback_tags(self, input_text: str) -> List[str]:
        """Generate fallback tags when AI is not available"""
        # Common YouTube tags (multi-word phrases only - no single words)
        base_tags = [
            'how to', 'step by step', 'complete guide', 'for beginners',
            'tips and tricks', 'best practices', 'must watch',
            'quick tutorial', 'pro tips', 'expert advice'
        ]

        # Extract multi-word phrases from input (bigrams and trigrams)
        if input_text:
            words = input_text.lower().split()
            # Create bigrams (2-word phrases)
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"
                # Only add if both words are meaningful (3+ chars, alphabetic)
                if len(words[i]) >= 3 and len(words[i+1]) >= 3 and words[i].isalpha() and words[i+1].isalpha():
                    if phrase not in base_tags:
                        base_tags.insert(0, phrase)  # Add content-specific phrases first

        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in base_tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        return unique_tags[:25]  # Return up to 25 tags

    def get_fallback_prompt(self) -> str:
        """Get fallback prompt if file is not found"""
        now = datetime.now()
        return f"""Generate YouTube tags for the following video content:

        IMPORTANT: Current date is {now.strftime('%B %d, %Y')}. Use current and relevant time references.

        {{input}}

        Requirements:
        - Generate 20-30 relevant tags
        - Include a mix of broad and specific tags
        - Include trending keywords when relevant
        - Tags should help with SEO and discoverability
        - Total character count should be between 400-500 characters
        - Return as comma-separated list
        - Use {now.year} for any year references, not past years

        Focus on:
        - Main topic keywords
        - Related topics
        - Target audience terms
        - Trending hashtags (without the # symbol)
        - Long-tail keywords
        - Category-specific terms"""