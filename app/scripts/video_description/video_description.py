"""
Video Description Generator Module
Handles YouTube description generation for both long-form and shorts content
"""
import os
import logging
import json
from typing import Dict, Optional
from pathlib import Path
from app.system.ai_provider.ai_provider import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoDescriptionGenerator:
    """Video Description Generator with AI support"""

    def __init__(self):
        self.max_description_length = 5000  # YouTube's limit

    def get_prompt_template(self, video_type: str, reference_description: str = "") -> str:
        """Get the prompt template for description generation"""
        try:
            current_dir = Path(__file__).parent

            # Build filename based on video type
            if video_type == 'short':
                prompt_file = current_dir / 'short_description_prompt.txt'
            else:
                prompt_file = current_dir / 'long_description_prompt.txt'

            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return self.get_fallback_prompt(video_type, reference_description)

            with open(prompt_file, 'r', encoding='utf-8') as f:
                template = f.read()

            # Add reference description context if provided
            if reference_description:
                template += f"\n\nREFERENCE DESCRIPTION FOR STYLE AND LINKS:\n{reference_description}\n\nExtract and use the social links, hashtags style, and overall tone from the reference above."

            return template

        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return self.get_fallback_prompt(video_type, reference_description)

    def generate_description(self, input_text: str, video_type: str = 'long',
                           reference_description: str = "", user_id: str = None) -> Dict:
        """
        Generate YouTube description using AI

        Args:
            input_text: Video details or script
            video_type: Either 'long' or 'short'
            reference_description: Optional reference description for style/links
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated description
        """
        try:
            # Get the appropriate prompt template
            prompt_template = self.get_prompt_template(video_type, reference_description)

            # Format the prompt with user input
            prompt = prompt_template.format(input=input_text)

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # System prompt to ensure correct format
                    system_prompt = f"""You are a YouTube content strategist specializing in video descriptions.
                    Create engaging descriptions that maximize viewer retention and discoverability.
                    The description should be optimized for {'YouTube Shorts' if video_type == 'short' else 'long-form YouTube videos'}.

                    CRITICAL FORMATTING RULES:
                    - NO bold text or markdown formatting (no ** or ##)
                    - Do NOT include section headers like "HOOK:" or "OVERVIEW:"
                    - Use single asterisk (*) for bullet points only
                    - Maximum 3 hashtags at the end
                    - Keep total length under {self.max_description_length} characters
                    - Make the first 125 characters compelling as they show in search results
                    - Write naturally without formatting marks or labels

                    {"If a reference description is provided, extract and reuse the social media links, contact info, and match the overall style and tone." if reference_description else ""}"""

                    # Generate using AI provider
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        max_tokens=1500
                    )

                    # Extract description from response
                    response_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    description = self.clean_description(response_content)

                    # Ensure it fits within YouTube's limit
                    if len(description) > self.max_description_length:
                        description = description[:self.max_description_length-3] + "..."

                    return {
                        'success': True,
                        'description': description,
                        'used_ai': True,
                        'character_count': len(description),
                        'token_usage': {
                            'model': 'ai_provider',
                            'input_tokens': len(prompt.split()),  # Rough estimate
                            'output_tokens': len(description.split())  # Rough estimate
                        }
                    }

                except Exception as e:
                    logger.error(f"AI generation failed: {e}")
                    # Fall through to fallback

            # Fallback: Generate without AI
            description = self.generate_fallback_description(
                input_text, video_type, reference_description
            )

            return {
                'success': True,
                'description': description,
                'used_ai': False,
                'character_count': len(description),
                'token_usage': {
                    'model': 'fallback',
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            }

        except Exception as e:
            logger.error(f"Error generating description: {e}")
            return {
                'success': False,
                'error': str(e),
                'description': ''
            }

    def clean_description(self, description: str) -> str:
        """Clean and format the description"""
        # Remove any JSON formatting if present
        if description.strip().startswith('{') and description.strip().endswith('}'):
            try:
                data = json.loads(description)
                if 'description' in data:
                    description = data['description']
            except:
                pass

        # Clean up the description
        lines = description.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove excess whitespace but preserve intentional formatting
            cleaned = line.strip()
            if cleaned:
                cleaned_lines.append(cleaned)
            elif len(cleaned_lines) > 0 and cleaned_lines[-1]:  # Preserve single blank lines
                cleaned_lines.append('')

        return '\n'.join(cleaned_lines)

    def generate_fallback_description(self, input_text: str, video_type: str,
                                     reference_description: str = "") -> str:
        """Generate fallback description when AI is not available"""

        topic = input_text[:200] if input_text else "your topic"

        description_parts = []

        # Extract links from reference if provided
        links_section = ""
        hashtags = "#tutorial #howto #guide"

        if reference_description:
            # Try to extract social links
            lines = reference_description.split('\n')
            for i, line in enumerate(lines):
                if any(word in line.lower() for word in ['instagram', 'twitter', 'website', 'business', 'email', 'connect', 'social']):
                    # Found potential links section, extract it
                    links_section = '\n'.join(lines[i:min(i+6, len(lines))])
                    break
                if line.strip().startswith('#'):
                    # Extract hashtags style
                    hashtags = ' '.join([word for word in line.split() if word.startswith('#')][:3])

        if video_type == 'short':
            # Shorts description
            description_parts.append(f"🎬 {topic[:100]}")
            description_parts.append("")
            description_parts.append("In this short, you'll discover:")
            description_parts.append("* Key insights and tips")
            description_parts.append("* Quick solutions that work")
            description_parts.append("* Actionable advice you can use today")
            description_parts.append("")
            description_parts.append("👉 Watch till the end for the best tip!")
            description_parts.append("")
            description_parts.append("#shorts #viral #tips")

        else:
            # Long-form description
            description_parts.append(f"Welcome to this comprehensive guide on {topic[:150]}!")
            description_parts.append("")
            description_parts.append("In this video, you'll learn everything you need to know, including:")
            description_parts.append("")

            description_parts.append("📚 In this video, you'll learn:")
            description_parts.append("* Main concepts and fundamentals")
            description_parts.append("* Step-by-step instructions")
            description_parts.append("* Real-world examples")
            description_parts.append("* Common mistakes to avoid")
            description_parts.append("* Pro tips and advanced techniques")
            description_parts.append("")
            description_parts.append("This video is perfect for beginners and intermediate users who want to master this topic.")
            description_parts.append("")
            description_parts.append("💬 Don't forget to:")
            description_parts.append("* Like this video if you found it helpful")
            description_parts.append("* Subscribe for more content like this")
            description_parts.append("* Hit the bell icon to never miss an update")
            description_parts.append("* Comment below with your questions")
            description_parts.append("")
            description_parts.append(hashtags)

        # Add links section if available
        if links_section:
            description_parts.append("")
            description_parts.append(links_section)
        elif not reference_description:
            # Default links if no reference
            description_parts.append("")
            description_parts.append("🔗 Connect with us:")
            description_parts.append("Instagram: @yourchannel")
            description_parts.append("Twitter: @yourchannel")
            description_parts.append("Website: www.yourchannel.com")

        description_parts.append("")
        description_parts.append("Thanks for watching! See you in the next video 👋")

        return '\n'.join(description_parts)

    def get_fallback_prompt(self, video_type: str, reference_description: str = "") -> str:
        """Get fallback prompt if file is not found"""

        base_prompt = f"""Generate a YouTube {'Shorts' if video_type == 'short' else 'video'} description for:
        {{input}}

        Requirements:
        - Make the first 125 characters compelling (shown in search)
        - Include relevant keywords naturally
        - {'Keep it brief and punchy for Shorts' if video_type == 'short' else 'Be comprehensive but scannable'}
        - Use single asterisk (*) for bullet points only
        - Maximum 3 hashtags at the end
        - Include a clear call-to-action
        - Keep the total length under 5000 characters
        """

        if reference_description:
            base_prompt += f"\n\nUse this reference description for style and to extract social links:\n{reference_description}"

        return base_prompt