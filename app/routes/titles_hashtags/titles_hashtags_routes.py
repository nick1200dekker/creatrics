from flask import render_template, request, jsonify
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.tiktok_titles_hashtags.tiktok_title_generator import TikTokTitleGenerator
from . import bp
import logging

logger = logging.getLogger(__name__)

@bp.route('/')
@auth_required
@require_permission('titles_hashtags')
def titles_hashtags():
    """Titles & Hashtags - Create captions with trending keywords & hashtags"""
    return render_template('tiktok/titles_hashtags.html',
                         title='Titles & Hashtags',
                         description='Create captions with trending keywords & hashtags')

@bp.route('/api/generate-tiktok-titles', methods=['POST'])
@auth_required
@require_permission('titles_hashtags')
def generate_tiktok_titles():
    """Generate TikTok titles with hooks and hashtags using AI"""
    try:
        data = request.json
        keywords = data.get('keywords', '').strip()
        video_input = data.get('video_input', '').strip()

        if not keywords:
            return jsonify({'success': False, 'error': 'Please provide target keywords'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        title_generator = TikTokTitleGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        # Estimate based on keywords and video input
        input_text = f"{keywords}\n{video_input}" if video_input else keywords
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=input_text,
            model_name=None  # Uses current AI provider model
        )

        required_credits = cost_estimate['final_cost']
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        # Check for sufficient credits
        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }), 402

        # Step 2: Generate titles
        generation_result = title_generator.generate_titles(
            keywords=keywords,
            video_input=video_input,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Title generation failed')
            }), 500

        # Step 3: Deduct credits if AI was used
        if generation_result.get('used_ai', False):
            token_usage = generation_result.get('token_usage', {})

            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="TikTok Title & Hashtags Generation",
                    provider_enum=token_usage.get('provider_enum')
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                    return jsonify({
                        'success': False,
                        'error': 'Credit deduction failed',
                        'error_type': 'insufficient_credits'
                    }), 402

        return jsonify({
            'success': True,
            'titles': generation_result.get('titles', []),
            'message': 'Titles generated successfully',
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating TikTok titles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500