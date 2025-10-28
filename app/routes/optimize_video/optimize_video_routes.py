"""
Optimize Video Routes
Handles user's own YouTube video optimization
"""
from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission, get_user_subscription
from app.scripts.optimize_video.video_optimizer import VideoOptimizer
from app.system.services.firebase_service import db
from app.system.credits.credits_manager import CreditsManager
from app.system.ai_provider.ai_provider import AIProvider
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
                        # Get highest resolution thumbnail from RapidAPI response
                        # Array goes from low to high resolution, last item is typically maxresdefault
                        thumbnails = video.get('thumbnail', [])
                        thumbnail = thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

                        videos.append({
                            'video_id': video_id,
                            'title': video.get('title'),
                            'thumbnail': thumbnail,
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

        # PARALLEL API CALLS - Videos and Shorts at same time
        import asyncio
        import httpx

        async def fetch_videos_and_shorts():
            async with httpx.AsyncClient(timeout=30.0) as client:
                tasks = [
                    client.get(url, headers=headers, params=querystring),
                    client.get(f"https://{RAPIDAPI_HOST}/channel/shorts", headers=headers, params=querystring)
                ]
                return await asyncio.gather(*tasks, return_exceptions=True)

        response, shorts_response = asyncio.run(fetch_videos_and_shorts())

        # Process videos response
        data = response.json() if not isinstance(response, Exception) else {}

        # Extract channel keywords from meta
        channel_keywords = []
        if 'meta' in data and 'keywords' in data['meta']:
            channel_keywords = data['meta'].get('keywords', [])
            logger.info(f"Found {len(channel_keywords)} channel keywords: {channel_keywords[:5]}...")

            # Store channel keywords in user document for later use
            try:
                user_ref.update({
                    'youtube_channel_keywords': channel_keywords
                })
                logger.info(f"Successfully saved {len(channel_keywords)} channel keywords to user document {user_id}")
            except Exception as e:
                logger.error(f"Error saving channel keywords: {e}")

        # Extract video list
        videos = []
        if 'data' in data:
            for video in data['data']:
                # Only include actual videos (not shorts, playlists, etc.)
                if video.get('type') == 'video':
                    video_id = video.get('videoId')
                    # Get highest resolution thumbnail from RapidAPI response
                    # Array goes from low to high resolution, last item is typically maxresdefault
                    thumbnails = video.get('thumbnail', [])
                    thumbnail = thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

                    videos.append({
                        'video_id': video_id,
                        'title': video.get('title'),
                        'thumbnail': thumbnail,
                        'view_count': video.get('viewCountText', '0'),
                        'published_time': video.get('publishedTimeText', ''),
                        'length_text': video.get('lengthText', ''),
                        'is_short': False
                    })

        # Process shorts response
        try:
            shorts_data = shorts_response.json() if not isinstance(shorts_response, Exception) else {}

            if 'data' in shorts_data:
                for short in shorts_data['data']:
                    if short.get('type') == 'shorts':
                        video_id = short.get('videoId')
                        # Get highest resolution thumbnail from RapidAPI response
                        # Array goes from low to high resolution, last item is typically maxresdefault
                        thumbnails = short.get('thumbnail', [])
                        thumbnail = thumbnails[-1].get('url') if thumbnails else f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

                        videos.append({
                            'video_id': video_id,
                            'title': short.get('title'),
                            'thumbnail': thumbnail,
                            'view_count': short.get('viewCountText', '0'),
                            'published_time': '',
                            'length_text': 'Short',
                            'is_short': True
                        })

            logger.info(f"Fetched {len([v for v in videos if v.get('is_short')])} shorts for channel {channel_title}")
        except Exception as e:
            logger.warning(f"Could not fetch shorts: {e}")

        logger.info(f"Fetched {len(videos)} total videos (regular + shorts) for channel {channel_title}")

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

@bp.route('/api/get-private-videos', methods=['GET'])
@auth_required
@require_permission('optimize_video')
def get_private_videos():
    """Get user's private/unlisted YouTube videos using official YouTube API"""
    try:
        user_id = get_workspace_user_id()

        # Check cache first (15 minutes) - only if not forcing refresh
        force_refresh = request.args.get('refresh') == 'true'
        cache_ref = db.collection('users').document(user_id).collection('cache').document('private_videos')

        if not force_refresh:
            cache_doc = cache_ref.get()

            if cache_doc.exists:
                cache_data = cache_doc.to_dict()
                cache_time = cache_data.get('cached_at')
                cache_version = cache_data.get('version', 1)  # Add version check

                # Only use cache if it's version 2 (post-fix) and within 15 minutes
                if cache_version >= 2 and cache_time and (datetime.now(timezone.utc) - cache_time).total_seconds() < 900:
                    logger.info(f"Returning cached private videos for user {user_id}")
                    return jsonify({
                        'success': True,
                        'videos': cache_data.get('videos', []),
                        'from_cache': True
                    })

        # Get user's YouTube credentials
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials or not yt_analytics.channel_id:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected with proper permissions'
            }), 400

        # Build YouTube Data API client
        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Fetch all videos (including private/unlisted)
        # We check up to 100 most recent videos to find private/unlisted ones
        # API Cost: ~3 units (1 search call + 2 videos.list calls for status check)
        all_video_ids = []
        next_page_token = None
        MAX_VIDEOS_TO_CHECK = 100

        # First, get all video IDs
        while True:
            search_request = youtube.search().list(
                part='snippet',
                forMine=True,
                type='video',
                maxResults=50,
                pageToken=next_page_token,
                order='date'
            )
            response = search_request.execute()

            for item in response.get('items', []):
                video_id = item['id'].get('videoId')
                if video_id:
                    all_video_ids.append(video_id)

            next_page_token = response.get('nextPageToken')
            if not next_page_token or len(all_video_ids) >= MAX_VIDEOS_TO_CHECK:
                break

        # Now fetch video details to check privacy status
        videos = []
        if all_video_ids:
            # Fetch in batches of 50 (YouTube API limit)
            for i in range(0, len(all_video_ids), 50):
                batch_ids = all_video_ids[i:i+50]

                video_details = youtube.videos().list(
                    part='snippet,status,contentDetails',
                    id=','.join(batch_ids)
                ).execute()

                for video in video_details.get('items', []):
                    privacy_status = video['status'].get('privacyStatus', 'public')

                    # Only include private and unlisted videos
                    if privacy_status in ['private', 'unlisted']:
                        # Parse duration to detect shorts (ISO 8601 format like PT1M30S)
                        import re
                        duration_str = video['contentDetails'].get('duration', 'PT0S')
                        duration_seconds = 0

                        try:
                            # Parse ISO 8601 duration (e.g., PT1M30S = 90 seconds)
                            hours = re.search(r'(\d+)H', duration_str)
                            minutes = re.search(r'(\d+)M', duration_str)
                            seconds = re.search(r'(\d+)S', duration_str)

                            if hours:
                                duration_seconds += int(hours.group(1)) * 3600
                            if minutes:
                                duration_seconds += int(minutes.group(1)) * 60
                            if seconds:
                                duration_seconds += int(seconds.group(1))
                        except:
                            duration_seconds = 0

                        is_short = duration_seconds <= 60

                        videos.append({
                            'video_id': video['id'],
                            'title': video['snippet'].get('title'),
                            'thumbnail': video['snippet']['thumbnails'].get('medium', {}).get('url', ''),
                            'published_time': video['snippet'].get('publishedAt', ''),
                            'privacy_status': privacy_status,
                            'is_private': True,
                            'is_short': is_short,
                            'duration': duration_seconds
                        })

        logger.info(f"Fetched {len(videos)} private/unlisted videos for user {user_id}")

        # Cache the results with version number
        cache_ref.set({
            'videos': videos,
            'cached_at': datetime.now(timezone.utc),
            'version': 2  # Version 2 = properly filtered private/unlisted only
        })

        return jsonify({
            'success': True,
            'videos': videos,
            'from_cache': False
        })

    except Exception as e:
        logger.error(f"Error fetching private videos: {e}")

        # Check for YouTube quota exceeded error
        error_str = str(e)
        if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
            return jsonify({
                'success': False,
                'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                'error_type': 'quota_exceeded'
            }), 429

        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-info/<video_id>', methods=['GET'])
