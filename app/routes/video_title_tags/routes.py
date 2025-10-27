from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
from app.scripts.video_title.video_tags import VideoTagsGenerator
from app.scripts.video_title.video_description import VideoDescriptionGenerator
from app.system.services.firebase_service import db
from datetime import datetime, timezone
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
    """Get user's saved reference descriptions"""
    try:
        user_id = get_workspace_user_id()

        # Get user's reference descriptions from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({
                'success': True,
                'reference_description_long': '',
                'reference_description_short': ''
            })

        user_data = user_doc.to_dict()
        reference_description_long = user_data.get('reference_description_long', '')
        reference_description_short = user_data.get('reference_description_short', '')

        # Backwards compatibility: check old field
        if not reference_description_long and not reference_description_short:
            old_reference = user_data.get('reference_description', '')
            if old_reference:
                reference_description_long = old_reference

        return jsonify({
            'success': True,
            'reference_description_long': reference_description_long,
            'reference_description_short': reference_description_short
        })

    except Exception as e:
        logger.error(f"Error getting reference description: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/save-reference-description', methods=['POST'])
@auth_required
@require_permission('video_title')
def save_reference_description():
    """Save user's reference descriptions to Firestore"""
    try:
        user_id = get_workspace_user_id()
        data = request.json
        reference_description_long = data.get('reference_description_long', '').strip()
        reference_description_short = data.get('reference_description_short', '').strip()

        # Update user's reference descriptions in Firestore
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'reference_description_long': reference_description_long,
            'reference_description_short': reference_description_short
        })

        logger.info(f"Saved reference descriptions for user {user_id} (long: {len(reference_description_long)} chars, short: {len(reference_description_short)} chars)")

        return jsonify({
            'success': True,
            'message': 'Reference descriptions saved successfully'
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

@bp.route('/api/upload-video-temp', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_video_temp():
    """Legacy endpoint - no longer needed. Videos upload directly to YouTube from browser."""
    return jsonify({
        'success': False,
        'error': 'This endpoint is deprecated. Videos now upload directly to YouTube.'
    }), 410

@bp.route('/api/delete-temp-video', methods=['POST'])
@auth_required
@require_permission('video_title')
def delete_temp_video():
    """No-op endpoint - videos are no longer uploaded to temp storage, they're held in browser memory"""
    return jsonify({
        'success': True,
        'message': 'No cleanup needed - video is only in browser memory'
    })

@bp.route('/api/upload-thumbnail-temp', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_thumbnail_temp():
    """Temporarily upload thumbnail to server"""
    try:
        user_id = get_workspace_user_id()

        if 'thumbnail' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No thumbnail file provided'
            }), 400

        thumbnail_file = request.files['thumbnail']

        if thumbnail_file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No thumbnail file selected'
            }), 400

        # Validate file type
        if thumbnail_file.content_type not in ['image/jpeg', 'image/jpg', 'image/png']:
            return jsonify({
                'success': False,
                'error': 'Only JPG and PNG images are supported'
            }), 400

        # Create temp directory for thumbnails
        temp_dir = os.path.join(tempfile.gettempdir(), 'thumbnail_uploads', user_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Generate filename
        filename = secure_filename(thumbnail_file.filename)
        file_path = os.path.join(temp_dir, filename)

        # Save the file
        thumbnail_file.save(file_path)

        logger.info(f"Temporarily uploaded thumbnail for user {user_id}: {filename} ({os.path.getsize(file_path)} bytes)")

        return jsonify({
            'success': True,
            'thumbnail_path': file_path,
            'filename': filename,
            'message': 'Thumbnail uploaded successfully'
        })

    except Exception as e:
        logger.error(f"Error uploading thumbnail temp: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to upload thumbnail: {str(e)}'
        }), 500

@bp.route('/api/check-youtube-connection', methods=['GET'])
@auth_required
def check_youtube_connection():
    """Check if user has YouTube connected"""
    try:
        user_id = get_workspace_user_id()

        # Get user's YouTube channel info from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'connected': False})

        user_data = user_doc.to_dict()

        # Check if YouTube is connected
        youtube_channel_id = user_data.get('youtube_channel_id', '')
        youtube_account = user_data.get('youtube_account', '')

        return jsonify({
            'connected': bool(youtube_channel_id and youtube_account)
        })

    except Exception as e:
        logger.error(f"Error checking YouTube connection: {e}")
        return jsonify({'connected': False})

