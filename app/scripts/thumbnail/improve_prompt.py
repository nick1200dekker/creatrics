"""
Enhanced Prompt Improvement Module for Image Editor
Uses AI Provider for multi-provider support
"""
import os
import logging
import traceback
import base64
from pathlib import Path
from dotenv import load_dotenv
from app.system.ai_provider.ai_provider import get_ai_provider


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
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_prompt_template():
    """Get the image editor prompt template from prompt.txt file"""
    # Load the prompt template from prompts directory
    template = load_prompt('prompt.txt')
    logger.info("Loaded prompt template from prompts/prompt.txt")
    return template

def improve_editing_prompt(prompt_text, image_base64=None, mime_type='image/jpeg', model='nano-banana', all_images_with_types=None, user_subscription=None):
    """
    Improve an editing prompt using AI Provider

    Args:
        prompt_text (str): The original editing prompt
        image_base64 (str): Base64 encoded image data (optional, for backward compatibility)
        mime_type (str): MIME type of the image (default: 'image/jpeg')
        model (str): The selected model ('nano-banana' for Canvas Editor or 'seeddream' for Photo Editor)
        all_images_with_types (list): List of dicts with 'base64' and 'mimeType' keys for multiple images

    Returns:
        str: Improved prompt or original prompt if error
    """
    try:
        # Clean the prompt text
        prompt_text = prompt_text.strip() if prompt_text else ""
        
        if not prompt_text:
            prompt_text = "analyze the image and suggest interesting edits"
        
        # Get template from file
        template = get_prompt_template()

        # Get AI provider
        ai_provider = get_ai_provider(
                script_name='thumbnail/improve_prompt',
                user_subscription=user_subscription
            )

        # Add model context to the template
        model_name = "Canvas Editor (nano-banana)" if model == "nano-banana" else "Photo Editor (seeddream)"
        template = template.replace("{model}", model_name)

        # Create full prompt
        full_prompt = template.replace("{prompt}", prompt_text)
        
        # Prepare messages based on whether we have images
        images_to_process = []

        # Handle multiple images if provided
        if all_images_with_types and len(all_images_with_types) > 0:
            for img_data in all_images_with_types:
                base64_data = img_data.get('base64', '')
                img_mime_type = img_data.get('mimeType', 'image/jpeg')

                # Detect actual MIME type from the base64 data
                import base64 as b64
                try:
                    image_bytes = b64.b64decode(base64_data[:100])  # Check first bytes
                    if image_bytes.startswith(b'\x89PNG'):
                        actual_mime = 'image/png'
                    elif image_bytes.startswith(b'\xff\xd8\xff'):
                        actual_mime = 'image/jpeg'
                    elif image_bytes.startswith(b'GIF8'):
                        actual_mime = 'image/gif'
                    elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:20]:
                        actual_mime = 'image/webp'
                    else:
                        actual_mime = img_mime_type
                except:
                    actual_mime = img_mime_type

                images_to_process.append({
                    'base64': base64_data,
                    'mime_type': actual_mime
                })
        # Fall back to single image for backward compatibility
        elif image_base64:
            images_to_process.append({
                'base64': image_base64,
                'mime_type': mime_type
            })

        if images_to_process and ai_provider.config['supports_vision']:
            logger.info(f"Using vision capabilities with {len(images_to_process)} image(s)")

            # Build content array with text and all images
            user_content = [
                {
                    "type": "text",
                    "text": full_prompt
                }
            ]

            # Add all images to the content
            for img in images_to_process:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['mime_type']};base64,{img['base64']}",
                        "detail": "high"
                    }
                })

            # Use vision capabilities if available
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert at creating prompts for AI image editing."
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]

            # Use vision completion
            response = ai_provider.create_vision_completion(
                messages,
                temperature=0.7,
                max_tokens=200
            )
        else:
            # Text-only completion
            messages = [
                {"role": "system", "content": "You are an expert at creating prompts for AI image editing."},
                {"role": "user", "content": full_prompt}
            ]
            
            response = ai_provider.create_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
        
        # Extract improved prompt from unified response
        improved_prompt = response['content'].strip()

        # Get token usage from response
        token_usage = response.get('usage', {})

        logger.info(f"Improved editing prompt using {response['provider']}: {improved_prompt[:50]}...")

        # Return both prompt and token usage
        return {
            'improved_prompt': improved_prompt,
            'token_usage': {
                'model': response.get('model', 'ai_provider'),
                'input_tokens': token_usage.get('input_tokens', 0),
                'output_tokens': token_usage.get('output_tokens', 0),
                'provider_enum': response.get('provider_enum'),
                'provider': response.get('provider', 'unknown')
            }
        }

    except Exception as e:
        logger.error(f"Error improving prompt: {str(e)}")
        logger.error(traceback.format_exc())
        # Return in same format for consistency
        return {
            'improved_prompt': prompt_text,
            'token_usage': {
                'model': 'fallback',
                'input_tokens': 0,
                'output_tokens': 0,
                'provider': 'error'
            }
        }