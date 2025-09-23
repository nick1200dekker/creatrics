from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-title')
@auth_required
def video_title():
    """Video title generator page"""
    return render_template('video_title/index.html')

@bp.route('/api/generate-video-titles', methods=['POST'])
@auth_required
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

        user_id = g.user.get('id')

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=user_input,
            model_name='claude-3-sonnet-20240229'  # Default model
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
                    model_name=token_usage.get('model', 'claude-3-sonnet-20240229'),
                    input_tokens=token_usage.get('input_tokens', 100),
                    output_tokens=token_usage.get('output_tokens', 200),
                    description=f"Video Title Generation ({video_type}) - 10 titles"
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'titles': generation_result.get('titles', []),
            'message': 'Titles generated successfully',
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video titles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-title/analyze', methods=['POST'])
@auth_required
def analyze_title():
    """Analyze a video title for SEO and engagement potential"""
    try:
        data = request.json
        title = data.get('title', '')

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        # Title analysis
        length = len(title)
        word_count = len(title.split())
        has_hashtags = '#' in title
        is_shorts = '#shorts' in title.lower()

        # Calculate score
        score = 50  # Base score

        # Length scoring
        if is_shorts:
            if length < 40:
                score += 20
            elif length < 60:
                score += 10
        else:
            if 50 <= length <= 60:
                score += 20
            elif 40 <= length < 50 or 60 < length <= 70:
                score += 10

        # Power words
        power_words = ['how', 'why', 'best', 'top', 'ultimate', 'secret', 'never', 'everyone',
                       'nobody', 'trick', 'hack', 'genius', 'viral', 'amazing', 'proven']
        power_word_count = sum(1 for word in power_words if word in title.lower())
        score += min(power_word_count * 5, 20)

        # Numbers
        import re
        if re.search(r'\d+', title):
            score += 10

        strengths = []
        suggestions = []

        # Analyze strengths
        if is_shorts:
            if length < 40:
                strengths.append('Perfect length for Shorts')
            if has_hashtags:
                strengths.append('Includes hashtags for discoverability')
        else:
            if 50 <= length <= 60:
                strengths.append('Optimal length for YouTube display')
            elif length < 50:
                strengths.append('Good concise length')

        if power_word_count > 0:
            strengths.append(f'Contains {power_word_count} power word(s)')

        if re.search(r'\d+', title):
            strengths.append('Includes numbers for better CTR')

        # Generate suggestions
        if is_shorts and not has_hashtags:
            suggestions.append('Add #shorts and 2 more relevant hashtags')
        elif not is_shorts and length > 70:
            suggestions.append('Consider shortening to under 60 characters')

        if power_word_count == 0:
            suggestions.append('Add power words like "Ultimate", "Secret", or "How to"')

        if not re.search(r'\d+', title) and not is_shorts:
            suggestions.append('Consider adding numbers (e.g., "5 Ways", "Top 10")')

        if not any(word in title.lower() for word in ['you', 'your']):
            suggestions.append('Make it personal with "You" or "Your"')

        analysis = {
            'score': min(score, 100),
            'length': length,
            'word_count': word_count,
            'is_shorts': is_shorts,
            'strengths': strengths[:3],
            'suggestions': suggestions[:3],
            'seo_keywords': [word for word in title.split() if len(word) > 3][:5]
        }

        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        logger.error(f"Error analyzing title: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500