@bp.route('/api/init-youtube-upload', methods=['POST'])
@auth_required
@require_permission('video_title')
def init_youtube_upload():
    """Initialize YouTube resumable upload and return upload URL"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        tags = data.get('tags', [])
        privacy_status = data.get('privacy_status', 'private')
        language = data.get('language', 'en')
        scheduled_time = data.get('scheduled_time')
        file_size = data.get('file_size', 0)
        mime_type = data.get('mime_type', 'video/*')

        if not title:
            return jsonify({
                'success': False,
                'error': 'Title is required'
            }), 400

        # Get YouTube credentials
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected. Please connect your YouTube account first.'
            }), 400

        # Build YouTube Data API client
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import json

        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Prepare video metadata
        request_body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags[:500] if len(tags) > 500 else tags,
                'categoryId': '22',
                'defaultLanguage': language,
                'defaultAudioLanguage': language
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        # Add scheduled publish time if provided
        if scheduled_time:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(scheduled_time)
                request_body['status']['publishAt'] = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                logger.info(f"Video scheduled for: {request_body['status']['publishAt']}")
            except Exception as e:
                logger.warning(f"Could not parse scheduled time: {e}")

        # Initialize resumable upload
        import requests

        # Get access token
        access_token = yt_analytics.credentials.token

        # Create resumable upload session
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Upload-Content-Length': str(file_size),
            'X-Upload-Content-Type': mime_type
        }

        init_url = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'

        init_response = requests.post(
            init_url,
            headers=headers,
            json=request_body
        )

        if init_response.status_code not in [200, 201]:
            logger.error(f"Failed to initialize upload: {init_response.text}")
            return jsonify({
                'success': False,
                'error': 'Failed to initialize YouTube upload'
            }), 500

        # Get upload URL from Location header
        upload_url = init_response.headers.get('Location')

        if not upload_url:
            logger.error("No upload URL in response")
            return jsonify({
                'success': False,
                'error': 'Failed to get upload URL'
            }), 500

        # Extract video ID from upload URL (we'll get it after upload completes)
        # For now, we'll return the upload URL and handle video ID in finalize

        logger.info(f"Initialized resumable upload for user {user_id}")

        return jsonify({
            'success': True,
            'upload_url': upload_url,
            'message': 'Upload initialized successfully'
        })

    except Exception as e:
        logger.error(f"Error initializing YouTube upload: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to initialize upload: {str(e)}'
        }), 500

@bp.route('/api/finalize-youtube-upload', methods=['POST'])
@auth_required
@require_permission('video_title')
def finalize_youtube_upload():
    """Finalize YouTube upload (handle thumbnail, store metadata)"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        video_id = data.get('video_id', '').strip()
        thumbnail_path = data.get('thumbnail_path')
        target_keyword = data.get('target_keyword', '').strip()

        if not video_id:
            return jsonify({
                'success': False,
                'error': 'Video ID is required'
            }), 400

        # Get YouTube credentials
        from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
        yt_analytics = YouTubeAnalytics(user_id)

        if not yt_analytics.credentials:
            return jsonify({
                'success': False,
                'error': 'No YouTube account connected'
            }), 400

        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Upload thumbnail if provided
        if thumbnail_path:
            import os
            if os.path.exists(thumbnail_path):
                try:
                    import mimetypes
                    mimetype, _ = mimetypes.guess_type(thumbnail_path)
                    if not mimetype:
                        mimetype = 'image/jpeg'

                    from googleapiclient.http import MediaFileUpload
                    thumbnail_media = MediaFileUpload(thumbnail_path, mimetype=mimetype, resumable=True)

                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=thumbnail_media
                    ).execute()

                    logger.info(f"Thumbnail uploaded successfully for video {video_id}")
                except Exception as e:
                    logger.error(f"Error uploading thumbnail: {e}")
                finally:
                    # Clean up thumbnail file
                    try:
                        os.unlink(thumbnail_path)
                    except Exception as e:
                        logger.error(f"Error deleting thumbnail file: {e}")

        # Store video metadata in Firestore
        try:
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

            video_metadata = {
                'video_id': video_id,
                'thumbnail_url': thumbnail_url,
                'uploaded_at': datetime.now(timezone.utc),
                'uploaded_via': 'upload_studio'
            }

            if target_keyword:
                video_metadata['target_keyword'] = target_keyword

            db.collection('users').document(user_id).collection('uploaded_videos').document(video_id).set(video_metadata)
            logger.info(f"Stored video metadata in Firestore for video {video_id}")

        except Exception as e:
            logger.error(f"Error storing video metadata in Firestore: {e}")

        return jsonify({
            'success': True,
            'message': 'Upload finalized successfully'
        })

    except Exception as e:
        logger.error(f"Error finalizing YouTube upload: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to finalize upload: {str(e)}'
        }), 500

@bp.route('/api/upload-youtube-video', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_youtube_video():
    """Legacy endpoint - kept for backward compatibility. Use init-youtube-upload + finalize-youtube-upload instead."""
    return jsonify({
        'success': False,
        'error': 'This endpoint is deprecated. Please use the new direct upload flow.'
    }), 410
