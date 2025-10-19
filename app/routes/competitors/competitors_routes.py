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

@bp.route('/competitors/video/<video_id>/deep-dive')
@auth_required
@require_permission('competitors')
def video_deep_dive(video_id):
    """Deep dive analysis page for a competitor video or short"""
    try:
        if not video_id:
            return f"""
                <html>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1>Error</h1>
                    <p>Video ID is required</p>
                    <button onclick="window.history.back()" style="padding: 10px 20px; cursor: pointer;">Go Back</button>
                </body>
                </html>
            """, 400

        user_id = get_workspace_user_id()
        is_short = request.args.get('is_short', 'false').lower() == 'true'

        # Use the analyzer to perform deep dive
        from app.scripts.competitors.video_deep_dive_analyzer import VideoDeepDiveAnalyzer
        analyzer = VideoDeepDiveAnalyzer()

        result = analyzer.analyze_video(video_id, user_id, is_short=is_short)

        if not result.get('success'):
            error_msg = result.get('error', 'Analysis failed')
            # Check if it's an API overload error
            if '529' in str(error_msg) or 'overloaded' in str(error_msg).lower():
                error_display = "Claude AI is currently experiencing high demand. Please try again in a few moments."
            else:
                error_display = str(error_msg)

            return f"""
                <html>
                <head>
                    <style>
                        body {{
                            font-family: 'Inter', Arial, sans-serif;
                            padding: 40px;
                            text-align: center;
                            background: #18181b;
                            color: #fafafa;
                        }}
                        .error-container {{
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 40px;
                            background: rgba(255, 255, 255, 0.03);
                            border: 1px solid rgba(255, 255, 255, 0.1);
                            border-radius: 12px;
                        }}
                        h1 {{ color: #EF4444; margin-bottom: 20px; }}
                        p {{ margin-bottom: 30px; line-height: 1.6; }}
                        button {{
                            padding: 12px 24px;
                            background: #3B82F6;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 16px;
                            margin: 0 10px;
                        }}
                        button:hover {{ background: #2563EB; }}
                    </style>
                </head>
                <body>
                    <div class="error-container">
                        <h1>⚠️ Analysis Error</h1>
                        <p>{error_display}</p>
                        <button onclick="window.history.back()">← Go Back</button>
                        <button onclick="window.location.reload()">🔄 Try Again</button>
                    </div>
                </body>
                </html>
            """, 500

        video_data = result.get('data', {}).get('video_info', {})
        video_data['summary'] = result.get('data', {}).get('summary', '')
        video_data['transcript_preview'] = result.get('data', {}).get('transcript_preview', '')
        video_data['analysis'] = result.get('data', {}).get('analysis', '')

        # Save to user's video analysis history (same as Analyze Video page)
        try:
            from datetime import datetime, timezone
            import firebase_admin
            from firebase_admin import firestore

            # Initialize Firestore if needed
            if not firebase_admin._apps:
                firebase_admin.initialize_app()

            db = firestore.client()
            history_ref = db.collection('users').document(user_id).collection('video_analyses').document(video_id)

            history_data = {
                'title': video_data.get('title', ''),
                'channel_title': video_data.get('channel_title', ''),
                'thumbnail': video_data.get('thumbnail', ''),
                'view_count': video_data.get('view_count', '0'),
                'like_count': video_data.get('like_count', '0'),
                'comment_count': video_data.get('comment_count', '0'),
                'description': video_data.get('description', ''),
                'summary': video_data.get('summary', ''),
                'transcript_preview': video_data.get('transcript_preview', ''),
                'analysis': video_data.get('analysis', ''),
                'is_short': is_short,
                'analyzed_at': datetime.now(timezone.utc)
            }

            history_ref.set(history_data)
            logger.info(f"Saved deep dive analysis to history for user {user_id}: {video_id}")
        except Exception as e:
            logger.error(f"Error saving deep dive to history: {e}")
            # Don't fail the request if history save fails

        return render_template('competitors/deep_dive.html', video_data=video_data)

    except Exception as e:
        logger.error(f"Error in video deep dive: {e}")
        error_msg = str(e)
        if '529' in error_msg or 'overloaded' in error_msg.lower():
            error_display = "Claude AI is currently experiencing high demand. Please try again in a few moments."
        else:
            error_display = error_msg

        return f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: 'Inter', Arial, sans-serif;
                        padding: 40px;
                        text-align: center;
                        background: #18181b;
                        color: #fafafa;
                    }}
                    .error-container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 40px;
                        background: rgba(255, 255, 255, 0.03);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 12px;
                    }}
                    h1 {{ color: #EF4444; margin-bottom: 20px; }}
                    p {{ margin-bottom: 30px; line-height: 1.6; }}
                    button {{
                        padding: 12px 24px;
                        background: #3B82F6;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        font-size: 16px;
                        margin: 0 10px;
                    }}
                    button:hover {{ background: #2563EB; }}
                </style>
            </head>
            <body>
                <div class="error-container">
                    <h1>⚠️ Unexpected Error</h1>
                    <p>{error_display}</p>
                    <button onclick="window.history.back()">← Go Back</button>
                    <button onclick="window.location.reload()">🔄 Try Again</button>
                </div>
            </body>
            </html>
        """, 500

@bp.route('/api/competitors/lists', methods=['GET'])
@auth_required
@require_permission('competitors')
def get_niche_lists():
    """Get all niche lists"""
    try:
        user_id = get_workspace_user_id()
        lists_ref = db.collection('users').document(user_id).collection('niche_lists')
        lists = lists_ref.order_by('created_at').stream()

        lists_data = []
        for lst in lists:
            list_dict = lst.to_dict()
            list_dict['id'] = lst.id

            # Convert timestamps
            if list_dict.get('created_at'):
                list_dict['created_at'] = list_dict['created_at'].isoformat()
            if list_dict.get('updated_at'):
                list_dict['updated_at'] = list_dict['updated_at'].isoformat()

            lists_data.append(list_dict)

        return jsonify({
            'success': True,
            'lists': lists_data
        })
    except Exception as e:
        logger.error(f"Error getting niche lists: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/lists', methods=['POST'])
@auth_required
@require_permission('competitors')
def create_niche_list():
    """Create a new niche list"""
    try:
        data = request.json
        list_name = data.get('name', '').strip()

        if not list_name:
            return jsonify({'success': False, 'error': 'List name is required'}), 400

        user_id = get_workspace_user_id()
        now = datetime.now(timezone.utc)

        list_data = {
            'name': list_name,
            'created_at': now,
            'updated_at': now,
            'channel_count': 0
        }

        lists_ref = db.collection('users').document(user_id).collection('niche_lists')
        doc_ref = lists_ref.add(list_data)

        # Get the document ID
        if isinstance(doc_ref, tuple):
            doc_id = doc_ref[1].id
        else:
            doc_id = doc_ref.id

        list_data['id'] = doc_id
        list_data['created_at'] = list_data['created_at'].isoformat()
        list_data['updated_at'] = list_data['updated_at'].isoformat()

        return jsonify({
            'success': True,
            'list': list_data
        })
    except Exception as e:
        logger.error(f"Error creating niche list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/lists/<list_id>', methods=['DELETE'])
@auth_required
@require_permission('competitors')
def delete_niche_list(list_id):
    """Delete a niche list and all its channels"""
    try:
        user_id = get_workspace_user_id()

        # Delete all channels in this list (using subcollection)
        channels_ref = db.collection('users').document(user_id).collection('niche_lists').document(list_id).collection('channels')
        channels = channels_ref.stream()
        for channel in channels:
            channel.reference.delete()

        # Delete the list
        lists_ref = db.collection('users').document(user_id).collection('niche_lists')
        lists_ref.document(list_id).delete()

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting niche list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/search', methods=['GET'])
@auth_required
@require_permission('competitors')
def search_channels():
    """Search for YouTube channels using RapidAPI"""
    try:
        import requests
        import os

        query = request.args.get('query', '').strip()

        if not query:
            return jsonify({'success': False, 'error': 'Search query is required'}), 400

        # Get RapidAPI key from environment
        rapidapi_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')

        url = "https://yt-api.p.rapidapi.com/search"
        headers = {
            "x-rapidapi-key": rapidapi_key,
            "x-rapidapi-host": "yt-api.p.rapidapi.com"
        }

        # Extract unique channels from search results
        channels = {}
        continuation_token = None
        max_requests = 5  # Make up to 5 API requests to get ~50 channels

        # First request
        querystring = {"query": query, "sort_by": "relevance"}
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()

        # Extract channels from first response
        if 'data' in data:
            for item in data['data']:
                if item.get('type') in ['video', 'shorts', 'channel']:
                    channel_id = item.get('channelId')
                    if channel_id and channel_id not in channels:
                        # Parse subscriber count
                        sub_count = 0
                        sub_text = 'Unknown'
                        if item.get('subscriberCountText'):
                            sub_text = item.get('subscriberCountText')
                            # Try to parse the number
                            try:
                                sub_str = sub_text.replace(' subscribers', '').replace(' subscriber', '').strip()
                                if 'K' in sub_str:
                                    sub_count = int(float(sub_str.replace('K', '')) * 1000)
                                elif 'M' in sub_str:
                                    sub_count = int(float(sub_str.replace('M', '')) * 1000000)
                                else:
                                    sub_count = int(sub_str)
                            except:
                                pass

                        # Parse video count
                        video_count = 0
                        if item.get('videoCount'):
                            try:
                                video_count = int(item.get('videoCount'))
                            except:
                                pass

                        channels[channel_id] = {
                            'channel_id': channel_id,
                            'title': item.get('channelTitle', ''),
                            'channel_handle': item.get('channelHandle', ''),
                            'avatar': item.get('channelAvatar', [{}])[0].get('url', '') if item.get('channelAvatar') else '',
                            'subscriber_count': sub_count,
                            'subscriber_count_text': sub_text,
                            'video_count': video_count
                        }

        continuation_token = data.get('continuation')

        # Make additional requests using continuation token
        request_count = 1
        while continuation_token and len(channels) < 50 and request_count < max_requests:
            querystring = {"query": query, "token": continuation_token, "sort_by": "relevance"}
            response = requests.get(url, headers=headers, params=querystring)
            data = response.json()

            if 'data' in data:
                for item in data['data']:
                    if item.get('type') in ['video', 'shorts', 'channel']:
                        channel_id = item.get('channelId')
                        if channel_id and channel_id not in channels:
                            # Parse subscriber count
                            sub_count = 0
                            sub_text = 'Unknown'
                            if item.get('subscriberCountText'):
                                sub_text = item.get('subscriberCountText')
                                # Try to parse the number
                                try:
                                    sub_str = sub_text.replace(' subscribers', '').replace(' subscriber', '').strip()
                                    if 'K' in sub_str:
                                        sub_count = int(float(sub_str.replace('K', '')) * 1000)
                                    elif 'M' in sub_str:
                                        sub_count = int(float(sub_str.replace('M', '')) * 1000000)
                                    else:
                                        sub_count = int(sub_str)
                                except:
                                    pass

                            # Parse video count
                            video_count = 0
                            if item.get('videoCount'):
                                try:
                                    video_count = int(item.get('videoCount'))
                                except:
                                    pass

                            channels[channel_id] = {
                                'channel_id': channel_id,
                                'title': item.get('channelTitle', ''),
                                'channel_handle': item.get('channelHandle', ''),
                                'avatar': item.get('channelAvatar', [{}])[0].get('url', '') if item.get('channelAvatar') else '',
                                'subscriber_count': sub_count,
                                'subscriber_count_text': sub_text,
                                'video_count': video_count
                            }

            continuation_token = data.get('continuation')
            request_count += 1

        # Fetch detailed channel info for channels with missing data
        channel_details_url = "https://yt-api.p.rapidapi.com/channel/about"
        for channel_id, channel_data in list(channels.items()):
            # Only fetch if we don't have subscriber info
            if channel_data['subscriber_count_text'] == 'Unknown':
                try:
                    detail_querystring = {"id": channel_id}
                    detail_response = requests.get(channel_details_url, headers=headers, params=detail_querystring)
                    detail_data = detail_response.json()

                    if detail_data.get('subscriberCountText'):
                        sub_text = detail_data.get('subscriberCountText', 'Unknown')
                        channel_data['subscriber_count_text'] = sub_text

                        # Parse subscriber count
                        try:
                            sub_str = sub_text.replace(' subscribers', '').replace(' subscriber', '').strip()
                            if 'K' in sub_str:
                                channel_data['subscriber_count'] = int(float(sub_str.replace('K', '')) * 1000)
                            elif 'M' in sub_str:
                                channel_data['subscriber_count'] = int(float(sub_str.replace('M', '')) * 1000000)
                            else:
                                channel_data['subscriber_count'] = int(sub_str)
                        except:
                            pass

                    if detail_data.get('videoCount'):
                        try:
                            channel_data['video_count'] = int(detail_data.get('videoCount'))
                        except:
                            pass

                    if detail_data.get('avatar'):
                        avatars = detail_data.get('avatar', [])
                        if avatars and len(avatars) > 0:
                            channel_data['avatar'] = avatars[0].get('url', channel_data['avatar'])
                except Exception as e:
                    logger.error(f"Error fetching channel details for {channel_id}: {e}")
                    # Continue with existing data

        # Filter out channels with unknown subs or below 1K subs
        filtered_channels = []
        for channel_data in channels.values():
            # Skip if subscriber count is unknown
            if channel_data['subscriber_count_text'] == 'Unknown':
                continue
            # Skip if subscriber count is below 1000
            if channel_data['subscriber_count'] < 1000:
                continue
            filtered_channels.append(channel_data)

        return jsonify({
            'success': True,
            'channels': filtered_channels[:50]  # Return up to 50 filtered channels
        })

    except Exception as e:
        logger.error(f"Error searching channels: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/add', methods=['POST'])
@auth_required
@require_permission('competitors')
def add_competitor():
    """Add a competitor channel"""
    try:
        data = request.json
        channel_url = data.get('channel_url', '').strip()
        channel_data_from_search = data.get('channel_data')  # From search results
        list_id = data.get('list_id', '').strip()

        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        user_id = get_workspace_user_id()
        now = datetime.now(timezone.utc)

        # If channel data is provided from search (explore), use it directly
        if channel_data_from_search:
            channel_id = channel_data_from_search.get('channel_id')
            if not channel_id:
                return jsonify({'success': False, 'error': 'Channel ID is required'}), 400

            competitor_data = {
                'channel_id': channel_id,
                'channel_handle': channel_data_from_search.get('channel_handle', ''),
                'title': channel_data_from_search.get('title', ''),
                'description': '',
                'avatar': channel_data_from_search.get('avatar', ''),
                'subscriber_count': channel_data_from_search.get('subscriber_count', 0),
                'subscriber_count_text': channel_data_from_search.get('subscriber_count_text', 'Unknown'),
                'video_count': channel_data_from_search.get('video_count', 0),
                'keywords': [],
                'added_at': now,
                'updated_at': now
            }
        else:
            # Original flow: fetch from YouTube API
            if not channel_url:
                return jsonify({'success': False, 'error': 'Channel URL is required'}), 400

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

        # Check if competitor already exists in this list (using subcollection)
        competitors_ref = db.collection('users').document(user_id).collection('niche_lists').document(list_id).collection('channels')
        existing = competitors_ref.where('channel_id', '==', channel_id).limit(1).get()

        if len(list(existing)) > 0:
            return jsonify({'success': False, 'error': 'This channel is already in this niche list'}), 400

        # Save to Firebase
        doc_ref = competitors_ref.add(competitor_data)

        # Get the document ID
        if isinstance(doc_ref, tuple):
            doc_id = doc_ref[1].id
        else:
            doc_id = doc_ref.id

        # Update channel count in list
        lists_ref = db.collection('users').document(user_id).collection('niche_lists')
        list_doc = lists_ref.document(list_id).get()
        if list_doc.exists:
            current_count = list_doc.to_dict().get('channel_count', 0)
            lists_ref.document(list_id).update({
                'channel_count': current_count + 1,
                'updated_at': now
            })

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
    """Get all saved competitors for a specific list"""
    try:
        user_id = get_workspace_user_id()
        list_id = request.args.get('list_id')

        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        # Get all competitors from Firebase for this list (using subcollection)
        competitors_ref = db.collection('users').document(user_id).collection('niche_lists').document(list_id).collection('channels')
        competitors = competitors_ref.stream()

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

@bp.route('/api/competitors/latest-analysis', methods=['GET'])
@auth_required
@require_permission('competitors')
def get_latest_analysis():
    """Get the latest saved competitor analysis"""
    try:
        user_id = get_workspace_user_id()

        # Get the latest analysis document
        analysis_ref = db.collection('users').document(user_id).collection('competitor_analyses').document('latest')
        analysis_doc = analysis_ref.get()

        if not analysis_doc.exists:
            return jsonify({
                'success': True,
                'has_analysis': False
            })

        analysis_data = analysis_doc.to_dict()

        # Convert timestamp
        if analysis_data.get('created_at'):
            analysis_data['created_at'] = analysis_data['created_at'].isoformat()

        return jsonify({
            'success': True,
            'has_analysis': True,
            'analysis': analysis_data
        })

    except Exception as e:
        logger.error(f"Error getting latest analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/analyze', methods=['POST'])
@auth_required
@require_permission('competitors')
def analyze_competitors():
    """Analyze competitors and generate insights"""
    try:
        data = request.json
        timeframe = data.get('timeframe', '30')  # days
        list_id = data.get('list_id', '').strip()

        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        user_id = get_workspace_user_id()

        # Get all saved competitors for this list (using subcollection)
        competitors_ref = db.collection('users').document(user_id).collection('niche_lists').document(list_id).collection('channels')
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
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="Competitor Analysis"
                )

        # Save as latest analysis (replace if exists)
        try:
            analysis_data = {
                'list_id': list_id,
                'list_name': data.get('list_name', 'Unknown'),
                'timeframe': timeframe,
                'channel_count': len(channel_data),
                'insights': result.get('data', {}),
                'created_at': datetime.now(timezone.utc)
            }

            # Store in user's latest_analysis document (overwrites previous)
            analysis_ref = db.collection('users').document(user_id).collection('competitor_analyses').document('latest')
            analysis_ref.set(analysis_data)

            logger.info(f"Saved latest analysis for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving analysis: {e}")
            # Don't fail the request if save fails

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
        timeframe_days = request.args.get('timeframe_days', type=int)

        youtube_api = YouTubeAPI()
        result = youtube_api.get_channel_videos(
            channel_identifier=channel_id,
            continuation_token=continuation_token
        )

        if not result:
            return jsonify({'success': False, 'error': 'Failed to fetch videos'}), 500

        videos = result.get('videos', [])

        # Apply timeframe filter if specified
        if timeframe_days:
            videos = youtube_api.filter_videos_by_timeframe(videos, timeframe_days)

        return jsonify({
            'success': True,
            'videos': videos,
            'continuation_token': result.get('continuation_token')
        })

    except Exception as e:
        logger.error(f"Error fetching channel videos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/shorts/<channel_id>', methods=['GET'])
@auth_required
@require_permission('competitors')
def get_channel_shorts(channel_id):
    """Get shorts for a specific channel"""
    try:
        continuation_token = request.args.get('continuation_token')
        timeframe_days = request.args.get('timeframe_days', type=int)

        youtube_api = YouTubeAPI()
        result = youtube_api.get_channel_shorts(
            channel_identifier=channel_id,
            continuation_token=continuation_token
        )

        if not result:
            return jsonify({'success': False, 'error': 'Failed to fetch shorts'}), 500

        shorts = result.get('shorts', [])

        # Apply timeframe filter if specified
        if timeframe_days:
            shorts = youtube_api.filter_videos_by_timeframe(shorts, timeframe_days)

        return jsonify({
            'success': True,
            'shorts': shorts,
            'continuation_token': result.get('continuation_token')
        })

    except Exception as e:
        logger.error(f"Error fetching channel shorts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/competitors/video/<video_id>', methods=['GET'])
@auth_required
@require_permission('competitors')
def get_video_details(video_id):
    """Get detailed information about a specific video or short"""
    try:
        youtube_api = YouTubeAPI()
        is_short = request.args.get('is_short', 'false').lower() == 'true'

        # Get video or short info
        if is_short:
            video_info = youtube_api.get_short_info(video_id)
        else:
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

@bp.route('/api/competitors/remove/<list_id>/<doc_id>', methods=['DELETE'])
@auth_required
@require_permission('competitors')
def remove_competitor(list_id, doc_id):
    """Remove a competitor"""
    try:
        user_id = get_workspace_user_id()

        # Delete from Firebase (using subcollection)
        competitors_ref = db.collection('users').document(user_id).collection('niche_lists').document(list_id).collection('channels')
        competitors_ref.document(doc_id).delete()

        # Update channel count in list
        lists_ref = db.collection('users').document(user_id).collection('niche_lists')
        list_doc = lists_ref.document(list_id).get()
        if list_doc.exists:
            current_count = list_doc.to_dict().get('channel_count', 1)
            lists_ref.document(list_id).update({
                'channel_count': max(0, current_count - 1),
                'updated_at': datetime.now(timezone.utc)
            })

        return jsonify({'success': True, 'message': 'Competitor removed successfully'})

    except Exception as e:
        logger.error(f"Error removing competitor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500