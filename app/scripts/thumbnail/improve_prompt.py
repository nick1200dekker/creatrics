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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_prompt_template():
    """Get the image editor prompt template from prompt.txt file"""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    prompt_file = script_dir / "prompt.txt"
    
    # Read the prompt template from file
    with open(prompt_file, 'r', encoding='utf-8') as f:
        template = f.read().strip()
        
    logger.info(f"Loaded prompt template from {prompt_file}")
    return template

def improve_editing_prompt(prompt_text, image_base64=None, mime_type='image/jpeg'):
    """
    Improve an editing prompt using AI Provider
    
    Args:
        prompt_text (str): The original editing prompt
        image_base64 (str): Base64 encoded image data (optional)
        mime_type (str): MIME type of the image (default: 'image/jpeg')
        
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
        ai_provider = get_ai_provider()
        
        # Create full prompt
        full_prompt = template.replace("{prompt}", prompt_text)
        
        # Prepare messages based on whether we have an image
        if image_base64 and ai_provider.config['supports_vision']:
            logger.info(f"Using vision capabilities with MIME type: {mime_type}")
            
            # Use vision capabilities if available
            messages = [
                {
                    "role": "system", 
                    "content": "You are an expert at creating prompts for AI image editing."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": full_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
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
        
        logger.info(f"Improved editing prompt using {response['provider']}: {improved_prompt[:50]}...")
        return improved_prompt
        
    except Exception as e:
        logger.error(f"Error improving prompt: {str(e)}")
        logger.error(traceback.format_exc())
        return prompt_text