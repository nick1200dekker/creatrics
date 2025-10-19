"""
Video Title Generator Module
Handles YouTube title generation for both long-form and shorts content
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

class VideoTitleGenerator:
    """Video Title Generator with AI support"""

    def __init__(self):
        self.prompt_types = ['long_form', 'shorts']

    def get_prompt_template(self, video_type: str) -> str:
        """Get the prompt template for video title generation"""
        try:
            current_dir = Path(__file__).parent
            prompt_file = current_dir / f'{video_type}_prompt.txt'

            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return None

            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return None

    def generate_titles(self, user_input: str, video_type: str = 'long_form',
                       user_id: str = None) -> Dict:
        """
        Generate YouTube titles using AI

        Args:
            user_input: Video description or script
            video_type: Either 'long_form' or 'shorts'
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated titles
        """
        try:
            # Validate video type
            if video_type not in ['long_form', 'shorts']:
                video_type = 'long_form'

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # Get the appropriate prompt template
                    prompt_template = self.get_prompt_template(video_type)
                    if not prompt_template:
                        # Use fallback prompt
                        prompt_template = self.get_fallback_prompt(video_type)

                    # Format the prompt with user input
                    prompt = prompt_template.format(input=user_input)

                    # System prompt to ensure correct format
                    system_prompt = f"""You are a YouTube title generation expert.
                    Current date: {now.strftime('%B %d, %Y')}. Current year: {now.year}. Always use current and up-to-date references.
                    Always return exactly 10 titles in a JSON array format.
                    For shorts, always include 3 hashtags at the end of each title.
                    IMPORTANT: Use {now.year} for any year references, not past years like 2024."""

                    # Log the complete prompt being sent
                    logger.info(f"=== COMPLETE PROMPT TO AI ({video_type}) ===")
                    logger.info(f"SYSTEM PROMPT:\n{system_prompt}")
                    logger.info(f"\nUSER PROMPT:\n{prompt}")
                    logger.info("=== END PROMPT ===")

                    # Generate using AI provider
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.9,
                        max_tokens=800
                    )

                    # Extract titles from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    titles = self.parse_ai_response(response_content, video_type)

                    # Get actual token usage from AI provider response
                    token_usage = response.get('usage', {}) if isinstance(response, dict) else {}

                    return {
                        'success': True,
                        'titles': titles,
                        'used_ai': True,
                        'token_usage': {
                            'model': response.get('model', 'ai_provider') if isinstance(response, dict) else 'ai_provider',
                            'input_tokens': token_usage.get('input_tokens', 0),
                            'output_tokens': token_usage.get('output_tokens', 0)
                        }
                    }

                except Exception as e:
                    logger.error(f"AI generation failed: {e}")
                    # Fall through to fallback

            # Fallback: Generate without AI
            titles = self.generate_fallback_titles(user_input, video_type)

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
            logger.error(f"Error generating titles: {e}")
            return {
                'success': False,
                'error': str(e),
                'titles': []
            }

    def parse_ai_response(self, response: str, video_type: str) -> List[str]:
        """Parse AI response to extract titles"""
        try:
            logger.info(f"=== AI RESPONSE DEBUG ({video_type}) ===")
            logger.info(f"Raw response (first 500 chars): {response[:500]}")

            # Try to extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                titles = json.loads(json_match.group())
                if isinstance(titles, list):
                    logger.info(f"Parsed {len(titles)} titles from JSON")
                    logger.info(f"Title 1: {titles[0] if len(titles) > 0 else 'none'}")
                    logger.info(f"Title 2: {titles[1] if len(titles) > 1 else 'none'}")
                    logger.info(f"Title 3: {titles[2] if len(titles) > 2 else 'none'}")
                    return self.ensure_ten_titles(titles, video_type)

            # Fallback: Parse line by line
            logger.info("No JSON found, parsing line by line")
            lines = response.split('\n')
            titles = []
            for line in lines:
                # Remove common prefixes like "1.", "•", "-"
                cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line.strip())
                # Remove quotes
                cleaned = cleaned.strip('"\'')
                if cleaned and len(cleaned) > 10:
                    titles.append(cleaned)

            logger.info(f"Parsed {len(titles)} titles line by line")
            if titles:
                logger.info(f"First title: {titles[0]}")
            return self.ensure_ten_titles(titles, video_type)

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return self.generate_fallback_titles("", video_type)

    def ensure_ten_titles(self, titles: List[str], video_type: str) -> List[str]:
        """Ensure we have exactly 10 titles"""
        # Remove empty or too short titles
        titles = [t for t in titles if t and len(t) > 10]

        # If we have more than 10, take the first 10
        if len(titles) > 10:
            return titles[:10]

        # If we have less than 10, add generic ones
        while len(titles) < 10:
            index = len(titles) + 1
            if video_type == 'shorts':
                titles.append(f"Amazing Content #{index} #shorts #viral #fyp")
            else:
                titles.append(f"Must-Watch Video Content #{index} - Don't Miss This!")

        return titles

    def generate_fallback_titles(self, input_text: str, video_type: str) -> List[str]:
        """Generate fallback titles when AI is not available"""
        # Extract key terms from input
        words = input_text.split()[:10] if input_text else []
        topic = ' '.join(words[:3]) if len(words) >= 3 else input_text[:30] if input_text else "Content"

        if video_type == 'shorts':
            return [
                f"POV: You discover {topic} #shorts #viral #fyp",
                f"WAIT FOR IT... {topic} #shorts #trending #amazing",
                f"This {topic} hack is GENIUS #shorts #lifehack #tips",
                f"You've been doing {topic} WRONG #shorts #mindblown #wow",
                f"The {topic} trick that went viral #shorts #viral #mustsee",
                f"60 seconds to master {topic} #shorts #howto #quick",
                f"Why nobody talks about {topic} #shorts #secret #truth",
                f"I tried {topic} and... #shorts #experiment #results",
                f"The {topic} method everyone needs #shorts #tips #useful",
                f"This changes everything: {topic} #shorts #gamechanger #new"
            ]
        else:
            return [
                f"How to Master {topic} - Complete Guide",
                f"{topic}: Everything You Need to Know (Beginner to Pro)",
                f"The Hidden Truth About {topic} Nobody Tells You",
                f"I Spent 100 Hours Learning {topic} - Here's What I Discovered",
                f"Why {topic} Will Change Your Life (Scientific Proof)",
                f"{topic} Explained: The Only Tutorial You'll Ever Need",
                f"10 Mistakes Everyone Makes with {topic} (And How to Fix Them)",
                f"The Ultimate {topic} Strategy That Actually Works",
                f"{topic} vs Everything Else: The Definitive Comparison",
                f"From Zero to Hero: My {topic} Transformation Journey"
            ]

    def get_fallback_prompt(self, video_type: str) -> str:
        """Get fallback prompt if file is not found"""
        if video_type == 'shorts':
            return """Generate 10 YouTube Shorts titles for the following content:
            {input}

            Each title should:
            - Be under 40 characters
            - Include 3 hashtags at the end
            - First hashtag should be #shorts
            - Be catchy and attention-grabbing"""
        else:
            return """Generate 10 YouTube titles for the following content:
            {input}

            Each title should:
            - Be 50-60 characters long
            - Include power words
            - Create curiosity
            - Be SEO-friendly"""