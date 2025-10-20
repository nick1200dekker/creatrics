"""
TikTok Hook Generator Module
Handles powerful hook generation for TikTok videos to capture attention and keep viewers watching
"""
import os
import logging
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from app.system.ai_provider.ai_provider import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

class TikTokHookGenerator:
    """TikTok Hook Generator with AI support"""

    def __init__(self):
        pass

    def get_prompt_template(self) -> str:
        """Get the prompt template for hook generation"""
        try:
            return load_prompt('prompts.txt', 'USER_PROMPT')
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            raise

    def generate_hooks(self, content: str, user_id: str = None) -> Dict:
        """
        Generate TikTok hooks using AI

        Args:
            content: Video script, concept, or content idea
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated hooks
        """
        try:
            # Get the prompt template
            prompt_template = self.get_prompt_template()

            # Format the prompt with user content
            prompt = prompt_template.format(content=content)

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # Load system prompt from file and format it
                    system_prompt_template = load_prompt('prompts.txt', 'SYSTEM_PROMPT')
                    system_prompt = system_prompt_template.format(
                        current_date=now.strftime('%B %d, %Y'),
                        current_year=now.year
                    )

                    # Generate using AI provider
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.9,
                        max_tokens=1000
                    )

                    # Extract hooks from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    logger.info(f"AI response content preview: {response_content[:200]}...")
                    hooks = self.parse_ai_response(response_content)

                    # Get actual token usage from AI provider response
                    token_usage = response.get('usage', {}) if isinstance(response, dict) else {}

                    return {
                        'success': True,
                        'hooks': hooks,
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
            hooks = self.generate_fallback_hooks(content)

            return {
                'success': True,
                'hooks': hooks,
                'used_ai': False,
                'token_usage': {
                    'model': 'fallback',
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            }

        except Exception as e:
            logger.error(f"Error generating hooks: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'hooks': []
            }

    def parse_ai_response(self, response: str) -> List[Dict]:
        """Parse AI response to extract hooks with emotions"""
        try:
            # Try to extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                try:
                    hooks_data = json.loads(json_match.group())
                    if isinstance(hooks_data, list) and len(hooks_data) > 0:
                        # Check if it's already in the format with emotions
                        if isinstance(hooks_data[0], dict):
                            return self.ensure_ten_hooks(hooks_data)
                        else:
                            # Old format - just strings, need to add default emotions
                            hooks_with_emotions = []
                            for hook in hooks_data:
                                if isinstance(hook, str):
                                    hooks_with_emotions.append({
                                        'hook': hook,
                                        'emotion': 'Curiosity'
                                    })
                            return self.ensure_ten_hooks(hooks_with_emotions)
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON decode error: {je}. Falling back to line parsing.")

            # Fallback: Parse line by line
            lines = response.split('\n')
            hooks = []
            for line in lines:
                # Remove common prefixes like "1.", "•", "-"
                cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line.strip())
                # Remove quotes
                cleaned = cleaned.strip('"\'')
                if cleaned and len(cleaned) > 5:
                    hooks.append({
                        'hook': cleaned,
                        'emotion': 'Curiosity'
                    })

            if len(hooks) > 0:
                return self.ensure_ten_hooks(hooks)
            else:
                # If we still have nothing, use fallback
                logger.warning("No hooks parsed from AI response, using fallback")
                return self.generate_fallback_hooks("")

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return self.generate_fallback_hooks("")

    def ensure_ten_hooks(self, hooks: List[Dict]) -> List[Dict]:
        """Ensure we have exactly 10 hooks with emotions"""
        # Remove empty or too short hooks
        if hooks and len(hooks) > 0 and isinstance(hooks[0], dict):
            hooks = [h for h in hooks if h.get('hook') and len(h.get('hook', '')) > 5]
        elif not hooks:
            hooks = []

        # If we have more than 10, take the first 10
        if len(hooks) > 10:
            return hooks[:10]

        # If we have less than 10, add generic ones
        while len(hooks) < 10:
            index = len(hooks) + 1
            hooks.append({
                'hook': f"Wait until you see what happens next... #{index}",
                'emotion': 'Curiosity'
            })

        return hooks

    def generate_fallback_hooks(self, content: str) -> List[Dict]:
        """Generate fallback hooks when AI is not available"""
        # Extract key terms from content
        words = content.split()[:10] if content else []
        topic = ' '.join(words[:3]) if len(words) >= 3 else content[:30] if content else "this"

        return [
            {'hook': f"POV: You discover {topic}", 'emotion': 'Curiosity'},
            {'hook': f"Wait for it... {topic}", 'emotion': 'Anticipation'},
            {'hook': f"This {topic} changed everything for me", 'emotion': 'Surprise'},
            {'hook': f"Nobody talks about {topic}", 'emotion': 'Exclusivity'},
            {'hook': f"You've been doing {topic} wrong", 'emotion': 'Shock'},
            {'hook': f"STOP scrolling! You need to see {topic}", 'emotion': 'Urgency'},
            {'hook': f"I tried {topic} and I'm speechless", 'emotion': 'Wonder'},
            {'hook': f"The truth about {topic} that nobody tells you", 'emotion': 'Revelation'},
            {'hook': f"Watch before {topic} gets deleted", 'emotion': 'FOMO'},
            {'hook': f"This is why {topic} went viral", 'emotion': 'Social Proof'}
        ]

