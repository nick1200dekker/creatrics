"""
Thumbnail generation routes using Fal AI models
Supports Nano Banana and SeedDream V4 for image editing
"""

from flask import render_template, request, jsonify, g
from app.routes.thumbnail import bp
from app.system.auth.middleware import auth_required
from app.system.credits.credits_manager import CreditsManager
import logging
import base64
import fal_client
import os
from PIL import Image
import io

logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image_for_thumbnail(image_data):
    """
    Preprocess image to ensure it's in 16:9 thumbnail format.
    If the image is not 16:9, place it on a white background with correct aspect ratio.
    """
    try:
        # Open the image
        img = Image.open(io.BytesIO(image_data))

        # Convert RGBA to RGB if necessary
        if img.mode == 'RGBA':
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Target dimensions for YouTube thumbnail
        target_width = 1280
        target_height = 720
        target_ratio = target_width / target_height

        # Get current dimensions
        current_width, current_height = img.size
        current_ratio = current_width / current_height

        # Check if image is already in correct aspect ratio (with small tolerance)
        if abs(current_ratio - target_ratio) < 0.01:
            # Just resize if needed
            if current_width != target_width or current_height != target_height:
                img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            # Create a new image with white background in 16:9 ratio
            # Calculate the size to fit the image while maintaining aspect ratio
            if current_ratio > target_ratio:
                # Image is wider - fit by width
                new_width = target_width
                new_height = int(target_width / current_ratio)
            else:
                # Image is taller - fit by height
                new_height = target_height
                new_width = int(target_height * current_ratio)

            # Resize the original image
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Create white background in target dimensions
            background = Image.new('RGB', (target_width, target_height), (255, 255, 255))

            # Calculate position to center the image
            x = (target_width - new_width) // 2
            y = (target_height - new_height) // 2

            # Paste the image onto the background
            background.paste(img, (x, y))
            img = background

        # Convert back to bytes
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=95)
        return output.getvalue()

    except Exception as e:
        logger.warning(f"Could not preprocess image: {str(e)}")
        # Return original if preprocessing fails
        return image_data

@bp.route('/thumbnail')
@auth_required
def index():
    """Render the thumbnail editor page"""
    return render_template('thumbnail/index.html')

