from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_tags.video_tags import VideoTagsGenerator
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-tags')
@auth_required
@require_permission('video_tags')
def video_tags():
    """Video tags generator page"""
    return render_template('video_tags/index.html')

@bp.route('/api/generate-video-tags', methods=['POST'])
@auth_required
@require_permission('video_tags')
def generate_video_tags():
    """Generate video tags using AI with proper credit management"""
    try:
        data = request.json
        input_text = data.get('input', '').strip()

        if not input_text:
            return jsonify({'success': False, 'error': 'Please provide video details'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        tags_generator = VideoTagsGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=input_text,
            model_name='claude-3-sonnet-20240229'  # Default model
        )

        # Tags cost less than scripts (shorter output)
        required_credits = cost_estimate['final_cost'] * 1.5  # Multiply by 1.5 for tags
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        # Check for sufficient credits - strict enforcement
        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": f"Insufficient credits. Required: {required_credits:.2f}, Available: {current_credits:.2f}",
                "error_type": "insufficient_credits",
                "current_credits": current_credits,
                "required_credits": required_credits
            }), 402

        # Step 2: Generate tags
        generation_result = tags_generator.generate_tags(
            input_text=input_text,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Tags generation failed')
            }), 500

        # Step 3: Deduct credits if AI was used
        if generation_result.get('used_ai', False):
            token_usage = generation_result.get('token_usage', {})

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', 'claude-3-sonnet-20240229'),
                    input_tokens=token_usage.get('input_tokens', 100),
                    output_tokens=token_usage.get('output_tokens', 300),
                    description="Video Tags Generation"
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'tags': generation_result.get('tags', []),
            'message': 'Tags generated successfully',
            'total_characters': generation_result.get('total_characters', 0),
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video tags: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Legacy endpoint compatibility
@bp.route('/api/video-tags/generate', methods=['POST'])
@auth_required
@require_permission('video_tags')
def generate_video_tags_legacy():
    """Legacy endpoint - redirects to new endpoint"""
    return generate_video_tags()