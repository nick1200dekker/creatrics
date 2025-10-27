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
    """Temporarily upload video to server"""
    try:
        user_id = get_workspace_user_id()

        # Check if file is uploaded
        if 'video' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No video file provided'
            }), 400

        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No video file selected'
            }), 400

        # Validate file type
        if not video_file.content_type.startswith('video/'):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Please upload a video file.'
            }), 400

        # Save to temporary location
        import tempfile
        import os
        from werkzeug.utils import secure_filename

        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(tempfile.gettempdir(), 'video_uploads', user_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Generate filename
        filename = secure_filename(video_file.filename)
        file_path = os.path.join(temp_dir, filename)

        # Save the file
        video_file.save(file_path)

        logger.info(f"Temporarily uploaded video for user {user_id}: {filename} ({os.path.getsize(file_path)} bytes)")

        return jsonify({
            'success': True,
            'video_path': file_path,
            'filename': filename,
            'message': 'Video uploaded successfully'
        })

    except Exception as e:
        logger.error(f"Error uploading video temp: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to upload video: {str(e)}'
        }), 500

@bp.route('/api/delete-temp-video', methods=['POST'])
@auth_required
@require_permission('video_title')
def delete_temp_video():
    """Delete temporarily uploaded video from Firebase Storage or server"""
    try:
        data = request.get_json()
        video_path = data.get('video_path', '').strip()

        if not video_path:
            return jsonify({
                'success': False,
                'error': 'No video path provided'
            }), 400

        # Check if it's a Firebase Storage path
        if video_path.startswith('temp_videos/'):
            # Delete from Firebase Storage
            from app.system.services.firebase_service import storage_bucket
            try:
                blob = storage_bucket.blob(video_path)
                blob.delete()
                logger.info(f"Deleted video from Firebase Storage: {video_path}")

                return jsonify({
                    'success': True,
                    'message': 'Video deleted successfully from cloud storage'
                })
            except Exception as e:
                logger.error(f"Error deleting from Firebase Storage: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to delete video from cloud storage: {str(e)}'
                }), 500
        else:
            # Legacy: Delete from local temp directory
            import os
            import tempfile
            temp_base = os.path.join(tempfile.gettempdir(), 'video_uploads')
            if not video_path.startswith(temp_base):
                logger.warning(f"Attempted to delete file outside temp directory: {video_path}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid video path'
                }), 400

            # Delete the file if it exists
            if os.path.exists(video_path):
                os.unlink(video_path)
                logger.info(f"Deleted temporary video: {video_path}")

            return jsonify({
                'success': True,
                'message': 'Video deleted successfully'
            })

    except Exception as e:
        logger.error(f"Error deleting temp video: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to delete video: {str(e)}'
        }), 500

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

