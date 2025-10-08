from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.competitors.competitor_analyzer import CompetitorAnalyzer
from app.scripts.competitors.youtube_api import YouTubeAPI
from app.system.services.firebase_service import db
from datetime import datetime, timezone
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
        
        # Extract channel handle or ID from URL
        channel_identifier = youtube_api.extract_channel_handle(channel_url)
        if not channel_identifier:
            return jsonify({'success': False, 'error': 'Invalid YouTube channel URL. Use format: youtube.com/@username'}), 400
        
        # Get channel info
        channel_info = youtube_api.get_channel_info(channel_identifier)
        if not channel_info:
            return jsonify({'success': False, 'error': 'Failed to fetch channel information. Please check the URL.'}), 500
        
        channel_id = channel_info.get('channel_id')
        if not channel_id:
            return jsonify({'success': False, 'error': 'Could not get channel ID from YouTube'}), 500
        
        # Check if competitor already exists
        competitors_ref = db.collection('users').document(user_id).collection('competitor_channels')
        existing = competitors_ref.where('channel_id', '==', channel_id).limit(1).get()
        
        if len(list(existing)) > 0:
            return jsonify({'success': False, 'error': 'This channel is already in your competitors list'}), 400
        
        # Save to Firebase
        now = datetime.now(timezone.utc)
        competitor_data = {
            'channel_id': channel_id,
            'channel_handle': channel_info.get('channel_handle', ''),
            'title': channel_info.get('title', ''),
            'description': channel_info.get('description', ''),
            'avatar': channel_info.get('avatar', ''),
            'subscriber_count': channel_info.get('subscriber_count', 0),
            'subscriber_count_text': channel_info.get('subscriber_count_text', '0'),
            'video_count': channel_info.get('video_count', 0),
            'keywords': channel_info.get('keywords', []),
            'added_at': now,
            'updated_at': now
        }
        
        doc_ref = competitors_ref.add(competitor_data)
        
        # Get the document ID
        if isinstance(doc_ref, tuple):
            doc_id = doc_ref[1].id
        else:
            doc_id = doc_ref.id
        
        # Add ID to response
        competitor_data['id'] = doc_id
        competitor_data['added_at'] = competitor_data['added_at'].isoformat()
        competitor_data['updated_at'] = competitor_data['updated_at'].isoformat()
        
        return jsonify({
            'success': True,
            'channel': competitor_data
        })
        
    except Exception as e:
        logger.error(f"Error adding competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/list', methods=['GET'])
@auth_required
@require_permission('competitors')
def list_competitors():
    """Get all saved competitors"""
    try:
        user_id = get_workspace_user_id()
        
        # Get all competitors from Firebase
        competitors_ref = db.collection('users').document(user_id).collection('competitor_channels')
        competitors = competitors_ref.order_by('added_at').stream()
        
        competitors_list = []
        for comp in competitors:
            comp_data = comp.to_dict()
            comp_data['id'] = comp.id

            # Fix avatar format - handle both old (array) and new (string) formats
            avatar = comp_data.get('avatar')
            if isinstance(avatar, list) and len(avatar) > 0:
                # Old format: array of avatar objects
                comp_data['avatar'] = avatar[0].get('url') if isinstance(avatar[0], dict) else None
            elif not isinstance(avatar, str):
                comp_data['avatar'] = None

            # Convert timestamps to ISO format
            if comp_data.get('added_at'):
                comp_data['added_at'] = comp_data['added_at'].isoformat()
            if comp_data.get('updated_at'):
                comp_data['updated_at'] = comp_data['updated_at'].isoformat()

            competitors_list.append(comp_data)
        
        return jsonify({
            'success': True,
            'competitors': competitors_list
        })
        
    except Exception as e:
        logger.error(f"Error listing competitors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/analyze', methods=['POST'])
@auth_required
@require_permission('competitors')
def analyze_competitors():
    """Analyze competitors and generate insights"""
    try:
        data = request.json
        timeframe = data.get('timeframe', '30')  # days
        
        user_id = get_workspace_user_id()
        
        # Get all saved competitors
        competitors_ref = db.collection('users').document(user_id).collection('competitor_channels')
        competitors = list(competitors_ref.stream())
        
        if not competitors:
            return jsonify({'success': False, 'error': 'No competitors added. Please add some channels first.'}), 400
        
        if len(competitors) > 15:
            return jsonify({'success': False, 'error': 'Maximum 15 competitors allowed for analysis'}), 400
        
        # Extract channel IDs and handles
        channel_data = []
        for comp in competitors:
            comp_dict = comp.to_dict()
            channel_data.append({
                'channel_id': comp_dict.get('channel_id'),
                'channel_handle': comp_dict.get('channel_handle', ''),
                'title': comp_dict.get('title', '')
            })
        
        credits_manager = CreditsManager()
        analyzer = CompetitorAnalyzer()
        
        # Estimate cost (rough estimate based on number of channels)
        estimated_cost = len(channel_data) * 0.5  # 0.5 credits per channel
        
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
            channel_data=channel_data,
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
        continuation_token = request.args.get('continuation_token')
        
        youtube_api = YouTubeAPI()
        result = youtube_api.get_channel_videos(
            channel_identifier=channel_id,
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
        youtube_api = YouTubeAPI()
        
        # Get video info
        video_info = youtube_api.get_video_info(video_id)
        if not video_info:
            return jsonify({'success': False, 'error': 'Failed to fetch video info'}), 500
        
        return jsonify({
            'success': True,
            'video': video_info
        })
        
    except Exception as e:
        logger.error(f"Error fetching video details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/remove/<doc_id>', methods=['DELETE'])
@auth_required
@require_permission('competitors')
def remove_competitor(doc_id):
    """Remove a competitor"""
    try:
        user_id = get_workspace_user_id()
        
        # Delete from Firebase
        competitors_ref = db.collection('users').document(user_id).collection('competitor_channels')
        competitors_ref.document(doc_id).delete()
        
        return jsonify({'success': True, 'message': 'Competitor removed successfully'})
        
    except Exception as e:
        logger.error(f"Error removing competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500