@auth_required
@require_permission('optimize_video')
def get_video_info(video_id):
    """Get basic video information without optimizing"""
    try:
        user_id = get_workspace_user_id()

        # Check if user has YouTube connected
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)
        has_youtube_connected = bool(yt_analytics.credentials)

        # Use VideoOptimizer to fetch video info
        optimizer = VideoOptimizer()
        video_info = optimizer.get_video_info(video_id, user_id)

        if not video_info:
            return jsonify({'success': False, 'error': 'Failed to fetch video information'}), 404

        return jsonify({
            'success': True,
            'data': video_info,
            'has_youtube_connected': has_youtube_connected
        })

    except Exception as e:
        logger.error(f"Error fetching video info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/optimize/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def optimize_video_analysis(video_id):
    """Optimize a specific video with AI analysis and recommendations"""
    try:
        user_id = get_workspace_user_id()
        user_subscription = get_user_subscription()

        # Get selected optimizations from request body
        request_data = request.get_json() or {}
        selected_optimizations = request_data.get('selected_optimizations', ['title', 'description', 'tags'])
        logger.info(f"Selected optimizations for {video_id}: {selected_optimizations}")

        # Check if optimization already exists in Firebase
        optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
        existing_doc = optimization_ref.get()

        if existing_doc.exists:
            # Check if cached data has the requested optimizations
            logger.info(f"Loading existing optimization from Firebase for user {user_id}: {video_id}")
            stored_data = existing_doc.to_dict()

            # Check which requested optimizations are missing from cache
            missing_optimizations = []
            if 'title' in selected_optimizations:
                titles = stored_data.get('title_suggestions', [])
                if not titles or len(titles) == 0 or not titles[0]:
                    missing_optimizations.append('title')
                    logger.info(f"Title missing from cache")

            if 'description' in selected_optimizations:
                desc = stored_data.get('optimized_description', '')
                if not desc or desc.strip() == '':
                    missing_optimizations.append('description')
                    logger.info(f"Description missing from cache")

            if 'tags' in selected_optimizations:
                tags = stored_data.get('optimized_tags', [])
                current_tags = stored_data.get('current_tags', [])
                logger.info(f"Checking tags: optimized={len(tags) if tags else 0}, current={len(current_tags) if current_tags else 0}")
                # Tags are missing if: empty, or same as current tags (not optimized)
                if not tags or len(tags) == 0 or tags == current_tags:
                    missing_optimizations.append('tags')
                    logger.info(f"Tags missing from cache or not optimized")

            logger.info(f"Missing optimizations: {missing_optimizations}")

            # If all requested optimizations are cached, return them
            if not missing_optimizations:
                title_suggestions = stored_data.get('title_suggestions', [])
                logger.info(f"Returning cached optimization with {len(title_suggestions)} titles")
                return jsonify({
                    'success': True,
                    'data': stored_data
                })
            else:
                # Some optimizations are missing - need to regenerate those
                logger.info(f"Cache missing optimizations: {missing_optimizations}. Will regenerate.")
                # Continue to generation below

        # If no optimizations selected (empty array), return error
        if not selected_optimizations or len(selected_optimizations) == 0:
            return jsonify({
                'success': False,
                'error': 'No optimizations selected'
            }), 400

        # Check if captions or pinned_comment are selected - these require YouTube API access
        requires_youtube_api = 'captions' in selected_optimizations or 'pinned_comment' in selected_optimizations

        if requires_youtube_api:
            # Verify user has YouTube connected
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            yt_analytics = YouTubeAnalytics(user_id)

            if not yt_analytics.credentials:
                return jsonify({
                    'success': False,
                    'error': 'YouTube account connection required for captions and pinned comments',
                    'error_type': 'no_youtube_connection'
                }), 400

        # Check credits before optimization (estimates ~5000 tokens)
        credits_manager = CreditsManager()
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content="video optimization" * 500,  # Rough estimate for video optimization
            model_name=None
        )

        required_credits = cost_estimate['final_cost']
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }), 402

        # Perform new optimization with selected features
        optimizer = VideoOptimizer()
        result = optimizer.optimize_video(video_id, user_id, user_subscription, selected_optimizations=selected_optimizations)

        if not result.get('success'):
            error_msg = result.get('error', 'Optimization failed')
            return jsonify({'success': False, 'error': error_msg}), 500

        # Get existing data to merge with new results (prevent overwriting previously generated optimizations)
        existing_data = {}
        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            logger.info(f"Merging new optimization data with existing cached data")

        # Save to Firebase - merge with existing data
        optimization_data = {
            **existing_data,  # Start with existing data
            # Always update these base fields
            'video_id': video_id,
            'video_info': result.get('video_info', {}) or existing_data.get('video_info', {}),
            'current_title': result.get('current_title', '') or existing_data.get('current_title', ''),
            'current_description': result.get('current_description', '') or existing_data.get('current_description', ''),
            'current_tags': result.get('current_tags', []) or existing_data.get('current_tags', []),
            'transcript_preview': result.get('transcript_preview', '') or existing_data.get('transcript_preview', ''),
            'optimized_at': datetime.now(timezone.utc)
        }

        # Only update fields that were actually generated in this request
        if 'title' in selected_optimizations:
            optimization_data['optimized_title'] = result.get('optimized_title', '')
            optimization_data['title_suggestions'] = result.get('title_suggestions', [])

        if 'description' in selected_optimizations:
            optimization_data['optimized_description'] = result.get('optimized_description', '')

        if 'tags' in selected_optimizations:
            optimization_data['optimized_tags'] = result.get('optimized_tags', [])

        # Always include recommendations if present (or preserve existing)
        if result.get('recommendations'):
            optimization_data['recommendations'] = result.get('recommendations', {})
        elif 'recommendations' not in optimization_data:
            optimization_data['recommendations'] = {}

        # Add captions result if present
        captions_result = result.get('corrected_captions_result')
        if captions_result and captions_result.get('success'):
            optimization_data['corrected_captions'] = {
                'original_srt': captions_result.get('original_srt', ''),
                'corrected_srt': captions_result.get('corrected_srt', ''),
                'corrected_segments': captions_result.get('corrected_segments', 0),
                'message': captions_result.get('message', ''),
                'preview': captions_result.get('preview', True),
                'generated_at': datetime.now(timezone.utc)
            }

        # Add pinned comment result if present
        pinned_comment_result = result.get('pinned_comment_result')
        if pinned_comment_result and pinned_comment_result.get('success'):
            optimization_data['pinned_comment'] = {
                'comment_text': pinned_comment_result.get('comment_text', ''),
                'message': pinned_comment_result.get('message', ''),
                'preview': pinned_comment_result.get('preview', True),
                'generated_at': datetime.now(timezone.utc)
            }

        optimization_ref.set(optimization_data)
        logger.info(f"Saved video optimization to Firebase for user {user_id}: {video_id}")

        # Deduct credits for ALL AI operations
        all_token_usages = result.get('all_token_usages', [])
        if all_token_usages:
            logger.info(f"Deducting credits for {len(all_token_usages)} AI operations")

            for token_usage in all_token_usages:
                operation_name = token_usage.get('operation', 'Unknown')
                input_tokens = token_usage.get('input_tokens', 0)
                output_tokens = token_usage.get('output_tokens', 0)

                if input_tokens > 0 or output_tokens > 0:
                    logger.info(f"Deducting credits for {operation_name}: {input_tokens} input, {output_tokens} output tokens")

                    # Convert provider_enum string back to AIProvider enum if present
                    provider_enum_str = token_usage.get('provider_enum')
                    provider_enum = None
                    if provider_enum_str:
                        try:
                            provider_enum = AIProvider(provider_enum_str)
                        except (ValueError, KeyError):
                            logger.warning(f"Invalid provider enum value: {provider_enum_str}")

                    deduction_result = credits_manager.deduct_llm_credits(
                        user_id=user_id,
                        model_name=token_usage.get('model', None),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        description=f"Video Optimization - {operation_name} - {video_id}",
                        provider_enum=provider_enum
                    )

                    if not deduction_result['success']:
                        logger.error(f"Failed to deduct credits for {operation_name}: {deduction_result.get('message')}")
                        return jsonify({
                            'success': False,
                            'error': f'Credit deduction failed for {operation_name}',
                            'error_type': 'insufficient_credits'
                        }), 402
        else:
            logger.warning(f"No token usage information found for video {video_id}")

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

            # Convert timestamps
            if doc_data.get('optimized_at'):
                doc_data['optimized_at'] = doc_data['optimized_at'].isoformat()

            # Convert nested timestamps in captions
            if doc_data.get('corrected_captions'):
                if doc_data['corrected_captions'].get('generated_at'):
                    doc_data['corrected_captions']['generated_at'] = doc_data['corrected_captions']['generated_at'].isoformat()
                if doc_data['corrected_captions'].get('applied_at'):
                    doc_data['corrected_captions']['applied_at'] = doc_data['corrected_captions']['applied_at'].isoformat()

            # Convert nested timestamps in pinned comment
            if doc_data.get('pinned_comment'):
                if doc_data['pinned_comment'].get('generated_at'):
                    doc_data['pinned_comment']['generated_at'] = doc_data['pinned_comment']['generated_at'].isoformat()
                if doc_data['pinned_comment'].get('applied_at'):
                    doc_data['pinned_comment']['applied_at'] = doc_data['pinned_comment']['applied_at'].isoformat()

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