@bp.route('/api/upload-youtube-video', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_youtube_video():
    """Upload a video to YouTube with title, description, and tags"""
    try:
        user_id = get_workspace_user_id()

        # Get metadata from request (now JSON instead of form)
        data = request.get_json()

        video_path = data.get('video_path', '').strip()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        tags = data.get('tags', [])
        privacy_status = data.get('privacy_status', 'private')
        language = data.get('language', 'en')  # Default to English
        thumbnail_path = data.get('thumbnail_path')  # Optional server path to thumbnail
        scheduled_time = data.get('scheduled_time')  # Optional scheduled publish time (ISO 8601 format)
        target_keyword = data.get('target_keyword', '').strip()  # Store for Optimize Video later

        # Check if video path is provided
        if not video_path:
            return jsonify({
                'success': False,
                'error': 'No video file provided'
            }), 400

        # Download video from Firebase Storage to temp file
        import os
        import tempfile
        from app.system.services.firebase_service import storage_bucket

        # Create temp directory
        temp_dir = tempfile.mkdtemp()

        try:
            # Check if video_path is Firebase Storage path or local path
            if video_path.startswith('temp_videos/'):
                # Firebase Storage path - download it
                blob = storage_bucket.blob(video_path)

                # Extract filename from path
                filename = os.path.basename(video_path)
                local_video_path = os.path.join(temp_dir, filename)

                # Download to local temp file
                logger.info(f"Downloading video from Firebase Storage: {video_path}")
                blob.download_to_filename(local_video_path)
                logger.info(f"Downloaded video to: {local_video_path} ({os.path.getsize(local_video_path)} bytes)")

                video_path = local_video_path
            else:
                # Local path - verify it exists
                if not os.path.exists(video_path):
                    return jsonify({
                        'success': False,
                        'error': 'Video file not found. Please upload the video again.'
                    }), 400

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

        youtube = build('youtube', 'v3', credentials=yt_analytics.credentials)

        # Rename video file for SEO (use title as filename)
        import re
        # Create safe filename from title
        safe_title = re.sub(r'[^\w\s-]', '', title)  # Remove special chars
        safe_title = re.sub(r'[-\s]+', '-', safe_title)  # Replace spaces/dashes with single dash
        safe_title = safe_title.strip('-')[:100]  # Limit length and trim dashes

        # Get original file extension
        original_ext = os.path.splitext(video_path)[1]

        # Create new path with SEO-friendly filename
        video_dir = os.path.dirname(video_path)
        seo_video_path = os.path.join(video_dir, f"{safe_title}{original_ext}")

        # Rename the file
        try:
            os.rename(video_path, seo_video_path)
            video_path = seo_video_path
            logger.info(f"Renamed video file for SEO: {safe_title}{original_ext}")
        except Exception as e:
            logger.warning(f"Could not rename video file: {e}, using original path")

        # Upload video to YouTube
        logger.info(f"Uploading video to YouTube for user {user_id}: {title}")

        request_body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags[:500] if len(tags) > 500 else tags,  # YouTube allows max 500 tags
                'categoryId': '22',  # People & Blogs category
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
            # Convert HTML datetime-local format to YouTube API format (ISO 8601)
            try:
                dt = datetime.fromisoformat(scheduled_time)
                request_body['status']['publishAt'] = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                logger.info(f"Video scheduled for: {request_body['status']['publishAt']}")
            except Exception as e:
                logger.warning(f"Could not parse scheduled time: {e}")

        media_file = MediaFileUpload(video_path, resumable=True)

        upload_request = youtube.videos().insert(
            part='snippet,status',
            body=request_body,
            media_body=media_file
        )

        response = None
        while response is None:
            status, response = upload_request.next_chunk()
            if status:
                logger.info(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response['id']
        logger.info(f"Video uploaded successfully: {video_id}")

        # Upload thumbnail if provided
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                # Rename thumbnail file for SEO (use title as filename)
                thumbnail_ext = os.path.splitext(thumbnail_path)[1]
                thumbnail_dir = os.path.dirname(thumbnail_path)
                seo_thumbnail_path = os.path.join(thumbnail_dir, f"{safe_title}-thumbnail{thumbnail_ext}")

                try:
                    os.rename(thumbnail_path, seo_thumbnail_path)
                    thumbnail_path = seo_thumbnail_path
                    logger.info(f"Renamed thumbnail file for SEO: {safe_title}-thumbnail{thumbnail_ext}")
                except Exception as e:
                    logger.warning(f"Could not rename thumbnail file: {e}, using original path")

                # Detect mimetype from file extension
                import mimetypes
                mimetype, _ = mimetypes.guess_type(thumbnail_path)
                if not mimetype:
                    mimetype = 'image/jpeg'  # Default

                # Upload thumbnail to YouTube
                from googleapiclient.http import MediaFileUpload as MediaUpload
                thumbnail_media = MediaUpload(thumbnail_path, mimetype=mimetype, resumable=True)

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

        # Clean up temporary video file and Firebase Storage
        try:
            os.unlink(video_path)
            logger.info(f"Cleaned up temporary video file: {video_path}")

            # Delete from Firebase Storage if it was a Firebase upload
            if data.get('video_path', '').startswith('temp_videos/'):
                try:
                    firebase_path = data.get('video_path', '')
                    blob = storage_bucket.blob(firebase_path)
                    blob.delete()
                    logger.info(f"Deleted video from Firebase Storage: {firebase_path}")
                except Exception as e:
                    logger.warning(f"Error deleting video from Firebase Storage: {e}")

            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Error deleting video file: {e}")

        # Store video metadata in Firestore for Optimize Video later
        try:
            # Get thumbnail URL from YouTube response
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
            if 'snippet' in response and 'thumbnails' in response['snippet']:
                thumbnails = response['snippet']['thumbnails']
                # Try to get highest quality thumbnail
                if 'maxres' in thumbnails:
                    thumbnail_url = thumbnails['maxres']['url']
                elif 'high' in thumbnails:
                    thumbnail_url = thumbnails['high']['url']
                elif 'medium' in thumbnails:
                    thumbnail_url = thumbnails['medium']['url']

            # Store in Firestore
            video_metadata = {
                'video_id': video_id,
                'title': title,
                'thumbnail_url': thumbnail_url,
                'uploaded_at': datetime.now(timezone.utc),
                'uploaded_via': 'upload_studio'
            }

            # Only add target_keyword if provided
            if target_keyword:
                video_metadata['target_keyword'] = target_keyword

            db.collection('users').document(user_id).collection('uploaded_videos').document(video_id).set(video_metadata)
            logger.info(f"Stored video metadata in Firestore for video {video_id}")

        except Exception as e:
            logger.error(f"Error storing video metadata in Firestore: {e}")
            # Don't fail the upload if Firestore storage fails

        return jsonify({
            'success': True,
            'video_id': video_id,
            'message': 'Video uploaded successfully to YouTube'
        })

    except Exception as e:
        logger.error(f"Error uploading video to YouTube: {e}")

        # Clean up files on error
        try:
            # Clean up temp video file if it exists
            if 'video_path' in locals() and os.path.exists(video_path):
                os.unlink(video_path)
                logger.info(f"Cleaned up temporary video file after error: {video_path}")

            # Clean up Firebase Storage if it was uploaded there
            if 'data' in locals() and data.get('video_path', '').startswith('temp_videos/'):
                try:
                    firebase_path = data.get('video_path', '')
                    blob = storage_bucket.blob(firebase_path)
                    blob.delete()
                    logger.info(f"Deleted video from Firebase Storage after error: {firebase_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Error deleting video from Firebase Storage: {cleanup_error}")

            # Clean up temp directory if it exists
            if 'temp_dir' in locals():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")

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
            'error': f'Failed to upload video: {str(e)}'
        }), 500
