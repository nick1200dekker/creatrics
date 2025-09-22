from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_description.video_description import VideoDescriptionGenerator
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-description')
@auth_required
def video_description():
    """Video description generator page"""
    return render_template('video_description/index.html')

@bp.route('/api/generate-video-description', methods=['POST'])
@auth_required
def generate_video_description():
    """Generate video description using AI with proper credit management"""
    try:
        data = request.json
        input_text = data.get('input', '').strip()
        video_type = data.get('type', 'long')
        reference_description = data.get('reference_description', '').strip()

        if not input_text:
            return jsonify({'success': False, 'error': 'Please provide video details'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        description_generator = VideoDescriptionGenerator()

        user_id = g.user.get('id')

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=input_text,
            model_name='claude-3-sonnet-20240229'  # Default model
        )

        # Descriptions cost moderate amount (between titles and scripts)
        required_credits = cost_estimate['final_cost'] * 2  # Multiply by 2 for descriptions
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        # For free users, allow limited uses
        if not credit_check.get('sufficient', False):
            # Check if user is on free plan
            user_plan = g.user.get('subscription_plan', 'Free Plan')
            if user_plan == 'Free Plan':
                # Allow free users some limited generations
                if current_credits >= 0:  # They have at least their initial free credits
                    pass  # Allow generation
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Insufficient credits. Please upgrade to continue.",
                        "error_type": "insufficient_credits",
                        "current_credits": current_credits,
                        "required_credits": required_credits
                    }), 402
            else:
                return jsonify({
                    "success": False,
                    "error": f"Insufficient credits. Required: {required_credits:.2f}, Available: {current_credits:.2f}",
                    "error_type": "insufficient_credits",
                    "current_credits": current_credits,
                    "required_credits": required_credits
                }), 402

        # Step 2: Generate description
        generation_result = description_generator.generate_description(
            input_text=input_text,
            video_type=video_type,
            reference_description=reference_description,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Description generation failed')
            }), 500

        # Step 3: Deduct credits if AI was used
        if generation_result.get('used_ai', False):
            token_usage = generation_result.get('token_usage', {})

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', 'claude-3-sonnet-20240229'),
                    input_tokens=token_usage.get('input_tokens', 150),
                    output_tokens=token_usage.get('output_tokens', 500),
                    description=f"Video Description Generation ({video_type})"
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'description': generation_result.get('description', ''),
            'message': 'Description generated successfully',
            'character_count': generation_result.get('character_count', 0),
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Save reference description
@bp.route('/api/save-reference-description', methods=['POST'])
@auth_required
def save_reference_description():
    """Save user's reference description to Firestore"""
    try:
        from app.system.services.firebase_service import db

        if not db:
            return jsonify({'success': False, 'error': 'Database not available'}), 500

        data = request.json
        reference_description = data.get('reference_description', '').strip()

        if not reference_description:
            return jsonify({'success': False, 'error': 'No reference description provided'}), 400

        user_id = g.user.get('id')

        # Save to Firestore
        doc_ref = db.collection('users').document(user_id)
        doc_ref.update({
            'yt_reference_description': reference_description,
            'yt_reference_updated_at': firestore.SERVER_TIMESTAMP
        })

        return jsonify({
            'success': True,
            'message': 'Reference description saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving reference description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Get reference description
@bp.route('/api/get-reference-description', methods=['GET'])
@auth_required
def get_reference_description():
    """Get user's saved reference description from Firestore"""
    try:
        from app.system.services.firebase_service import db

        if not db:
            return jsonify({'success': False, 'error': 'Database not available'}), 500

        user_id = g.user.get('id')

        # Get from Firestore
        doc_ref = db.collection('users').document(user_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            reference_description = data.get('yt_reference_description', '')

            return jsonify({
                'success': True,
                'reference_description': reference_description
            })
        else:
            return jsonify({
                'success': True,
                'reference_description': ''
            })

    except Exception as e:
        logger.error(f"Error getting reference description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Legacy endpoint compatibility
@bp.route('/api/video-description/generate', methods=['POST'])
@auth_required
def generate_video_description_legacy():
    """Legacy endpoint - redirects to new endpoint"""
    return generate_video_description()