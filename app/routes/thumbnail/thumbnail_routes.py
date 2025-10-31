"""
Thumbnail generation routes using Fal AI models
Supports Nano Banana and SeedDream V4 for image editing
"""

from flask import render_template, request, jsonify, g
from app.routes.thumbnail import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.system.services.firebase_service import db
from datetime import datetime
import logging
import base64
import fal_client
import os
from PIL import Image
import io

# Import preset prompts
from app.scripts.thumbnail.canvas_presets import CANVAS_PRESETS
from app.scripts.thumbnail.photo_presets import PHOTO_PRESETS

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
@require_permission('thumbnail')
def index():
    """Render the thumbnail editor page"""
    return render_template('thumbnail/index.html',
                         canvas_presets=CANVAS_PRESETS,
                         photo_presets=PHOTO_PRESETS)

@bp.route('/thumbnail/generate', methods=['POST'])
@auth_required
@require_permission('thumbnail')
def generate_thumbnail():
    """Generate thumbnail using Fal AI models"""
    try:
        user_id = get_workspace_user_id()

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
        fal_client.api_key = os.getenv('FAL_KEY')

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
                        "image_size": {
                            "width": 1280,  # YouTube thumbnail width
                            "height": 720   # YouTube thumbnail height (16:9)
                        }
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

            # Save thumbnails to Firebase for user
            try:
                thumbnails_ref = db.collection('users').document(user_id).collection('thumbnails')
                now = datetime.utcnow().isoformat() + 'Z'

                # Extract image URLs from result
                image_urls = []
                if result.get('images'):
                    image_urls = [img.get('url', img) if isinstance(img, dict) else img for img in result['images']]
                elif result.get('image'):
                    image_urls = [result['image'].get('url', result['image']) if isinstance(result['image'], dict) else result['image']]
                elif result.get('output'):
                    image_urls = [result['output']]

                # Save each generated thumbnail to Firebase
                saved_thumbnails = []
                for img_url in image_urls:
                    thumbnail_data = {
                        'url': img_url,
                        'prompt': prompt,
                        'model': model,
                        'created_at': now,
                        'updated_at': now,
                        'credits_used': base_credits  # Credits per image
                    }
                    doc_ref = thumbnails_ref.add(thumbnail_data)
                    thumbnail_data['id'] = doc_ref[1].id
                    saved_thumbnails.append(thumbnail_data)

                logger.info(f"Saved {len(saved_thumbnails)} thumbnails for user {user_id}")
            except Exception as save_error:
                logger.error(f"Failed to save thumbnails to Firebase: {str(save_error)}")
                # Continue even if saving fails

            # Return result
            return jsonify({
                'success': True,
                'result': result,
                'model': model,
                'credits_used': required_credits
            })

        except Exception as api_error:
            logger.error(f"Fal AI API error: {str(api_error)}")
            error_message = str(api_error)

            # Check if it's a content policy violation
            if 'Gemini could not generate' in error_message or 'prompt' in error_message.lower():
                return jsonify({
                    'success': False,
                    'error': 'Your prompt was rejected by the AI safety filters. Please try rephrasing your prompt to avoid violent, dangerous, or inappropriate content.',
                    'error_type': 'content_policy_violation'
                }), 400

            return jsonify({
                'success': False,
                'error': f'Generation failed: {error_message}'
            }), 500

    except Exception as e:
        logger.error(f"Error generating thumbnail: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500

@bp.route('/thumbnail/improve-prompt', methods=['POST'])
@auth_required
@require_permission('thumbnail')
def improve_prompt():
    """Improve a thumbnail generation prompt using AI"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()
        prompt = data.get('prompt', '').strip()
        model = data.get('model', 'nano-banana')  # Get selected model
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

        # New credit structure: 0.2 base, +0.3 for 1st photo, +0.2 for each additional
        # 0 photos: 0.2, 1 photo: 0.5, 2 photos: 0.7, 3 photos: 0.9, 4 photos: 1.0
        num_images = len(all_images_with_types) if all_images_with_types else (len(all_images) if all_images else (1 if image_data else 0))

        if num_images == 0:
            required_credits = 0.2
        elif num_images == 1:
            required_credits = 0.5
        elif num_images == 2:
            required_credits = 0.7
        elif num_images == 3:
            required_credits = 0.9
        else:  # 4 or more
            required_credits = 1.0

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

        # Log the number of images being processed and model
        model_name = "Canvas Editor" if model == "nano-banana" else "Photo Editor"
        if all_images_with_types:
            logger.info(f"Processing prompt improvement for {model_name} with {len(all_images_with_types)} images")
        elif all_images:
            logger.info(f"Processing prompt improvement for {model_name} with {len(all_images)} images (legacy)")
        elif image_data:
            logger.info(f"Processing prompt improvement for {model_name} with 1 image (legacy)")
        else:
            logger.info(f"Processing prompt improvement for {model_name} without images")

        # Improve the prompt with all images
        if all_images_with_types and len(all_images_with_types) > 0:
            # Pass all images to the prompt improver
            logger.info(f"Sending {len(all_images_with_types)} image(s) to prompt improver")
            result = improve_editing_prompt(prompt, None, None, model, all_images_with_types)
            image_context = f"with {len(all_images_with_types)} image(s)"
        elif all_images and len(all_images) > 0:
            # Legacy format without mime type - convert to new format
            converted_images = []
            for img_base64 in all_images:
                converted_images.append({
                    'base64': img_base64,
                    'mimeType': 'image/jpeg'
                })
            logger.info(f"Converting {len(all_images)} legacy image(s) to new format")
            result = improve_editing_prompt(prompt, None, None, model, converted_images)
            image_context = f"with {len(all_images)} image(s)"
        elif image_data:
            # Backward compatibility - single image
            result = improve_editing_prompt(prompt, image_data, 'image/jpeg', model)
            image_context = "with image"
        else:
            result = improve_editing_prompt(prompt, None, None, model)
            image_context = ""

        # Handle both old string return and new dict return formats
        if isinstance(result, dict):
            improved_prompt = result.get('improved_prompt', prompt)
            token_usage = result.get('token_usage', {})

            # Calculate actual credits from token usage if available
            if token_usage.get('input_tokens', 0) > 0 or token_usage.get('output_tokens', 0) > 0:
                actual_credits = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    model_name=token_usage.get('model', 'ai_provider'),
                    description=f"Prompt improvement {image_context}".strip(),
                    feature_id="thumbnail_prompt_improver",
                    provider_enum=token_usage.get('provider_enum')
                )

                if actual_credits.get('success'):
                    credits_used = actual_credits.get('credits_deducted', required_credits)
                else:
                    # Fall back to fixed credits if token-based deduction fails
                    deduction_result = credits_manager.deduct_credits(
                        user_id=user_id,
                        amount=required_credits,
                        description=f"Prompt improvement {image_context}".strip(),
                        feature_id="thumbnail_prompt_improver"
                    )
                    credits_used = required_credits
            else:
                # No token usage data, use fixed credits
                deduction_result = credits_manager.deduct_credits(
                    user_id=user_id,
                    amount=required_credits,
                    description=f"Prompt improvement {image_context}".strip(),
                    feature_id="thumbnail_prompt_improver"
                )
                credits_used = required_credits
        else:
            # Old string format (backward compatibility)
            improved_prompt = result
            deduction_result = credits_manager.deduct_credits(
                user_id=user_id,
                amount=required_credits,
                description=f"Prompt improvement {image_context}".strip(),
                feature_id="thumbnail_prompt_improver"
            )
            credits_used = required_credits

        return jsonify({
            'success': True,
            'improved_prompt': improved_prompt,
            'credits_used': credits_used
        })

    except Exception as e:
        logger.error(f"Error improving prompt: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/thumbnail/upscale', methods=['POST'])
@auth_required
@require_permission('thumbnail')
def upscale_image():
    """Upscale an image using Topaz AI model"""
    try:
        user_id = get_workspace_user_id()

        # Get the image from request
        if 'image' not in request.files:
            # Check for base64 data in JSON
            data = request.get_json()
            if data and 'image_data' in data:
                image_base64 = data['image_data']
                mime_type = data.get('mime_type', 'image/jpeg')

                # Remove data URL prefix if present
                if image_base64.startswith('data:'):
                    header, image_base64 = image_base64.split(',', 1)
                    mime_type = header.split(':')[1].split(';')[0]
            else:
                return jsonify({
                    'success': False,
                    'error': 'No image provided'
                }), 400
        else:
            file = request.files['image']
            if not file or not allowed_file(file.filename):
                return jsonify({
                    'success': False,
                    'error': 'Invalid file'
                }), 400

            # Read and encode the image
            image_data = file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            ext = file.filename.rsplit('.', 1)[1].lower()
            mime_type = f'image/{ext if ext != "jpg" else "jpeg"}'

        # Check credits using configured cost
        credits_manager = CreditsManager()
        from app.system.credits.config import get_topaz_upscale_cost
        required_credits = get_topaz_upscale_cost()  # Get configured cost for upscaling

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

        # Import and use the upscale module
        import sys
        from pathlib import Path

        # Add scripts directory to path
        scripts_dir = Path(__file__).parent.parent.parent / 'scripts' / 'thumbnail'
        sys.path.insert(0, str(scripts_dir))

        from upscale import upscale_image as do_upscale

        # Perform the upscaling
        result = do_upscale(image_base64, mime_type)

        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Upscaling failed')
            }), 500

        # Deduct credits
        deduction_result = credits_manager.deduct_credits(
            user_id=user_id,
            amount=required_credits,
            description="Image upscaling with Topaz AI",
            feature_id="thumbnail_upscale"
        )

        if not deduction_result.get('success'):
            logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        # Save upscaled thumbnail to Firebase
        try:
            thumbnails_ref = db.collection('users').document(user_id).collection('thumbnails')
            now = datetime.utcnow().isoformat() + 'Z'

            # Extract upscaled image URL
            upscaled_url = None
            if result.get('result'):
                result_data = result['result']
                if isinstance(result_data, dict):
                    if result_data.get('image', {}).get('url'):
                        upscaled_url = result_data['image']['url']
                    elif result_data.get('image'):
                        upscaled_url = result_data['image']
                    elif result_data.get('url'):
                        upscaled_url = result_data['url']
                elif isinstance(result_data, str):
                    upscaled_url = result_data

            if upscaled_url:
                thumbnail_data = {
                    'url': upscaled_url,
                    'prompt': 'Upscaled Image',
                    'model': 'topaz-upscale',
                    'created_at': now,
                    'updated_at': now,
                    'credits_used': required_credits
                }
                doc_ref = thumbnails_ref.add(thumbnail_data)
                logger.info(f"Saved upscaled thumbnail for user {user_id}")
        except Exception as save_error:
            logger.error(f"Failed to save upscaled thumbnail to Firebase: {str(save_error)}")
            # Continue even if saving fails

        return jsonify({
            'success': True,
            'result': result.get('result'),
            'credits_used': required_credits
        })

    except Exception as e:
        logger.error(f"Error upscaling image: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/thumbnail/history', methods=['GET'])
@auth_required
@require_permission('thumbnail')
def get_thumbnail_history():
    """Get thumbnail generation history for the current user"""
    try:
        user_id = get_workspace_user_id()

        # Get user's thumbnails from Firebase
        thumbnails_ref = db.collection('users').document(user_id).collection('thumbnails')

        # Query with ordering and limit
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # Get thumbnails ordered by creation date (newest first)
        query = thumbnails_ref.order_by('created_at', direction='DESCENDING')

        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)

        thumbnails_docs = query.stream()

        # Convert to list
        thumbnails = []
        for doc in thumbnails_docs:
            thumbnail_data = doc.to_dict()
            thumbnail_data['id'] = doc.id
            thumbnails.append(thumbnail_data)

        # Get total count
        total_count = len(list(thumbnails_ref.stream()))

        return jsonify({
            'success': True,
            'thumbnails': thumbnails,
            'total': total_count,
            'limit': limit,
            'offset': offset
        })

    except Exception as e:
        logger.error(f"Error fetching thumbnail history: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch thumbnail history'
        }), 500

@bp.route('/thumbnail/history/<thumbnail_id>', methods=['DELETE'])
@auth_required
@require_permission('thumbnail')
def delete_thumbnail(thumbnail_id):
    """Delete a specific thumbnail from user's history"""
    try:
        user_id = get_workspace_user_id()

        # Get thumbnail reference
        thumbnail_ref = db.collection('users').document(user_id).collection('thumbnails').document(thumbnail_id)

        # Check if thumbnail exists
        thumbnail_doc = thumbnail_ref.get()
        if not thumbnail_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Thumbnail not found'
            }), 404

        # Delete the thumbnail
        thumbnail_ref.delete()

        logger.info(f"Deleted thumbnail {thumbnail_id} for user {user_id}")

        return jsonify({
            'success': True,
            'message': 'Thumbnail deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting thumbnail: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete thumbnail'
        }), 500

@bp.route('/thumbnail/estimate_cost', methods=['POST'])
@auth_required
@require_permission('thumbnail')
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
        user_id = get_workspace_user_id()
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