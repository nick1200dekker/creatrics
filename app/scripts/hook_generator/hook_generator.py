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

class TikTokHookGenerator:
    """TikTok Hook Generator with AI support"""

    def __init__(self):
        pass

    def get_prompt_template(self) -> str:
        """Get the prompt template for hook generation"""
        try:
            current_dir = Path(__file__).parent
            prompt_file = current_dir / 'hooks_prompt.txt'

            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return None

            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return None

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
            # Get the appropriate prompt template
            prompt_template = self.get_prompt_template()
            if not prompt_template:
                # Use fallback prompt
                prompt_template = self.get_fallback_prompt()

            # Format the prompt with user content
            prompt = prompt_template.format(content=content)

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # System prompt to ensure correct format
                    system_prompt = f"""You are a TikTok content expert specializing in viral hooks.
                    Current date: {now.strftime('%B %d, %Y')}. Current year: {now.year}.
                    Always return exactly 10 powerful hooks in a JSON array format.
                    Each hook should be attention-grabbing, concise, and designed to stop scrollers.
                    Focus on creating curiosity, emotion, or intrigue within the first 3 seconds.
                    IMPORTANT: Use {now.year} for any year references, not past years like 2024."""

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

                    # Calculate output tokens from hook text
                    hook_texts = [h.get('hook', '') if isinstance(h, dict) else str(h) for h in hooks]
                    output_token_estimate = len(' '.join(hook_texts).split())

                    return {
                        'success': True,
                        'hooks': hooks,
                        'used_ai': True,
                        'token_usage': {
                            'model': 'ai_provider',
                            'input_tokens': len(prompt.split()),  # Rough estimate
                            'output_tokens': output_token_estimate
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

    def get_fallback_prompt(self) -> str:
        """Get fallback prompt if file is not found"""
        return """Generate 10 powerful TikTok video hooks for the following content:
        {content}

        Each hook should:
        - Be under 10 words (ideally 3-7 words)
        - Create immediate curiosity or intrigue
        - Stop scrollers in their tracks
        - Use proven viral patterns (POV, Wait for it, This changed, Nobody talks about, etc.)
        - Be relevant to the content
        - Create an open loop that makes viewers want to keep watching

        Return ONLY a JSON array with 10 hooks, nothing else."""