@bp.route('/api/upload-thumbnail/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def upload_thumbnail(video_id):
    """Upload a custom thumbnail to YouTube video"""
    try:
        user_id = get_workspace_user_id()

        # Check if file was uploaded
        if 'thumbnail' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No thumbnail file provided'
            }), 400

        file = request.files['thumbnail']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Validate file type
        allowed_types = {'image/jpeg', 'image/jpg', 'image/png'}
        if file.content_type not in allowed_types:
            return jsonify({
                'success': False,
                'error': 'Only JPG and PNG images are supported'
            }), 400

        # Read file into memory
        file_content = file.read()

        # Validate file size (2MB limit)
        if len(file_content) > 2 * 1024 * 1024:
            return jsonify({
                'success': False,
                'error': 'Image must be smaller than 2MB'
            }), 400

        # Upload to YouTube
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected'
            }), 400

        # Build YouTube Data API client
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload
        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Upload thumbnail
        media = MediaInMemoryUpload(file_content, mimetype=file.content_type, resumable=True)

        youtube.thumbnails().set(
            videoId=video_id,
            media_body=media
        ).execute()

        logger.info(f"Thumbnail uploaded successfully for video {video_id} by user {user_id}")

        return jsonify({
            'success': True,
            'message': 'Thumbnail uploaded successfully'
        })

    except Exception as e:
        logger.error(f"Error uploading thumbnail: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to upload thumbnail: {str(e)}'
        }), 500

