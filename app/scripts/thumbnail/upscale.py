"""
Image upscaling module using Fal AI Topaz Upscale
"""
import os
import logging
import fal_client
import base64
from typing import Optional, Dict, Any
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def upscale_image(image_data: str, mime_type: str = 'image/jpeg') -> Dict[str, Any]:
    """
    Upscale an image using Fal AI Topaz Upscale model

    Args:
        image_data: Base64 encoded image data
        mime_type: MIME type of the image

    Returns:
        Dict containing the upscaled image URL and metadata
    """
    try:
        # Set FAL API key
        fal_client.api_key = os.getenv('FAL_KEY')

        if not fal_client.api_key:
            raise ValueError("FAL_KEY not found in environment variables")

        # Create data URL from base64
        data_url = f"data:{mime_type};base64,{image_data}"

        logger.info("Starting image upscaling with Topaz model")
        logger.debug(f"Data URL length: {len(data_url)}")
        logger.debug(f"Mime type: {mime_type}")

        # Run the upscaling model
        result = fal_client.run(
            "fal-ai/topaz/upscale/image",
            arguments={
                "image_url": data_url
            }
        )

        logger.info("Image upscaling completed successfully")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result: {result}")

        return {
            'success': True,
            'result': result,
            'model': 'topaz-upscale'
        }

    except Exception as e:
        logger.error(f"Error upscaling image: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def upscale_from_url(image_url: str) -> Dict[str, Any]:
    """
    Upscale an image from a URL using Fal AI Topaz Upscale model

    Args:
        image_url: URL of the image to upscale

    Returns:
        Dict containing the upscaled image URL and metadata
    """
    try:
        # Set FAL API key
        fal_client.api_key = os.getenv('FAL_KEY')

        if not fal_client.api_key:
            raise ValueError("FAL_KEY not found in environment variables")

        logger.info(f"Starting image upscaling from URL: {image_url}")

        # Run the upscaling model
        result = fal_client.run(
            "fal-ai/topaz/upscale/image",
            arguments={
                "image_url": image_url
            }
        )

        logger.info("Image upscaling from URL completed successfully")

        return {
            'success': True,
            'result': result,
            'model': 'topaz-upscale'
        }

    except Exception as e:
        logger.error(f"Error upscaling image from URL: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }