"""
Video Description Generator Module
Handles YouTube description generation for both long-form and shorts content
"""
import os
import logging
import json
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider
from app.scripts.keyword_research import KeywordResearcher

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
                return self.get_fallback_prompt(video_type, reference_description, style_analysis)

            with open(prompt_file, 'r', encoding='utf-8') as f:
                template = f.read()

            # Add reference description context if provided
            if reference_description:
                template += f"\n\nREFERENCE DESCRIPTION FOR STYLE AND LINKS:\n{reference_description}\n\nExtract and use the social links, hashtags style, and overall tone from the reference above."

            return template

        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return self.get_fallback_prompt(video_type, reference_description, style_analysis)

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
            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Get current date for system prompt
                    now = datetime.now()

                    # STEP 1: Research keywords (small AI call + free API calls)
                    logger.info("Researching YouTube keywords for description...")
                    keyword_researcher = KeywordResearcher()
                    keyword_data = keyword_researcher.research_keywords(input_text, ai_provider)
                    keyword_prompt = keyword_researcher.format_for_prompt(keyword_data)

                    # Get the appropriate prompt template
                    prompt_template = self.get_prompt_template(video_type, reference_description)

                    # STEP 2: Format the prompt with user input AND keywords
                    prompt = f"""{keyword_prompt}

{prompt_template.format(input=input_text)}"""

                    # System prompt to ensure correct format
                    system_prompt = f"""You are a YouTube content strategist specializing in video descriptions.
                    Create engaging descriptions that maximize viewer retention and discoverability.
                    The description should be optimized for {'YouTube Shorts' if video_type == 'short' else 'long-form YouTube videos'}.

                    Current date: {now.strftime('%B %d, %Y')}. Current year: {now.year}. Always use current and up-to-date references.

                    IMPORTANT: Use {now.year} for any year references, not past years like 2024.

                    KEYWORD INTEGRATION (CRITICAL):
                    - Researched keywords are provided - these are REAL searches people use on YouTube
                    - MUST include 2-3 of the most relevant keywords in the FIRST 125 CHARACTERS
                    - First 125 characters are shown in search results - make them keyword-rich AND compelling
                    - Naturally incorporate remaining keywords throughout the description where they make sense
                    - Do NOT force keywords where they don't fit naturally

                    CRITICAL FORMATTING RULES:
                    - NO bold text or markdown formatting (no ** or ##)
                    - Do NOT include section headers like "HOOK:" or "OVERVIEW:"
                    - Use single asterisk (*) for bullet points only
                    - Maximum 3 hashtags at the end
                    - Keep total length under {self.max_description_length} characters
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
                input_text, video_type, reference_description, style_analysis
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

    def create_style_instructions(self, style_analysis: Dict) -> str:
        """Create detailed style instructions from analysis"""
        if not style_analysis:
            return "Write in a clear, engaging style."

        instructions = []

        # Sentence structure
        if style_analysis.get('avg_sentence_length'):
            instructions.append(f"- Average sentence length: {style_analysis['avg_sentence_length']} words")
            instructions.append(f"- Sentence length variation: {style_analysis.get('sentence_variation', 'moderate')}")

        # Vocabulary
        instructions.append(f"- Vocabulary complexity: {style_analysis.get('vocab_complexity', 'moderate')}")

        # Emojis
        emoji_freq = style_analysis.get('emoji_frequency', 'none')
        if emoji_freq != 'none':
            instructions.append(f"- Emoji usage: {emoji_freq}")
            if style_analysis.get('emoji_list'):
                instructions.append(f"- Common emojis: {' '.join(style_analysis['emoji_list'][:5])}")

        # Capitalization
        instructions.append(f"- Capitalization style: {style_analysis.get('caps_style', 'standard')}")

        # Punctuation
        instructions.append(f"- Punctuation style: {style_analysis.get('punctuation_style', 'standard')}")

        # Formality
        instructions.append(f"- Tone formality: {style_analysis.get('formality', 'balanced')}")

        # Special patterns
        if style_analysis.get('has_timestamps'):
            instructions.append("- Include timestamps for sections")
        if style_analysis.get('uses_bullets'):
            instructions.append("- Use bullet points for lists")
        if style_analysis.get('uses_arrows'):
            instructions.append("- Use arrow symbols for emphasis")

        # Common phrases
        if style_analysis.get('common_phrases'):
            instructions.append(f"- Use these phrases: {', '.join(style_analysis['common_phrases'])}")

        instructions.append(f"- Line break frequency: {style_analysis.get('line_break_frequency', 'moderate')}")

        return '\n'.join(instructions)

    def create_system_style_instructions(self, style_analysis: Dict) -> str:
        """Create system-level style instructions for the AI"""
        if not style_analysis:
            return ""

        instructions = []

        # Sentence length guidance
        avg_length = style_analysis.get('avg_sentence_length', 15)
        if avg_length < 10:
            instructions.append("- Keep sentences SHORT and PUNCHY (under 10 words average)")
        elif avg_length > 20:
            instructions.append("- Use LONGER, more detailed sentences (20+ words average)")
        else:
            instructions.append("- Use medium-length sentences (10-20 words average)")

        # Vocabulary guidance
        vocab = style_analysis.get('vocab_complexity', 'moderate')
        if vocab == 'simple':
            instructions.append("- Use SIMPLE, everyday words - avoid complex vocabulary")
        elif vocab == 'complex':
            instructions.append("- Use sophisticated vocabulary and technical terms")

        # Emoji guidance
        emoji_freq = style_analysis.get('emoji_frequency', 'none')
        if emoji_freq == 'heavy':
            emojis = style_analysis.get('emoji_list', [])
            instructions.append(f"- Use LOTS of emojis throughout (like: {' '.join(emojis[:5])})")
        elif emoji_freq == 'moderate':
            instructions.append("- Include some emojis for visual appeal")
        elif emoji_freq == 'light':
            instructions.append("- Use emojis sparingly")
        else:
            instructions.append("- Do NOT use emojis")

        # Capitalization guidance
        caps = style_analysis.get('caps_style', 'standard')
        if caps == 'frequent':
            instructions.append("- Use CAPS for EMPHASIS frequently")
        elif caps == 'occasional':
            instructions.append("- Occasionally use CAPS for emphasis")

        # Formality guidance
        formality = style_analysis.get('formality', 'balanced')
        if formality == 'casual':
            instructions.append("- Write VERY casually - use slang, contractions, informal language")
        elif formality == 'formal':
            instructions.append("- Maintain formal, professional tone throughout")
        else:
            instructions.append("- Balance casual friendliness with professionalism")

        # Punctuation guidance
        punct = style_analysis.get('punctuation_style', 'standard')
        if punct == 'enthusiastic':
            instructions.append("- Use exclamation points frequently! Show excitement!")
        elif punct == 'questioning':
            instructions.append("- Use questions to engage the viewer")

        return '\n'.join(instructions) if instructions else "Write naturally and engagingly."

    def generate_fallback_description(self, input_text: str, video_type: str,
                                     reference_description: str = "", style_analysis: Dict = None) -> str:
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

    def get_fallback_prompt(self, video_type: str, reference_description: str = "", style_analysis: Dict = None) -> str:
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
            if style_analysis:
                base_prompt += f"\n\nStyle Analysis:\n{self.create_style_instructions(style_analysis)}"

        return base_prompt