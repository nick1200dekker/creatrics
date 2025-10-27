from flask import render_template, request, jsonify, redirect, url_for
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from app.scripts.competitors.video_deep_dive_analyzer import VideoDeepDiveAnalyzer
from app.system.services.firebase_service import db
from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)

@bp.route('/analyze-video')
@auth_required
@require_permission('analyze_video')
def analyze_video():
    """Analyze Video main page"""
    return render_template('analyze_video/index.html')

@bp.route('/analyze-video/video/<video_id>')
@auth_required
@require_permission('analyze_video')
def video_analysis(video_id):
    """Video analysis page - reuses deep dive functionality and template"""
    try:
        if not video_id:
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
                        <h1>Error</h1>
                        <p>Video ID is required</p>
                        <button onclick="window.history.back()">Go Back</button>
                    </div>
                </body>
                </html>
            """, 400

        user_id = get_workspace_user_id()
        is_short = request.args.get('is_short', 'false').lower() == 'true'

        # Check if analysis already exists in Firebase
        history_ref = db.collection('users').document(user_id).collection('video_analyses').document(video_id)
        existing_doc = history_ref.get()

        if existing_doc.exists:
            # Load existing analysis from Firebase
            logger.info(f"Loading existing analysis from Firebase for user {user_id}: {video_id}")
            stored_data = existing_doc.to_dict()

            video_data = {
                'video_id': video_id,
                'title': stored_data.get('title', ''),
                'channel_title': stored_data.get('channel_title', ''),
                'thumbnail': stored_data.get('thumbnail', ''),
                'view_count': stored_data.get('view_count', '0'),
                'like_count': stored_data.get('like_count', '0'),
                'comment_count': stored_data.get('comment_count', '0'),
                'description': stored_data.get('description', ''),
                'summary': stored_data.get('summary', ''),
                'transcript_preview': stored_data.get('transcript_preview', ''),
                'analysis': stored_data.get('analysis', ''),
                'is_short': stored_data.get('is_short', False)
            }

            # Reuse the competitors deep dive template with a back_url parameter
            return render_template('competitors/deep_dive.html',
                                 video_data=video_data,
                                 video_id=video_id,
                                 back_url=url_for('analyze_video.analyze_video'))

        # Check credits BEFORE calling the analyzer
        from app.system.credits.credits_manager import CreditsManager
        credits_manager = CreditsManager()

        # Estimate cost (conservative)
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content="video analysis" * 500,
            model_name=None
        )
        required_credits = cost_estimate['final_cost']

        logger.info(f"Checking credits for user {user_id}, required: {required_credits}")

        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        logger.info(f"Credit check result in video_analysis route: {credit_check}")

        if not credit_check.get('sufficient', False):
            # Redirect back to main page with error parameter
            logger.warning(f"Insufficient credits - redirecting user {user_id} back to main page")
            return redirect(url_for('analyze_video.analyze_video') + '?error=insufficient_credits')

        # Use the analyzer to perform deep dive
        analyzer = VideoDeepDiveAnalyzer()
        result = analyzer.analyze_video(video_id, user_id, is_short=is_short)

        if not result.get('success'):
            error_msg = result.get('error', 'Analysis failed')
            error_type = result.get('error_type', '')

            # Handle insufficient credits - redirect back to main page
            if error_type == 'insufficient_credits':
                return redirect(url_for('analyze_video.analyze_video') + '?error=insufficient_credits')

            if '529' in str(error_msg) or 'overloaded' in str(error_msg).lower():
                error_display = "AI service is currently experiencing high demand. Please try again in a few moments."
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

        # Save to Firebase with full analysis data
        try:
            history_data = {
                'video_id': video_id,
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

            # Save to user's video history
            history_ref.set(history_data)

            logger.info(f"Saved video analysis to history for user {user_id}: {video_id}")
        except Exception as e:
            logger.error(f"Error saving to history: {e}")
            # Don't fail the request if history save fails

        # Reuse the competitors deep dive template with a back_url parameter
        return render_template('competitors/deep_dive.html',
                             video_data=video_data,
                             video_id=video_id,
                             back_url=url_for('analyze_video.analyze_video'))

    except Exception as e:
        logger.error(f"Error in video analysis: {e}")
        error_msg = str(e)
        if '529' in error_msg or 'overloaded' in error_msg.lower():
            error_display = "AI service is currently experiencing high demand. Please try again in a few moments."
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

@bp.route('/api/analyze-video/search', methods=['GET'])
@auth_required
@require_permission('analyze_video')
def search_videos():
    """Search for videos or shorts with pagination"""
    try:
        from app.scripts.competitors.youtube_api import YouTubeAPI
        import requests

        query = request.args.get('query', '').strip()
        content_type = request.args.get('type', 'videos').strip()  # 'videos' or 'shorts'
        sort_by = request.args.get('sort_by', 'relevance').strip()  # 'relevance' or 'date'

        if not query:
            return jsonify({'success': False, 'error': 'Query is required'}), 400

        youtube_api = YouTubeAPI()

        # Search for videos or shorts with user-selected sorting
        import time
        url = f"https://yt-api.p.rapidapi.com/search"
        search_type = "shorts" if content_type == "shorts" else "video"
        querystring = {
            "query": query,
            "type": search_type,
            "sort_by": sort_by,
            "_t": int(time.time())  # Cache-busting
        }

        videos = []
        is_short = content_type == "shorts"

        # PARALLEL API CALLS - Make first request to get continuation token
        querystring['_t'] = int(time.time())
        first_response = requests.get(url, headers=youtube_api.headers, params=querystring, timeout=30)
        first_response.raise_for_status()
        first_data = first_response.json()

        continuation_token = first_data.get('continuation')

        # Process first batch
        if 'data' in first_data:
            for item in first_data['data']:
                item_type = item.get('type')
                if is_short and item_type == 'shorts':
                    videos.append({
                        'video_id': item.get('videoId'),
                        'title': item.get('title'),
                        'channel_title': item.get('channelTitle'),
                        'thumbnail': item.get('thumbnail', [{}])[0].get('url') if item.get('thumbnail') else '',
                        'view_count_text': item.get('viewCount', 'N/A'),
                        'published_time': item.get('publishedTimeText', ''),
                        'is_short': True
                    })
                elif not is_short and item_type == 'video':
                    videos.append({
                        'video_id': item.get('videoId'),
                        'title': item.get('title'),
                        'channel_title': item.get('channelTitle'),
                        'thumbnail': item.get('thumbnail', [{}])[0].get('url') if item.get('thumbnail') else '',
                        'view_count_text': item.get('viewCount', 'N/A'),
                        'published_time': item.get('publishedTimeText', ''),
                        'is_short': False
                    })

        # If we have continuation token and need more results, fetch next 2 pages in PARALLEL
        if continuation_token and len(videos) < 50:
            import asyncio
            import httpx

            async def fetch_next_pages():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    tasks = []
                    current_token = continuation_token

                    # Create 2 requests with continuation tokens
                    for i in range(2):
                        if current_token:
                            params = {**querystring, 'continuation': current_token, '_t': int(time.time()) + i}
                            tasks.append(client.get(url, headers=youtube_api.headers, params=params))

                    if tasks:
                        return await asyncio.gather(*tasks, return_exceptions=True)
                    return []

            responses = asyncio.run(fetch_next_pages())

            # Process parallel responses
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                try:
                    data = resp.json()
                    if 'data' in data:
                        for item in data['data']:
                            if len(videos) >= 50:
                                break
                            item_type = item.get('type')
                            if is_short and item_type == 'shorts':
                                videos.append({
                                    'video_id': item.get('videoId'),
                                    'title': item.get('title'),
                                    'channel_title': item.get('channelTitle'),
                                    'thumbnail': item.get('thumbnail', [{}])[0].get('url') if item.get('thumbnail') else '',
                                    'view_count_text': item.get('viewCount', 'N/A'),
                                    'published_time': item.get('publishedTimeText', ''),
                                    'is_short': True
                                })
                            elif not is_short and item_type == 'video':
                                videos.append({
                                    'video_id': item.get('videoId'),
                                    'title': item.get('title'),
                                    'channel_title': item.get('channelTitle'),
                                    'thumbnail': item.get('thumbnail', [{}])[0].get('url') if item.get('thumbnail') else '',
                                    'view_count_text': item.get('viewCount', 'N/A'),
                                    'published_time': item.get('publishedTimeText', ''),
                                    'is_short': False
                                })
                except:
                    continue

        return jsonify({
            'success': True,
            'videos': videos[:50]  # Return max 50 results
        })

    except Exception as e:
        logger.error(f"Error searching videos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analyze-video/extract-id', methods=['POST'])
@auth_required
@require_permission('analyze_video')
def extract_video_id():
    """Extract video ID from YouTube URL"""
    try:
        data = request.json
        url = data.get('url', '').strip()
        is_short = data.get('is_short', False)

        if not url:
            return jsonify({'success': False, 'error': 'URL is required'}), 400

        # Auto-detect if URL is a short
        if '/shorts/' in url:
            is_short = True

        # Extract video ID from various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)',
            r'youtube\.com\/shorts\/([^&\n?#]+)',
        ]

        video_id = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400

        return jsonify({
            'success': True,
            'video_id': video_id,
            'is_short': is_short
        })

    except Exception as e:
        logger.error(f"Error extracting video ID: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analyze-video/pre-check/<video_id>', methods=['GET'])
@auth_required
@require_permission('analyze_video')
def pre_check_analysis(video_id):
    """Pre-check if analysis can proceed (exists in history OR has sufficient credits)"""
    try:
        user_id = get_workspace_user_id()
        is_short = request.args.get('is_short', 'false').lower() == 'true'

        logger.info(f"Pre-check for video {video_id}, user {user_id}, is_short: {is_short}")

        # Check if analysis already exists in Firebase
        history_ref = db.collection('users').document(user_id).collection('video_analyses').document(video_id)
        existing_doc = history_ref.get()

        if existing_doc.exists:
            # Analysis exists - can proceed
            logger.info(f"Video {video_id} already exists in history - allowing")
            return jsonify({'success': True, 'can_proceed': True, 'reason': 'exists'})

        # Check credits before analysis
        from app.system.credits.credits_manager import CreditsManager
        credits_manager = CreditsManager()

        # Estimate cost (conservative)
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content="video analysis" * 500,
            model_name=None
        )
        required_credits = cost_estimate['final_cost']

        logger.info(f"Required credits for video analysis: {required_credits}")

        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        logger.info(f"Credit check result: {credit_check}")

        if not credit_check.get('sufficient', False):
            logger.warning(f"Insufficient credits for user {user_id} to analyze video {video_id}")
            return jsonify({
                'success': True,
                'can_proceed': False,
                'reason': 'insufficient_credits'
            })

        logger.info(f"Sufficient credits - allowing video analysis for {video_id}")
        return jsonify({'success': True, 'can_proceed': True, 'reason': 'sufficient_credits'})

    except Exception as e:
        logger.error(f"Error in pre-check: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analyze-video/history', methods=['GET'])
@auth_required
@require_permission('analyze_video')
def get_history():
    """Get video analysis history"""
    try:
        user_id = get_workspace_user_id()

        # Get analysis history from Firestore (last 50)
        history_ref = db.collection('users').document(user_id).collection('video_analyses')
        history_docs = history_ref.order_by('analyzed_at', direction='DESCENDING').limit(50).stream()

        history = []
        for doc in history_docs:
            doc_data = doc.to_dict()
            doc_data['video_id'] = doc.id

            # Convert timestamp
            if doc_data.get('analyzed_at'):
                doc_data['analyzed_at'] = doc_data['analyzed_at'].isoformat()

            history.append(doc_data)

        return jsonify({
            'success': True,
            'history': history
        })

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
