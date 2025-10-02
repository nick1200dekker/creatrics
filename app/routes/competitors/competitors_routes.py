from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.competitors.competitor_analyzer import CompetitorAnalyzer
from app.scripts.competitors.youtube_api import YouTubeAPI
import logging

logger = logging.getLogger(__name__)

@bp.route('/competitors')
@auth_required
@require_permission('competitors')
def competitors():
    """Competitor analysis page"""
    return render_template('competitors/index.html')

@bp.route('/api/competitors/add', methods=['POST'])
@auth_required
@require_permission('competitors')
def add_competitor():
    """Add a competitor channel"""
    try:
        data = request.json
        channel_url = data.get('channel_url', '').strip()
        
        if not channel_url:
            return jsonify({'success': False, 'error': 'Channel URL is required'}), 400
        
        user_id = get_workspace_user_id()
        youtube_api = YouTubeAPI()
        
        # Extract channel ID from URL
        channel_id = youtube_api.extract_channel_id(channel_url)
        if not channel_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube channel URL'}), 400
        
        # Get channel info
        channel_info = youtube_api.get_channel_info(channel_id)
        if not channel_info:
            return jsonify({'success': False, 'error': 'Failed to fetch channel information'}), 500
        
        # TODO: Save to database
        # For now, return channel info
        return jsonify({
            'success': True,
            'channel': channel_info
        })
        
    except Exception as e:
        logger.error(f"Error adding competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/analyze', methods=['POST'])
@auth_required
@require_permission('competitors')
def analyze_competitors():
    """Analyze competitors and generate insights"""
    try:
        data = request.json
        channel_ids = data.get('channel_ids', [])
        timeframe = data.get('timeframe', '30')  # days
        
        if not channel_ids:
            return jsonify({'success': False, 'error': 'No competitors selected'}), 400
        
        if len(channel_ids) > 15:
            return jsonify({'success': False, 'error': 'Maximum 15 competitors allowed'}), 400
        
        user_id = get_workspace_user_id()
        credits_manager = CreditsManager()
        analyzer = CompetitorAnalyzer()
        
        # Estimate cost (rough estimate based on number of channels)
        estimated_cost = len(channel_ids) * 0.5  # 0.5 credits per channel
        
        # Check credits
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=estimated_cost
        )
        
        if not credit_check.get('sufficient', False):
            current_credits = credits_manager.get_user_credits(user_id)
            return jsonify({
                "success": False,
                "error": f"Insufficient credits. Required: {estimated_cost:.2f}, Available: {current_credits:.2f}",
                "error_type": "insufficient_credits",
                "current_credits": current_credits,
                "required_credits": estimated_cost
            }), 402
        
        # Perform analysis
        result = analyzer.analyze_competitors(
            channel_ids=channel_ids,
            timeframe=timeframe,
            user_id=user_id
        )
        
        if not result.get('success'):
            return jsonify({
                "success": False,
                "error": result.get('error', 'Analysis failed')
            }), 500
        
        # Deduct credits if AI was used
        if result.get('used_ai', False):
            token_usage = result.get('token_usage', {})
            if token_usage.get('input_tokens', 0) > 0:
                credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', 'claude-3-sonnet-20240229'),
                    input_tokens=token_usage.get('input_tokens', 100),
                    output_tokens=token_usage.get('output_tokens', 300),
                    description="Competitor Analysis"
                )
        
        return jsonify({
            'success': True,
            'data': result.get('data', {}),
            'used_ai': result.get('used_ai', False)
        })
        
    except Exception as e:
        logger.error(f"Error analyzing competitors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/videos/<channel_id>', methods=['GET'])
@auth_required
@require_permission('competitors')
def get_channel_videos(channel_id):
    """Get videos for a specific channel"""
    try:
        timeframe = request.args.get('timeframe', '30')
        continuation_token = request.args.get('continuation_token')
        
        youtube_api = YouTubeAPI()
        result = youtube_api.get_channel_videos(
            channel_id=channel_id,
            continuation_token=continuation_token
        )
        
        if not result:
            return jsonify({'success': False, 'error': 'Failed to fetch videos'}), 500
        
        return jsonify({
            'success': True,
            'videos': result.get('videos', []),
            'continuation_token': result.get('continuation_token')
        })
        
    except Exception as e:
        logger.error(f"Error fetching channel videos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/video/<video_id>', methods=['GET'])
@auth_required
@require_permission('competitors')
def get_video_details(video_id):
    """Get detailed information about a specific video"""
    try:
        user_id = get_workspace_user_id()
        youtube_api = YouTubeAPI()
        
        # Get video info
        video_info = youtube_api.get_video_info(video_id)
        if not video_info:
            return jsonify({'success': False, 'error': 'Failed to fetch video info'}), 500
        
        # Get transcript (optional)
        transcript = youtube_api.get_transcript(video_id)
        
        return jsonify({
            'success': True,
            'video': video_info,
            'transcript': transcript
        })
        
    except Exception as e:
        logger.error(f"Error fetching video details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/remove/<channel_id>', methods=['DELETE'])
@auth_required
@require_permission('competitors')
def remove_competitor(channel_id):
    """Remove a competitor"""
    try:
        # TODO: Remove from database
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error removing competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500