"""
Thumbnail Analyzer using Claude Vision
Analyzes YouTube thumbnails for optimization recommendations
"""
import logging
import requests
import base64
from typing import Dict
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider
from app.system.credits.credits_manager import CreditsManager

logger = logging.getLogger(__name__)

class ThumbnailAnalyzer:
    """Analyzes video thumbnails using Claude Vision"""

    def analyze_thumbnail(self, thumbnail_url: str, video_title: str, user_id: str) -> Dict:
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

            ai_provider = get_ai_provider()
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
            prompt = f"""Analyze this YouTube thumbnail for: "{video_title}"

Current date: {now.strftime('%B %d, %Y')}. Current year: {now.year}.

IMPORTANT: Viewers decide to click in 0.3 seconds. 70% watch on mobile. Be ruthlessly concise.

Give ONLY these 3 sections:

**Quick Verdict** (1-2 sentences max)
Overall impression and estimated CTR potential (Low/Medium/High)

**What Works** (2-3 bullet points max)
- Be specific: "Yellow text with black outline = max contrast" not "good colors"
- Focus on what drives clicks: emotion, benefit, curiosity

**Fix These Now** (Top 3 changes only, ordered by impact)
1. Most critical fix (what will increase clicks most)
2. Second priority
3. Third priority

Rules:
- NO ratings or star systems
- NO section headers like "Visual Impact" or "Color Scheme"
- NO long explanations
- Each bullet: max 10 words
- Think: "Will this change increase clicks?" If no, don't mention it
- Focus on mobile readability (70% of views)
- Faces with clear emotions beat everything else
- Less text = better (max 3-5 words on thumbnail)
- High contrast colors are non-negotiable

Example good fix: "Make text 40% larger for mobile"
Example bad fix: "Consider evaluating the color scheme for better brand consistency"
"""

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
                model_name = response.get('model', 'claude-3-5-sonnet-20241022')

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
