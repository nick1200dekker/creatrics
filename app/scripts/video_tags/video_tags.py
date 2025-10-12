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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoTagsGenerator:
    """Video Tags Generator with AI support"""

    def __init__(self):
        self.max_tags_length = 500  # YouTube's limit
        self.optimal_min_length = 400
        self.optimal_max_length = 500

    def get_prompt_template(self) -> str:
        """Get the prompt template for video tags generation"""
        try:
            current_dir = Path(__file__).parent
            prompt_file = current_dir / 'tags_prompt.txt'

            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return self.get_fallback_prompt()

            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return self.get_fallback_prompt()

    def generate_tags(self, input_text: str, user_id: str = None) -> Dict:
        """
        Generate YouTube tags using AI

        Args:
            input_text: Video description or script
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated tags
        """
        try:
            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Get current date info
                    now = datetime.now()
                    current_date = now.strftime("%B %d, %Y")
                    current_year = now.year

                    # STEP 1: Research keywords (small AI call + free API calls)
                    logger.info("Researching YouTube keywords for tags...")
                    keyword_researcher = KeywordResearcher()
                    keyword_data = keyword_researcher.research_keywords(input_text, ai_provider)
                    keyword_prompt = keyword_researcher.format_for_prompt(keyword_data)

                    # Get all researched keywords as a flat list for tags
                    researched_keywords = keyword_researcher.get_all_keywords_flat(keyword_data)

                    # Get the prompt template
                    prompt_template = self.get_prompt_template()

                    # STEP 2: Format the prompt with user input, date AND keywords
                    prompt = f"""{keyword_prompt}

{prompt_template.format(
    input=input_text,
    current_date=current_date,
    current_year=current_year
)}

IMPORTANT: Use these researched keywords as tags. They are actual YouTube searches."""

                    # System prompt to ensure correct format
                    system_prompt = f"""You are a YouTube SEO expert specializing in tag generation.
                    Current date: {now.strftime('%B %d, %Y')}. Always use current and up-to-date references.
                    Generate relevant tags that will help the video rank well in YouTube search.
                    Return tags as a comma-separated list.
                    Focus on a mix of broad and specific tags.
                    Include trending and evergreen keywords when relevant.
                    The total character count should be between 400-500 characters.
                    IMPORTANT: Use {now.year} for any year references, not past years.
                    IMPORTANT: Prioritize the researched keywords provided - these are REAL searches people use."""

                    # Generate using AI provider
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=500
                    )

                    # Extract tags from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    tags = self.parse_ai_response(response_content)

                    # Optimize tags to fit within 400-500 characters
                    optimized_tags = self.optimize_tags_length(tags)

                    return {
                        'success': True,
                        'tags': optimized_tags,
                        'used_ai': True,
                        'total_characters': sum(len(tag) for tag in optimized_tags) + (len(optimized_tags) - 1) * 2,  # Include commas
                        'token_usage': {
                            'model': 'ai_provider',
                            'input_tokens': len(prompt.split()),  # Rough estimate
                            'output_tokens': len(' '.join(tags).split())  # Rough estimate
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
                    'output_tokens': 0
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

            return cleaned_tags[:30]  # Limit to 30 tags max

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
        """Optimize tags to fit within 400-500 characters"""
        if not tags:
            return []

        # Calculate current total length
        def calculate_total_length(tag_list):
            if not tag_list:
                return 0
            # Join with ", " separator
            return len(', '.join(tag_list))

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

        # If too short, try to expand tags or add more
        if current_length < self.optimal_min_length:
            # Keep all existing tags and try to add variations
            optimized = tags.copy()

            # Add some generic relevant tags if needed
            generic_tags = [
                'youtube', 'video', 'tutorial', 'how to', 'guide',
                'tips', 'tricks', 'learn', 'best', 'top', 'amazing', 'must watch',
                'viral', 'trending', 'new', 'latest', 'explained', 'for beginners'
            ]

            for tag in generic_tags:
                if tag not in optimized:
                    test_list = optimized + [tag]
                    test_length = calculate_total_length(test_list)
                    if test_length <= self.optimal_max_length:
                        optimized.append(tag)
                        if test_length >= self.optimal_min_length:
                            break

            return optimized

        return tags

    def generate_fallback_tags(self, input_text: str) -> List[str]:
        """Generate fallback tags when AI is not available"""
        # Extract key terms from input
        words = input_text.lower().split() if input_text else []

        # Common YouTube tags
        base_tags = [
            'youtube', 'video', 'content', 'tutorial', 'guide', 'how to',
            'tips', 'tricks', 'learn', 'education',
            'entertainment', 'viral', 'trending', 'fyp', 'for you page'
        ]

        # Extract meaningful words from input (3+ characters)
        if words:
            meaningful_words = [w for w in words if len(w) > 3 and w.isalpha()][:10]
            # Add extracted words as tags
            base_tags = meaningful_words + base_tags

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