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

        # Use the analyzer to perform deep dive
        analyzer = VideoDeepDiveAnalyzer()
        result = analyzer.analyze_video(video_id, user_id)

        if not result.get('success'):
            error_msg = result.get('error', 'Analysis failed')
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

        # Save to history
        try:
            history_data = {
                'video_id': video_id,
                'title': video_data.get('title', ''),
                'channel_title': video_data.get('channel_title', ''),
                'thumbnail': video_data.get('thumbnail', ''),
                'view_count': video_data.get('view_count', '0'),
                'analyzed_at': datetime.now(timezone.utc)
            }

            # Save to user's video history
            history_ref = db.collection('users').document(user_id).collection('video_analyses').document(video_id)
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
    """Search for videos"""
    try:
        from app.scripts.competitors.youtube_api import YouTubeAPI
        import requests

        query = request.args.get('query', '').strip()

        if not query:
            return jsonify({'success': False, 'error': 'Query is required'}), 400

        youtube_api = YouTubeAPI()

        # Search for videos with relevance sorting
        url = f"https://yt-api.p.rapidapi.com/search"
        querystring = {"query": query, "type": "video", "sort_by": "relevance"}

        response = requests.get(url, headers=youtube_api.headers, params=querystring)
        response.raise_for_status()

        data = response.json()
        videos = []

        if 'data' in data:
            for item in data['data'][:20]:  # Return top 20 videos
                if item.get('type') == 'video':
                    videos.append({
                        'video_id': item.get('videoId'),
                        'title': item.get('title'),
                        'channel_title': item.get('channelTitle'),
                        'thumbnail': item.get('thumbnail', [{}])[0].get('url') if item.get('thumbnail') else '',
                        'view_count_text': item.get('viewCount', 'N/A'),
                        'published_time': item.get('publishedTimeText', '')
                    })

        return jsonify({
            'success': True,
            'videos': videos
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

        if not url:
            return jsonify({'success': False, 'error': 'URL is required'}), 400

        # Extract video ID from various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)',
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
            'video_id': video_id
        })

    except Exception as e:
        logger.error(f"Error extracting video ID: {e}")
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