@bp.route('/api/set-video-public/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def set_video_public(video_id):
    """Set a video's privacy status to public"""
    try:
        user_id = get_workspace_user_id()

        # Build YouTube Data API client
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected'
            }), 400

        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Update video privacy status
        youtube.videos().update(
            part='status',
            body={
                'id': video_id,
                'status': {
                    'privacyStatus': 'public'
                }
            }
        ).execute()

        logger.info(f"Video {video_id} set to public by user {user_id}")

        # Clear private videos cache since this video is now public
        cache_ref = db.collection('users').document(user_id).collection('cache').document('private_videos')
        cache_ref.delete()

        return jsonify({
            'success': True,
            'message': 'Video is now public'
        })

    except Exception as e:
        logger.error(f"Error setting video to public: {e}")

        # Check for YouTube quota exceeded error
        error_str = str(e)
        if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
            return jsonify({
                'success': False,
                'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                'error_type': 'quota_exceeded'
            }), 429

        return jsonify({
            'success': False,
            'error': f'Failed to update video visibility: {str(e)}'
        }), 500

@bp.route('/api/set-video-private/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def set_video_private(video_id):
    """Set a video's privacy status to private"""
    try:
        user_id = get_workspace_user_id()

        # Build YouTube Data API client
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected'
            }), 400

        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Update video privacy status
        youtube.videos().update(
            part='status',
            body={
                'id': video_id,
                'status': {
                    'privacyStatus': 'private'
                }
            }
        ).execute()

        logger.info(f"Video {video_id} set to private by user {user_id}")

        # Clear private videos cache to refresh it
        cache_ref = db.collection('users').document(user_id).collection('cache').document('private_videos')
        cache_ref.delete()

        return jsonify({
            'success': True,
            'message': 'Video is now private'
        })

    except Exception as e:
        logger.error(f"Error setting video to private: {e}")

        # Check for YouTube quota exceeded error
        error_str = str(e)
        if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
            return jsonify({
                'success': False,
                'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                'error_type': 'quota_exceeded'
            }), 429

        return jsonify({
            'success': False,
            'error': f'Failed to update video visibility: {str(e)}'
        }), 500