@bp.route('/thumbnail/generate', methods=['POST'])
@auth_required
def generate_thumbnail():
    """Generate thumbnail using Fal AI models"""
    try:
        user_id = g.user.get('id')

        # Get form data
        prompt = request.form.get('prompt', '').strip()
        model = request.form.get('model', 'nano-banana')  # Default to Nano Banana
        num_images = int(request.form.get('num_images', 1))  # Number of generations

        # Validate num_images
        if num_images < 1 or num_images > 4:
            num_images = 1

        if not prompt:
            return jsonify({
                'success': False,
                'error': 'Please provide a prompt'
            }), 400

        # Process uploaded images (up to 4)
        image_urls = []
        uploaded_files = request.files.getlist('images')

        if not uploaded_files or len(uploaded_files) == 0:
            return jsonify({
                'success': False,
                'error': 'Please upload at least one image'
            }), 400

        if len(uploaded_files) > 4:
            return jsonify({
                'success': False,
                'error': 'Maximum 4 images allowed'
            }), 400

        # Validate and process images
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                # In production, you'd upload these to cloud storage
                # For now, we'll convert to base64 data URLs
                image_data = file.read()

                # Preprocess image for Nano Banana to ensure 16:9 format
                if model == 'nano-banana':
                    image_data = preprocess_image_for_thumbnail(image_data)
                    # After preprocessing, it's always JPEG
                    mime_type = 'image/jpeg'
                else:
                    # For SeedDream, keep original format
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    mime_type = f'image/{ext if ext != "jpg" else "jpeg"}'

                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # Create data URL
                data_url = f'data:{mime_type};base64,{image_base64}'
                image_urls.append(data_url)
            else:
                return jsonify({
                    'success': False,
                    'error': f'Invalid file: {file.filename}'
                }), 400

        # Check credits
        credits_manager = CreditsManager()

        # Determine cost based on model and number of images
        if model == 'nano-banana':
            from app.system.credits.config import get_nano_banana_cost
            base_credits = get_nano_banana_cost()
        else:  # seeddream
            from app.system.credits.config import get_seeddream_cost
            base_credits = get_seeddream_cost()

        # Total credits needed
        required_credits = base_credits * num_images

        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return jsonify({
                'success': False,
                'error': f'Insufficient credits. Required: {required_credits}, Available: {credit_check.get("current_credits", 0):.2f}',
                'error_type': 'insufficient_credits',
                'required_credits': required_credits,
                'current_credits': credit_check.get('current_credits', 0)
            }), 402

        # Set FAL API key
        fal_client.api_key = os.getenv('FAL_API_KEY')

        # Generate thumbnail based on model
        try:
            if model == 'nano-banana':
                result = fal_client.run(
                    "fal-ai/nano-banana/edit",
                    arguments={
                        "prompt": prompt,
                        "image_urls": image_urls,
                        "num_images": num_images
                    }
                )
            else:  # seeddream
                result = fal_client.run(
                    "fal-ai/bytedance/seedream/v4/edit",
                    arguments={
                        "prompt": prompt,
                        "image_urls": image_urls,
                        "num_images": num_images,
                        "width": 1280,  # YouTube thumbnail width
                        "height": 720   # YouTube thumbnail height (16:9)
                    }
                )

            # Deduct credits (using the generic deduct method for multiple generations)
            deduction_result = credits_manager.deduct_credits(
                user_id=user_id,
                amount=required_credits,
                description=f"Thumbnail generation with {model} ({num_images} images)",
                feature_id=f"thumbnail_{model}"
            )

            if not deduction_result.get('success'):
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

            # Return result
            return jsonify({
                'success': True,
                'result': result,
                'model': model,
                'credits_used': required_credits
            })

        except Exception as api_error:
            logger.error(f"Fal AI API error: {str(api_error)}")
            return jsonify({
                'success': False,
                'error': f'Generation failed: {str(api_error)}'
            }), 500

    except Exception as e:
        logger.error(f"Error generating thumbnail: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500

@bp.route('/thumbnail/improve-prompt', methods=['POST'])
@auth_required
def improve_prompt():
    """Improve a thumbnail generation prompt using AI"""
    try:
        user_id = g.user.get('id')
        data = request.get_json()
        prompt = data.get('prompt', '').strip()
        image_data = data.get('image_data')  # First image for backward compatibility
        all_images = data.get('all_images', [])  # Legacy format
        all_images_with_types = data.get('all_images_with_types', [])  # New format with mime types

        if not prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400

        # Check credits for prompt improvement
        credits_manager = CreditsManager()

        # Prompt improvement costs 0.5 credits (with images: 1 credit per image, max 2 credits)
        if all_images_with_types:
            # Charge based on number of images (0.5 per image, max 2 credits for 4+ images)
            required_credits = min(len(all_images_with_types) * 0.5, 2.0)
        elif all_images:
            required_credits = min(len(all_images) * 0.5, 2.0)
        elif image_data:
            required_credits = 1.0
        else:
            required_credits = 0.5

        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return jsonify({
                'success': False,
                'error': f'Insufficient credits. Required: {required_credits}, Available: {credit_check.get("current_credits", 0):.2f}',
                'error_type': 'insufficient_credits',
                'required_credits': required_credits,
                'current_credits': credit_check.get('current_credits', 0)
            }), 402

        # Import the improve prompt module
        import sys
        from pathlib import Path

        # Add scripts directory to path
        scripts_dir = Path(__file__).parent.parent.parent / 'scripts' / 'thumbnail'
        sys.path.insert(0, str(scripts_dir))

        from improve_prompt import improve_editing_prompt

        # Log the number of images being processed
        if all_images_with_types:
            logger.info(f"Processing prompt improvement with {len(all_images_with_types)} images")
        elif all_images:
            logger.info(f"Processing prompt improvement with {len(all_images)} images (legacy)")
        elif image_data:
            logger.info(f"Processing prompt improvement with 1 image (legacy)")
        else:
            logger.info(f"Processing prompt improvement without images")

        # Improve the prompt
        # For now, use the first image as most AI providers don't support multiple images well
        # But we could combine/stitch them in the future
        if all_images_with_types and len(all_images_with_types) > 0:
            # Use the first image with its proper mime type
            first_image = all_images_with_types[0]
            mime_type = first_image.get('mimeType', 'image/jpeg')
            base64_data = first_image.get('base64', '')
            logger.info(f"Using image with mime type: {mime_type}")
            improved_prompt = improve_editing_prompt(prompt, base64_data, mime_type)
            image_context = f"with {len(all_images_with_types)} image(s)"
        elif all_images and len(all_images) > 0:
            # Legacy format without mime type
            improved_prompt = improve_editing_prompt(prompt, all_images[0], 'image/jpeg')
            image_context = f"with {len(all_images)} image(s)"
        elif image_data:
            # Backward compatibility
            improved_prompt = improve_editing_prompt(prompt, image_data, 'image/jpeg')
            image_context = "with image"
        else:
            improved_prompt = improve_editing_prompt(prompt)
            image_context = ""

        # Deduct credits after successful improvement
        deduction_result = credits_manager.deduct_credits(
            user_id=user_id,
            amount=required_credits,
            description=f"Prompt improvement {image_context}".strip(),
            feature_id="thumbnail_prompt_improver"
        )

        if not deduction_result.get('success'):
            logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'improved_prompt': improved_prompt,
            'credits_used': required_credits
        })

    except Exception as e:
        logger.error(f"Error improving prompt: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/thumbnail/estimate_cost', methods=['POST'])
@auth_required
def estimate_cost():
    """Estimate cost for thumbnail generation"""
    try:
        data = request.get_json()
        model = data.get('model', 'nano-banana')

        # Get cost based on model
        if model == 'nano-banana':
            from app.system.credits.config import get_nano_banana_cost
            cost = get_nano_banana_cost()
        else:  # seeddream
            from app.system.credits.config import get_seeddream_cost
            cost = get_seeddream_cost()

        # Get user's current credits
        user_id = g.user.get('id')
        credits_manager = CreditsManager()
        current_credits = credits_manager.get_user_credits(user_id)

        return jsonify({
            'success': True,
            'cost': cost,
            'current_credits': current_credits,
            'sufficient': current_credits >= cost
        })

    except Exception as e:
        logger.error(f"Error estimating cost: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500