from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
from app.scripts.video_title.video_tags import VideoTagsGenerator
from app.scripts.video_title.video_description import VideoDescriptionGenerator
from app.system.services.firebase_service import db
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-title-tags')
@auth_required
@require_permission('video_title')
def video_title_tags():
    """Video title and tags generator page"""
    return render_template('video_title_tags/index.html')

@bp.route('/api/get-channel-keywords', methods=['GET'])
@auth_required
@require_permission('video_title')
def get_channel_keywords():
    """Get user's YouTube channel keywords"""
    try:
        user_id = get_workspace_user_id()

        # Get user's YouTube channel keywords from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'success': True, 'keywords': []})

        user_data = user_doc.to_dict()
        channel_keywords = user_data.get('youtube_channel_keywords', [])

        return jsonify({
            'success': True,
            'keywords': channel_keywords
        })

    except Exception as e:
        logger.error(f"Error getting channel keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/save-channel-keywords', methods=['POST'])
@auth_required
@require_permission('video_title')
def save_channel_keywords():
    """Save user's channel keywords to Firestore"""
    try:
        user_id = get_workspace_user_id()
        data = request.json
        keywords = data.get('keywords', [])

        if not isinstance(keywords, list):
            return jsonify({'success': False, 'error': 'Keywords must be an array'}), 400

        # Update user's channel keywords in Firestore
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'youtube_channel_keywords': keywords
        })

        logger.info(f"Saved {len(keywords)} channel keywords for user {user_id}")

        return jsonify({
            'success': True,
            'message': 'Channel keywords saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving channel keywords: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/get-reference-description', methods=['GET'])
@auth_required
@require_permission('video_title')
def get_reference_description():
    """Get user's saved reference description"""
    try:
        user_id = get_workspace_user_id()

        # Get user's reference description from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'success': True, 'reference_description': ''})

        user_data = user_doc.to_dict()
        reference_description = user_data.get('reference_description', '')

        return jsonify({
            'success': True,
            'reference_description': reference_description
        })

    except Exception as e:
        logger.error(f"Error getting reference description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/save-reference-description', methods=['POST'])
@auth_required
@require_permission('video_title')
def save_reference_description():
    """Save user's reference description to Firestore"""
    try:
        user_id = get_workspace_user_id()
        data = request.json
        reference_description = data.get('reference_description', '').strip()

        # Update user's reference description in Firestore
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'reference_description': reference_description
        })

        logger.info(f"Saved reference description for user {user_id} ({len(reference_description)} chars)")

        return jsonify({
            'success': True,
            'message': 'Reference description saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving reference description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/generate-video-titles', methods=['POST'])
@auth_required
@require_permission('video_title')
def generate_video_titles():
    """Generate video titles using AI with proper credit management"""
    try:
        data = request.json
        user_input = data.get('input', '').strip()
        video_type = data.get('type', 'long')  # 'long' or 'short'

        if not user_input:
            return jsonify({'success': False, 'error': 'Please provide video content description'}), 400

        # Map frontend type to backend type
        if video_type == 'short':
            video_type = 'shorts'
        elif video_type == 'long':
            video_type = 'long_form'
        else:
            video_type = 'long_form'

        # Initialize managers
        credits_manager = CreditsManager()
        title_generator = VideoTitleGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=user_input,
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
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }), 402

        # Step 2: Generate titles
        generation_result = title_generator.generate_titles(
            user_input=user_input,
            video_type=video_type,
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

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description=f"Video Title Generation ({video_type}) - 10 titles",
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
            'used_ai': generation_result.get('used_ai', False),
            'keyword_data': generation_result.get('keyword_data', {})
        })

    except Exception as e:
        logger.error(f"Error generating video titles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/generate-video-tags', methods=['POST'])
@auth_required
@require_permission('video_title')
def generate_video_tags():
    """Generate video tags using AI with proper credit management"""
    try:
        data = request.json
        input_text = data.get('input', '').strip()
        keyword = data.get('keyword', '').strip()
        channel_keywords = data.get('channel_keywords', [])

        if not input_text:
            return jsonify({'success': False, 'error': 'Please provide video details'}), 400

        # Add keyword to the beginning of input if provided
        if keyword:
            input_text = f"PRIMARY KEYWORD: {keyword}\n\n{input_text}"

        # Initialize managers
        credits_manager = CreditsManager()
        tags_generator = VideoTagsGenerator()

        user_id = get_workspace_user_id()

        # If no channel keywords provided by user, try to get from Firebase
        if not channel_keywords:
            try:
                user_ref = db.collection('users').document(user_id)
                user_doc = user_ref.get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    channel_keywords = user_data.get('youtube_channel_keywords', [])
                    logger.info(f"Retrieved {len(channel_keywords)} channel keywords from Firebase for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not retrieve channel keywords from Firebase: {e}")
                channel_keywords = []

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=input_text,
            model_name=None  # Uses current AI provider model  # Default model
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
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }), 402

        # Step 2: Generate tags with channel keywords
        generation_result = tags_generator.generate_tags(
            input_text=input_text,
            user_id=user_id,
            channel_keywords=channel_keywords
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
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="Video Tags Generation",
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
            'tags': generation_result.get('tags', []),
            'message': 'Tags generated successfully',
            'total_characters': generation_result.get('total_characters', 0),
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video tags: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/generate-video-description', methods=['POST'])
@auth_required
@require_permission('video_title')
def generate_video_description():
    """Generate video description using AI with proper credit management"""
    try:
        data = request.json
        user_input = data.get('input', '').strip()
        reference_description = data.get('reference_description', '').strip()
        video_type = data.get('type', 'long')
        keyword = data.get('keyword', '').strip()

        if not user_input:
            return jsonify({'success': False, 'error': 'Please provide video content description'}), 400

        # Map frontend type to backend type
        if video_type == 'short':
            video_type = 'shorts'
        elif video_type == 'long':
            video_type = 'long_form'
        else:
            video_type = 'long_form'

        # Initialize managers
        credits_manager = CreditsManager()
        description_generator = VideoDescriptionGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=user_input,
            model_name=None  # Uses current AI provider model  # Default model
        )

        # Description costs more than titles (longer output)
        required_credits = cost_estimate['final_cost'] * 2
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        # Check for sufficient credits - strict enforcement
        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }), 402

        # Step 2: Generate description
        generation_result = description_generator.generate_description(
            input_text=user_input,
            video_type=video_type,
            user_id=user_id,
            reference_description=reference_description if reference_description else "",
            keyword=keyword if keyword else ""
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
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description=f"Video Description Generation ({video_type})",
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
            'description': generation_result.get('description', ''),
            'message': 'Description generated successfully',
            'description_character_count': len(generation_result.get('description', '')),
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