@bp.route('/api/delete-video/<video_id>', methods=['DELETE'])
@auth_required
@require_permission('optimize_video')
def delete_video(video_id):
    """Delete a video from YouTube"""
    try:
        user_id = get_workspace_user_id()

        # Build YouTube Data API client
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected'
            }), 400

        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Delete the video
        youtube.videos().delete(id=video_id).execute()

        logger.info(f"Video {video_id} deleted by user {user_id}")

        # Delete optimization data from Firebase if exists
        optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
        optimization_ref.delete()

        # Clear caches
        cache_ref = db.collection('users').document(user_id).collection('cache').document('private_videos')
        cache_ref.delete()

        return jsonify({
            'success': True,
            'message': 'Video deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting video: {e}")

        # Check for YouTube quota exceeded error
        error_str = str(e)
        if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
            return jsonify({
                'success': False,
                'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                'error_type': 'quota_exceeded'
            }), 429

        return jsonify({
            'success': False,
            'error': f'Failed to delete video: {str(e)}'
        }), 500

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

        # Check for YouTube quota exceeded error
        error_str = str(e)
        if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
            return jsonify({
                'success': False,
                'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                'error_type': 'quota_exceeded'
            }), 429

        return jsonify({
            'success': False,
            'error': f'Failed to apply optimizations: {str(e)}'
        }), 500

@bp.route('/api/correct-captions/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def correct_captions(video_id):
    """Correct English captions for a video"""
    try:
        user_id = get_workspace_user_id()
        user_subscription = get_user_subscription()

        # Perform caption correction
        optimizer = VideoOptimizer()
        result = optimizer.correct_english_captions(video_id, user_id, user_subscription)

        if not result.get('success'):
            error_type = result.get('error_type', 'unknown')
            error_msg = result.get('error', 'Caption correction failed')

            # Return appropriate status codes for different errors
            if error_type == 'no_youtube_connection':
                return jsonify(result), 400
            elif error_type in ['no_captions', 'no_english_captions']:
                return jsonify(result), 404
            else:
                return jsonify(result), 500

        # Deduct credits for AI usage
        token_usage = result.get('token_usage')
        if token_usage and token_usage.get('input_tokens', 0) > 0:
            credits_manager = CreditsManager()
            from app.system.ai_provider.ai_provider import AIProvider

            provider_enum_str = token_usage.get('provider_enum')
            provider_enum = None
            if provider_enum_str:
                try:
                    provider_enum = AIProvider(provider_enum_str)
                except (ValueError, KeyError):
                    logger.warning(f"Invalid provider enum value: {provider_enum_str}")

            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=token_usage.get('model'),
                input_tokens=token_usage.get('input_tokens', 0),
                output_tokens=token_usage.get('output_tokens', 0),
                description=f"Caption Correction - {video_id}",
                provider_enum=provider_enum
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                return jsonify({
                    'success': False,
                    'error': 'Credit deduction failed',
                    'error_type': 'insufficient_credits'
                }), 402

        logger.info(f"Successfully corrected captions for video {video_id} by user {user_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error correcting captions: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to correct captions: {str(e)}'
        }), 500

@bp.route('/api/generate-chapters/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def generate_chapters(video_id):
    """Generate chapters/timestamps for a video"""
    try:
        user_id = get_workspace_user_id()
        user_subscription = get_user_subscription()

        # Get target keyword if video was uploaded via Upload Studio
        target_keyword = None
        try:
            uploaded_video_ref = db.collection('users').document(user_id).collection('uploaded_videos').document(video_id)
            uploaded_video_doc = uploaded_video_ref.get()

            if uploaded_video_doc.exists:
                video_metadata = uploaded_video_doc.to_dict()
                target_keyword = video_metadata.get('target_keyword')
        except Exception as e:
            logger.warning(f"Could not retrieve target keyword: {e}")

        # Generate chapters
        optimizer = VideoOptimizer()
        result = optimizer.generate_chapters(video_id, user_id, target_keyword, user_subscription)

        if not result.get('success'):
            error_type = result.get('error_type', 'unknown')

            if error_type == 'no_transcript':
                return jsonify(result), 404
            else:
                return jsonify(result), 500

        # Deduct credits for AI usage
        token_usage = result.get('token_usage')
        if token_usage and token_usage.get('input_tokens', 0) > 0:
            credits_manager = CreditsManager()
            from app.system.ai_provider.ai_provider import AIProvider

            provider_enum_str = token_usage.get('provider_enum')
            provider_enum = None
            if provider_enum_str:
                try:
                    provider_enum = AIProvider(provider_enum_str)
                except (ValueError, KeyError):
                    logger.warning(f"Invalid provider enum value: {provider_enum_str}")

            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=token_usage.get('model'),
                input_tokens=token_usage.get('input_tokens', 0),
                output_tokens=token_usage.get('output_tokens', 0),
                description=f"Chapter Generation - {video_id}",
                provider_enum=provider_enum
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                return jsonify({
                    'success': False,
                    'error': 'Credit deduction failed',
                    'error_type': 'insufficient_credits'
                }), 402

        logger.info(f"Successfully generated {result.get('num_chapters')} chapters for video {video_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error generating chapters: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to generate chapters: {str(e)}'
        }), 500

@bp.route('/api/post-pinned-comment/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def post_pinned_comment(video_id):
    """Generate and post a pinned comment for a video"""
    try:
        user_id = get_workspace_user_id()
        user_subscription = get_user_subscription()

        # Get video title and target keyword if available
        video_title = None
        target_keyword = None

        try:
            # Check optimization data first
            optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
            optimization_doc = optimization_ref.get()

            if optimization_doc.exists:
                optimization_data = optimization_doc.to_dict()
                video_title = optimization_data.get('current_title')

            # Check Upload Studio data for target keyword
            uploaded_video_ref = db.collection('users').document(user_id).collection('uploaded_videos').document(video_id)
            uploaded_video_doc = uploaded_video_ref.get()

            if uploaded_video_doc.exists:
                video_metadata = uploaded_video_doc.to_dict()
                target_keyword = video_metadata.get('target_keyword')
                if not video_title:
                    video_title = video_metadata.get('title')

        except Exception as e:
            logger.warning(f"Could not retrieve video metadata: {e}")

        # Generate and post comment
        optimizer = VideoOptimizer()
        result = optimizer.generate_and_post_pinned_comment(video_id, user_id, video_title, target_keyword, user_subscription)

        if not result.get('success'):
            error_type = result.get('error_type', 'unknown')

            if error_type == 'no_youtube_connection':
                return jsonify(result), 400
            else:
                return jsonify(result), 500

        # Deduct credits for AI usage
        token_usage = result.get('token_usage')
        if token_usage and token_usage.get('input_tokens', 0) > 0:
            credits_manager = CreditsManager()
            from app.system.ai_provider.ai_provider import AIProvider

            provider_enum_str = token_usage.get('provider_enum')
            provider_enum = None
            if provider_enum_str:
                try:
                    provider_enum = AIProvider(provider_enum_str)
                except (ValueError, KeyError):
                    logger.warning(f"Invalid provider enum value: {provider_enum_str}")

            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=token_usage.get('model'),
                input_tokens=token_usage.get('input_tokens', 0),
                output_tokens=token_usage.get('output_tokens', 0),
                description=f"Pinned Comment - {video_id}",
                provider_enum=provider_enum
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                return jsonify({
                    'success': False,
                    'error': 'Credit deduction failed',
                    'error_type': 'insufficient_credits'
                }), 402

        logger.info(f"Successfully posted pinned comment for video {video_id}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error posting pinned comment: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to post pinned comment: {str(e)}'
        }), 500

@bp.route('/api/apply-captions/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def apply_captions(video_id):
    """Apply previously corrected captions to YouTube"""
    try:
        user_id = get_workspace_user_id()
        request_data = request.get_json()
        corrected_srt = request_data.get('corrected_srt')

        if not corrected_srt:
            return jsonify({
                'success': False,
                'error': 'No caption data provided'
            }), 400

        # Apply captions
        from app.scripts.optimize_video.caption_correction import CaptionCorrector
        corrector = CaptionCorrector()
        result = corrector.apply_corrected_captions(video_id, user_id, corrected_srt)

        if not result.get('success'):
            error_type = result.get('error_type', 'unknown')
            if error_type == 'quota_exceeded':
                return jsonify(result), 429
            elif error_type == 'no_youtube_connection':
                return jsonify(result), 400
            else:
                return jsonify(result), 500

        # Update Firebase to mark captions as applied
        try:
            optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
            optimization_ref.update({
                'corrected_captions.preview': False,
                'corrected_captions.applied_at': datetime.now(timezone.utc)
            })
        except Exception as e:
            logger.warning(f"Could not update caption application status: {e}")

        logger.info(f"Successfully applied captions to video {video_id}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error applying captions: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to apply captions: {str(e)}'
        }), 500

@bp.route('/api/apply-pinned-comment/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def apply_pinned_comment(video_id):
    """Apply previously generated pinned comment to YouTube"""
    try:
        user_id = get_workspace_user_id()
        request_data = request.get_json()
        comment_text = request_data.get('comment_text')

        if not comment_text:
            return jsonify({
                'success': False,
                'error': 'No comment text provided'
            }), 400

        # Apply pinned comment
        from app.scripts.optimize_video.pinned_comment_generator import PinnedCommentGenerator
        generator = PinnedCommentGenerator()
        result = generator.apply_pinned_comment(video_id, user_id, comment_text)

        if not result.get('success'):
            error_type = result.get('error_type', 'unknown')
            if error_type == 'quota_exceeded':
                return jsonify(result), 429
            elif error_type == 'no_youtube_connection':
                return jsonify(result), 400
            else:
                return jsonify(result), 500

        # Update Firebase to mark pinned comment as applied
        try:
            optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
            optimization_ref.update({
                'pinned_comment.preview': False,
                'pinned_comment.applied_at': datetime.now(timezone.utc),
                'pinned_comment.comment_id': result.get('comment_id')
            })
        except Exception as e:
            logger.warning(f"Could not update pinned comment application status: {e}")

        logger.info(f"Successfully applied pinned comment to video {video_id}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error applying pinned comment: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to apply pinned comment: {str(e)}'
        }), 500

@bp.route('/api/reset-applied-status/<video_id>', methods=['POST'])
@auth_required
@require_permission('optimize_video')
def reset_applied_status(video_id):
    """Reset applied status when user edits content"""
    try:
        user_id = get_workspace_user_id()
        request_data = request.get_json()
        content_type = request_data.get('type')  # 'description', 'captions', or 'pinned_comment'

        if not content_type:
            return jsonify({
                'success': False,
                'error': 'Content type is required'
            }), 400

        # Get optimization document
        optimization_ref = db.collection('users').document(user_id).collection('video_optimizations').document(video_id)
        optimization_doc = optimization_ref.get()

        if not optimization_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Optimization not found'
            }), 404

        # Update based on content type
        update_data = {}
        if content_type == 'description':
            # Clear applied_description_at timestamp
            update_data['applied_description_at'] = None
        elif content_type == 'captions':
            # Set preview back to true
            update_data['corrected_captions.preview'] = True
            update_data['corrected_captions.applied_at'] = None
        elif content_type == 'pinned_comment':
            # Set preview back to true
            update_data['pinned_comment.preview'] = True
            update_data['pinned_comment.applied_at'] = None

        if update_data:
            optimization_ref.update(update_data)
            logger.info(f"Reset applied status for {content_type} on video {video_id}")

        return jsonify({
            'success': True
        })

    except Exception as e:
        logger.error(f"Error resetting applied status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
