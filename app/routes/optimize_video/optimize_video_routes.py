"""
Optimize Video Routes
Handles user's own YouTube video optimization
"""
from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from app.scripts.optimize_video.video_optimizer import VideoOptimizer
from app.system.services.firebase_service import db
from datetime import datetime, timezone
import logging
import os
import requests

logger = logging.getLogger(__name__)

# RapidAPI configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
RAPIDAPI_HOST = 'yt-api.p.rapidapi.com'

@bp.route('/')
@auth_required
@require_permission('optimize_video')
def optimize_video():
    """Optimize Video main page"""
    return render_template('optimize_video/index.html')

@bp.route('/api/get-unoptimized-videos', methods=['GET'])
@auth_required
def get_unoptimized_videos():
    """Get user's YouTube videos that haven't been optimized yet - for homepage"""
    try:
        user_id = get_workspace_user_id()

        # Get user's connected YouTube channel
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'success': False, 'videos': []})

        user_data = user_doc.to_dict()

        # Get YouTube channel info
        channel_id = user_data.get('youtube_channel_id', '')
        channel_title = user_data.get('youtube_account', '')

        if not channel_id or not channel_title:
            return jsonify({'success': True, 'videos': []})  # Not connected, return empty

        # Fetch videos from RapidAPI
        url = f"https://{RAPIDAPI_HOST}/channel/videos"
        channel_handle = f"@{channel_title}" if not channel_title.startswith('@') else channel_title

        import time
        querystring = {
            "forUsername": channel_handle,
            "_t": int(time.time())
        }
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Get list of optimized video IDs from Firebase
        optimizations_ref = db.collection('users').document(user_id).collection('video_optimizations')
        optimized_docs = optimizations_ref.stream()
        optimized_video_ids = {doc.id for doc in optimized_docs}

        # Filter to only non-optimized videos
        videos = []
        if 'data' in data:
            for video in data['data']:
                if video.get('type') == 'video':
                    video_id = video.get('videoId')
                    # Only include if NOT already optimized
                    if video_id and video_id not in optimized_video_ids:
                        videos.append({
                            'video_id': video_id,
                            'title': video.get('title'),
                            'thumbnail': video.get('thumbnail', [{}])[0].get('url') if video.get('thumbnail') else '',
                            'view_count': video.get('viewCountText', '0'),
                            'published_time': video.get('publishedTimeText', '')
                        })

                    # Limit to 6 videos for homepage
                    if len(videos) >= 6:
                        break

        return jsonify({
            'success': True,
            'videos': videos,
            'has_youtube': True
        })

    except Exception as e:
        logger.error(f"Error getting unoptimized videos: {e}")
        return jsonify({'success': True, 'videos': [], 'has_youtube': False})

