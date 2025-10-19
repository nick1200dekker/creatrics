"""
TikTok Trend Finder AI Processor
Handles AI operations for filtering gaming-related keywords
"""
import logging
from pathlib import Path
from app.system.ai_provider.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)

# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'


def load_prompt(filename: str) -> str:
    """Load a prompt from text file"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        raise


def filter_gaming_keywords_ai(keywords: list) -> list:
    """
    Use AI to filter gaming-related keywords from the list
    Uses the unified AI provider system (same as YouTube Keyword Research)
    """
    try:
        # Create keywords text
        keywords_text = "\n".join(keywords)

        # Load prompts from files
        system_prompt = load_prompt('filter_gaming_keywords_system.txt')
        user_prompt_template = load_prompt('filter_gaming_keywords.txt')
        user_prompt = user_prompt_template.format(keywords_text=keywords_text)

        # Use unified AI provider system
        ai_provider = get_ai_provider()

        logger.info(f"Using {ai_provider.provider.value} for AI filtering")

        # Create completion using unified interface
        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        # Parse response - split by newlines and filter empty
        response_text = response.get('content', '')
        gaming_keywords = [k.strip() for k in response_text.split('\n') if k.strip()]

        # Validate keywords are from original list (no modifications)
        valid_keywords = [k for k in gaming_keywords if k in keywords]

        logger.info(f"AI filtered: {len(keywords)} -> {len(valid_keywords)} gaming keywords")

        return valid_keywords

    except Exception as e:
        logger.error(f"Error filtering with AI: {e}")
        # Fallback: return all keywords if AI fails
        logger.warning("AI filtering failed, returning all keywords as fallback")
        return keywords
