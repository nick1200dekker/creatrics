"""
Thumbnail Analyzer using Claude Vision
Analyzes YouTube thumbnails for optimization recommendations
"""
import logging
from pathlib import Path
import requests
import base64
from typing import Dict
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider
from app.system.credits.credits_manager import CreditsManager


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
logger = logging.getLogger(__name__)

class ThumbnailAnalyzer:
    """Analyzes video thumbnails using Claude Vision"""

    def analyze_thumbnail(self, thumbnail_url: str, video_title: str, user_id: str, user_subscription: str = None) -> Dict:
        """
        Analyze a thumbnail using Claude Vision

        Args:
            thumbnail_url: URL to the thumbnail image
            video_title: Video title for context
            user_id: User ID for credit deduction

        Returns:
            Dict with analysis results
        """
        try:
            logger.info(f"Starting thumbnail analysis for video: {video_title}")
            logger.info(f"Thumbnail URL: {thumbnail_url}")

            ai_provider = get_ai_provider(
                script_name='optimize_video/thumbnail_analyzer',
                user_subscription=user_subscription
            )
            if not ai_provider:
                logger.error("AI provider not available for thumbnail analysis")
                return {'success': False, 'error': 'AI provider not available'}

            logger.info("Downloading thumbnail...")

            # Download thumbnail image
            try:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                image_data = response.content
                logger.info(f"Thumbnail downloaded successfully, size: {len(image_data)} bytes")
            except Exception as e:
                logger.error(f"Error downloading thumbnail: {e}")
                return {'success': False, 'error': 'Failed to download thumbnail'}

            # Prepare prompt for Claude Vision
            now = datetime.now()
            prompt_template = load_prompt('analyze_thumbnail.txt')
            prompt = prompt_template.format(
                video_title=video_title,
                current_date=now.strftime('%B %d, %Y'),
                current_year=now.year
            )

            # Use vision-capable model for analysis
            try:
                # Check if AI provider supports vision
                if hasattr(ai_provider, 'create_vision_completion'):
                    logger.info("Using vision-capable AI provider for thumbnail analysis")

                    # Convert image bytes to base64
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    image_data_uri = f"data:image/jpeg;base64,{base64_image}"

                    response = ai_provider.create_vision_completion(
                        messages_with_images=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": image_data_uri
                                        }
                                    }
                                ]
                            }
                        ],
                        temperature=0.7,
                        max_tokens=1000
                    )
                    logger.info("Vision analysis completed successfully")
                else:
                    logger.warning("AI provider does not support vision, using fallback URL method")
                    # Fallback: Send image URL directly if provider supports it
                    response = ai_provider.create_completion(
                        messages=[
                            {
                                "role": "user",
                                "content": f"{prompt}\n\nThumbnail URL: {thumbnail_url}"
                            }
                        ],
                        temperature=0.7,
                        max_tokens=1000
                    )
                    logger.info("Fallback analysis completed")

                analysis_text = response.get('content', '') if isinstance(response, dict) else str(response)
                logger.info(f"Thumbnail analysis result length: {len(analysis_text)} characters")

                # Deduct credits based on actual token usage
                credits_manager = CreditsManager()
                usage = response.get('usage', {})
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                model_name = response.get('model', None)  # Uses current AI provider model

                if input_tokens > 0 or output_tokens > 0:
                    credits_manager.deduct_llm_credits(
                        user_id,
                        model_name,
                        input_tokens,
                        output_tokens,
                        'Thumbnail analysis (vision)',
                        feature_id='optimize_video'
                    )
                    logger.info(f"Credits deducted for thumbnail analysis: {input_tokens} in / {output_tokens} out tokens")

                return {
                    'success': True,
                    'analysis': analysis_text,
                    'thumbnail_url': thumbnail_url
                }

            except Exception as e:
                logger.error(f"Error in vision analysis: {e}", exc_info=True)
                # Return basic analysis without vision
                return {
                    'success': True,
                    'analysis': f"""Thumbnail analysis for: {video_title}

**Note**: Full visual analysis is temporarily unavailable.

**General Recommendations**:
- Ensure text is large and readable on mobile devices
- Use high-contrast colors to stand out in search results
- Include human faces if possible (increases click-through rate)
- Keep the design clean and not cluttered
- Make sure the thumbnail relates directly to your title
- Test thumbnail at different sizes before uploading

**Review Your Thumbnail For**:
- Clear focal point
- Readable text (even at small sizes)
- Emotional appeal
- Brand consistency
- Mobile-friendly design""",
                    'thumbnail_url': thumbnail_url
                }

        except Exception as e:
            logger.error(f"Error analyzing thumbnail: {e}")
            return {'success': False, 'error': str(e)}
