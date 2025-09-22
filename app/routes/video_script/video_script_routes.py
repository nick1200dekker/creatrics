from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_script.video_script import VideoScriptGenerator
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-script')
@auth_required
def video_script():
    """Video script generator page"""
    return render_template('video_script/index.html')

@bp.route('/api/generate-video-script', methods=['POST'])
@auth_required
def generate_video_script():
    """Generate video script using AI with proper credit management"""
    try:
        data = request.json
        concept = data.get('concept', '').strip()
        video_type = data.get('videoType', 'long')  # 'long' or 'short'
        script_format = data.get('scriptFormat', 'full')  # 'full' or 'bullet'

        if not concept:
            return jsonify({'success': False, 'error': 'Please provide a video concept or topic'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        script_generator = VideoScriptGenerator()

        user_id = g.user.get('id')

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=concept,
            model_name='claude-3-sonnet-20240229'  # Default model
        )

        # Scripts cost more than titles (more output)
        required_credits = cost_estimate['final_cost'] * 3  # Multiply by 3 for longer output
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

        # Step 2: Generate script
        generation_result = script_generator.generate_script(
            concept=concept,
            video_type=video_type,
            script_format=script_format,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Script generation failed')
            }), 500

        # Step 3: Deduct credits if AI was used
        if generation_result.get('used_ai', False):
            token_usage = generation_result.get('token_usage', {})

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', 'claude-3-sonnet-20240229'),
                    input_tokens=token_usage.get('input_tokens', 200),
                    output_tokens=token_usage.get('output_tokens', 1000),
                    description=f"Video Script Generation ({video_type}/{script_format})"
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'script': generation_result.get('script'),
            'message': 'Script generated successfully',
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Legacy endpoint compatibility
@bp.route('/api/video-script/generate', methods=['POST'])
@auth_required
def generate_video_script_legacy():
    """Legacy endpoint - redirects to new endpoint"""
    return generate_video_script()