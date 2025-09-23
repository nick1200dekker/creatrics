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

logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # Get file extension
                ext = file.filename.rsplit('.', 1)[1].lower()
                mime_type = f'image/{ext if ext != "jpg" else "jpeg"}'

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

        # Determine cost based on model
        if model == 'nano-banana':
            from app.system.credits.config import get_nano_banana_cost
            required_credits = get_nano_banana_cost()
        else:  # seeddream
            from app.system.credits.config import get_seeddream_cost
            required_credits = get_seeddream_cost()

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
                        "image_urls": image_urls
                    }
                )
            else:  # seeddream
                result = fal_client.run(
                    "fal-ai/bytedance/seedream/v4/edit",
                    arguments={
                        "prompt": prompt,
                        "image_urls": image_urls
                    }
                )

            # Deduct credits
            if model == 'nano-banana':
                deduction_result = credits_manager.deduct_nano_banana_credits(
                    user_id=user_id,
                    description=f"Thumbnail generation with Nano Banana"
                )
            else:
                deduction_result = credits_manager.deduct_seeddream_credits(
                    user_id=user_id,
                    description=f"Thumbnail generation with SeedDream"
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