@bp.route('/api/get-my-videos', methods=['GET'])
@auth_required
@require_permission('optimize_video')
def get_my_videos():
    """Get user's YouTube channel videos"""
    try:
        user_id = get_workspace_user_id()

        # Get user's connected YouTube channel
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        user_data = user_doc.to_dict()

        # Get YouTube channel info from stored fields (set by accounts/youtube.py)
        channel_id = user_data.get('youtube_channel_id', '')
        channel_title = user_data.get('youtube_account', '')

        # Debug logging
        logger.info(f"User {user_id} - channel_id: {channel_id}, channel_title: {channel_title}")

        if not channel_id or not channel_title:
            return jsonify({
                'success': False,
                'error': 'No YouTube channel connected. Please connect your YouTube account in Social Accounts.'
            }), 400

        # Fetch videos from RapidAPI using channel handle (works better than ID)
        url = f"https://{RAPIDAPI_HOST}/channel/videos"
        # Use channel title as handle - add @ if not present
        channel_handle = f"@{channel_title}" if not channel_title.startswith('@') else channel_title

        # Add cache-busting timestamp to force fresh data
        import time
        querystring = {
            "forUsername": channel_handle,
            "_t": int(time.time())  # Cache buster
        }
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

        logger.info(f"Fetching videos from RapidAPI for channel {channel_handle} (cache-busting enabled)")
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Extract video list
        videos = []
        if 'data' in data:
            for video in data['data']:
                # Only include actual videos (not shorts, playlists, etc.)
                if video.get('type') == 'video':
                    videos.append({
                        'video_id': video.get('videoId'),
                        'title': video.get('title'),
                        'thumbnail': video.get('thumbnail', [{}])[0].get('url') if video.get('thumbnail') else '',
                        'view_count': video.get('viewCountText', '0'),
                        'published_time': video.get('publishedTimeText', ''),
                        'length_text': video.get('lengthText', '')
                    })

        logger.info(f"Fetched {len(videos)} videos for channel {channel_title}")

        return jsonify({
            'success': True,
            'videos': videos,
            'channel_name': channel_title if channel_title else channel_id
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching videos from RapidAPI: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch videos from YouTube'}), 500
    except Exception as e:
        logger.error(f"Error getting user videos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/optimize/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def optimize_video_analysis(video_id):
    """Optimize a specific video with AI analysis and recommendations"""
    try:
        user_id = get_workspace_user_id()

        # Check if optimization already exists in Firebase
        optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
        existing_doc = optimization_ref.get()

        if existing_doc.exists:
            # Return existing optimization
            logger.info(f"Loading existing optimization from Firebase for user {user_id}: {video_id}")
            stored_data = existing_doc.to_dict()

            # Log what titles we're returning
            title_suggestions = stored_data.get('title_suggestions', [])
            logger.info(f"Returning cached optimization with {len(title_suggestions)} titles")
            if title_suggestions:
                logger.info(f"First cached title: {title_suggestions[0]}")

            return jsonify({
                'success': True,
                'data': stored_data
            })

        # Perform new optimization
        optimizer = VideoOptimizer()
        result = optimizer.optimize_video(video_id, user_id)

        if not result.get('success'):
            error_msg = result.get('error', 'Optimization failed')
            return jsonify({'success': False, 'error': error_msg}), 500

        # Save to Firebase
        optimization_data = {
            'video_id': video_id,
            'video_info': result.get('video_info', {}),
            'current_title': result.get('current_title', ''),
            'current_description': result.get('current_description', ''),
            'current_tags': result.get('current_tags', []),
            'transcript_preview': result.get('transcript_preview', ''),
            'optimized_title': result.get('optimized_title', ''),
            'title_suggestions': result.get('title_suggestions', []),
            'optimized_description': result.get('optimized_description', ''),
            'optimized_tags': result.get('optimized_tags', []),
            'thumbnail_analysis': result.get('thumbnail_analysis', ''),
            'recommendations': result.get('recommendations', {}),
            'optimized_at': datetime.now(timezone.utc)
        }

        optimization_ref.set(optimization_data)
        logger.info(f"Saved video optimization to Firebase for user {user_id}: {video_id}")

        return jsonify({
            'success': True,
            'data': optimization_data
        })

    except Exception as e:
        logger.error(f"Error optimizing video: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/optimization-history', methods=['GET'])
@auth_required
@require_permission('optimize_video')
def get_optimization_history():
    """Get optimization history"""
    try:
        user_id = get_workspace_user_id()

        # Get optimization history from Firestore (last 50)
        history_ref = db.collection('users').document(user_id).collection('video_optimizations')
        history_docs = history_ref.order_by('optimized_at', direction='DESCENDING').limit(50).stream()

        history = []
        for doc in history_docs:
            doc_data = doc.to_dict()
            doc_data['video_id'] = doc.id

            # Convert timestamp
            if doc_data.get('optimized_at'):
                doc_data['optimized_at'] = doc_data['optimized_at'].isoformat()

            history.append(doc_data)

        return jsonify({
            'success': True,
            'history': history
        })

    except Exception as e:
        logger.error(f"Error getting optimization history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/refresh-titles/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def refresh_titles(video_id):
    """Regenerate title suggestions for a video"""
    try:
        user_id = get_workspace_user_id()

        # Get existing optimization to retrieve context
        optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
        existing_doc = optimization_ref.get()

        if not existing_doc.exists:
            return jsonify({'success': False, 'error': 'Optimization not found'}), 404

        stored_data = existing_doc.to_dict()

        # Build context for title generation
        from app.scripts.video_title.video_title import VideoTitleGenerator

        optimization_context = f"""
Video Title: {stored_data.get('current_title', '')}
Video Description: {stored_data.get('current_description', '')[:500]}
Video Transcript: {stored_data.get('transcript_preview', '')}
"""

        # Generate new title suggestions
        title_generator = VideoTitleGenerator()
        title_result = title_generator.generate_titles(
            optimization_context,
            video_type='long_form',
            user_id=user_id
        )

        # Get 10 titles from the result
        all_titles = title_result.get('titles', [])
        if len(all_titles) >= 10:
            new_title_suggestions = all_titles[:10]
        else:
            new_title_suggestions = all_titles + [stored_data.get('current_title', '')] * (10 - len(all_titles))

        # Update Firebase with new titles
        logger.info(f"Updating Firebase with {len(new_title_suggestions)} new titles for video {video_id}")
        logger.info(f"New titles: {new_title_suggestions[:3]}...")  # Log first 3 titles

        optimization_ref.update({
            'title_suggestions': new_title_suggestions,
            'optimized_title': new_title_suggestions[0] if new_title_suggestions else stored_data.get('current_title', '')
        })

        logger.info(f"Regenerated titles for user {user_id}, video {video_id}")

        # Verify the update by reading back
        updated_doc = optimization_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            logger.info(f"Verified Firebase update - first title: {updated_data.get('title_suggestions', [])[0] if updated_data.get('title_suggestions') else 'NONE'}")

        return jsonify({
            'success': True,
            'title_suggestions': new_title_suggestions
        })

    except Exception as e:
        logger.error(f"Error refreshing titles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/apply-optimizations/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def apply_optimizations(video_id):
    """Apply optimized title, description, or tags to YouTube video"""
    try:
        user_id = get_workspace_user_id()

        # Get request data
        request_data = request.get_json() or {}
        title = request_data.get('title')
        description = request_data.get('description')
        tags = request_data.get('tags')

        # Validate that at least one field is provided
        if title is None and description is None and tags is None:
            return jsonify({
                'success': False,
                'error': 'No fields to update provided'
            }), 400

        # Call update function
        from app.scripts.accounts.youtube_analytics import update_video_metadata
        result = update_video_metadata(
            user_id=user_id,
            video_id=video_id,
            title=title,
            description=description,
            tags=tags
        )

        # If successful, update Firebase to mark what was applied
        if result.get('success'):
            optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
            optimization_doc = optimization_ref.get()

            if optimization_doc.exists:
                update_data = {
                    'last_applied_at': datetime.now(timezone.utc)
                }

                if title is not None:
                    update_data['applied_title'] = title
                    update_data['applied_title_at'] = datetime.now(timezone.utc)

                if description is not None:
                    update_data['applied_description_at'] = datetime.now(timezone.utc)

                if tags is not None:
                    update_data['applied_tags_at'] = datetime.now(timezone.utc)

                optimization_ref.update(update_data)
                logger.info(f"Updated optimization tracking for video {video_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error applying optimizations: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to apply optimizations: {str(e)}'
        }), 500
