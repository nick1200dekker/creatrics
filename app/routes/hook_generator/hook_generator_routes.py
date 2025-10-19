from flask import render_template, request, jsonify, g
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.hook_generator.hook_generator import TikTokHookGenerator
from . import bp
import logging

logger = logging.getLogger(__name__)

@bp.route('/tiktok/hook-generator/')
@auth_required
@require_permission('hook_generator')
def hook_generator():
    """Hook Generator - Write viral hooks to grab attention in the first 3 seconds"""
    return render_template('tiktok/hook_generator.html',
                         title='Hook Generator',
                         description='Write viral hooks to grab attention in the first 3 seconds')

@bp.route('/api/generate-tiktok-hooks', methods=['POST'])
@auth_required
@require_permission('hook_generator')
def generate_tiktok_hooks():
    """Generate TikTok hooks using AI with proper credit management"""
    try:
        data = request.json
        content = data.get('content', '').strip()

        if not content:
            return jsonify({'success': False, 'error': 'Please provide your video content'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        hook_generator = TikTokHookGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=content,
            model_name=None  # Uses current AI provider model  # Default model
        )

        required_credits = cost_estimate['final_cost']
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

        # Step 2: Generate hooks
        generation_result = hook_generator.generate_hooks(
            content=content,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Hook generation failed')
            }), 500

        # Step 3: Deduct credits if AI was used
        if generation_result.get('used_ai', False):
            token_usage = generation_result.get('token_usage', {})

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="TikTok Hook Generation - 10 hooks"
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'hooks': generation_result.get('hooks', []),
            'message': 'Hooks generated successfully',
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating TikTok hooks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500