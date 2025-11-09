from flask import render_template, request, jsonify, g, redirect, url_for
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission, has_premium_subscription
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
from app.scripts.video_title.video_tags import VideoTagsGenerator
from app.scripts.video_title.video_description import VideoDescriptionGenerator
from app.system.services.firebase_service import db
from app.system.services.content_library_service import ContentLibraryManager
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-title-tags')
@auth_required
@require_permission('video_title')
def video_title_tags():
    """Video title and tags generator page"""
    user_id = get_workspace_user_id()
    has_premium = has_premium_subscription()

    # Check if user has YouTube connected via Late.dev
    is_connected = LateDevOAuthService.is_connected(user_id, 'youtube')

    return render_template('video_title_tags/index.html',
                         has_premium=has_premium,
                         is_connected=is_connected)

@bp.route('/video-title-tags/connect')
@auth_required
@require_permission('video_title')
def connect():
    """Initiate YouTube OAuth flow via Late.dev"""
    try:
        user_id = get_workspace_user_id()
        logger.info(f"YouTube connect route called for user {user_id}")

        # Generate Late.dev authorization URL for YouTube
        auth_url = LateDevOAuthService.get_authorization_url(user_id, 'youtube')
        logger.info(f"Generated auth URL: {auth_url}")

        logger.info(f"Redirecting user {user_id} to Late.dev YouTube OAuth")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating YouTube OAuth: {str(e)}", exc_info=True)
        error_msg = str(e)
        return redirect(url_for('video_title_tags.video_title_tags', error=error_msg))

@bp.route('/video-title-tags/callback')
@auth_required
@require_permission('video_title')
def callback():
    """Handle Late.dev OAuth callback for YouTube"""
    try:
        user_id = get_workspace_user_id()

        # Log all query params for debugging
        logger.info(f"YouTube callback received for user {user_id}")
        logger.info(f"Query params: {dict(request.args)}")

        # Get success/error from query params
        success = request.args.get('success')
        error = request.args.get('error')
        connected = request.args.get('connected')

        logger.info(f"success={success}, error={error}, connected={connected}")

        if error:
            logger.error(f"YouTube OAuth error: {error}")
            return redirect(url_for('video_title_tags.video_title_tags', error=f'oauth_error_{error}'))

        # Late.dev uses 'connected' parameter to indicate success
        if success == 'true' or connected:
            logger.info(f"YouTube connected successfully for user {user_id}")
            return redirect(url_for('video_title_tags.video_title_tags', success='connected'))
        else:
            logger.error(f"YouTube OAuth failed - no success indicator")
            return redirect(url_for('video_title_tags.video_title_tags', error='oauth_failed'))

    except Exception as e:
        logger.error(f"Error in YouTube callback: {str(e)}", exc_info=True)
        return redirect(url_for('video_title_tags.video_title_tags', error='callback_error'))

@bp.route('/video-title-tags/disconnect', methods=['POST'])
@auth_required
@require_permission('video_title')
def disconnect():
    """Disconnect YouTube account from Late.dev"""
    try:
        user_id = get_workspace_user_id()
        logger.info(f"Disconnect YouTube called for user {user_id}")

        result = LateDevOAuthService.disconnect(user_id, 'youtube')
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error disconnecting YouTube: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/video-title-tags/api/youtube-latedev-status', methods=['GET'])
@auth_required
@require_permission('video_title')
def youtube_latedev_status():
    """Check if user has YouTube connected via Late.dev"""
    try:
        user_id = get_workspace_user_id()
        account_info = LateDevOAuthService.get_account_info(user_id, 'youtube')

        # Format user info for frontend (same format as TikTok/Instagram)
        user_info = None
        if account_info:
            user_info = {
                'display_name': account_info.get('username') or 'YouTube User',
                'avatar_url': account_info.get('profile_picture'),
                'username': account_info.get('username')
            }

        return jsonify({
            'connected': account_info is not None,
            'user_info': user_info
        })

    except Exception as e:
        logger.error(f"Error checking YouTube Late.dev status: {str(e)}")
        return jsonify({'connected': False, 'error': str(e)}), 500

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

@bp.route('/api/upload-to-youtube', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_to_youtube():
    """Upload video to YouTube via Late.dev"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Get required fields
        firebase_url = (data.get('firebase_url') or '').strip()
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        tags = data.get('tags', [])
        visibility = data.get('visibility', 'private')
        scheduled_time = data.get('scheduled_time')
        thumbnail_url = (data.get('thumbnail_url') or '').strip()
        keywords = (data.get('keywords') or '').strip()
        content_description = (data.get('content_description') or '').strip()
        content_id = data.get('content_id')  # Content library ID (optional)
        calendar_event_id = data.get('calendar_event_id')  # Linked calendar event ID (optional)

        if not firebase_url:
            return jsonify({
                'success': False,
                'error': 'Video URL is required'
            }), 400

        if not title:
            return jsonify({
                'success': False,
                'error': 'Title is required'
            }), 400

        # Upload video via Late.dev
        from app.scripts.video_title.latedev_youtube_service import YouTubeLateDevService

        result = YouTubeLateDevService.upload_video(
            user_id=user_id,
            media_url=firebase_url,
            title=title,
            description=description,
            tags=tags,
            visibility=visibility,
            thumbnail_url=thumbnail_url,
            schedule_time=scheduled_time,
            timezone='UTC'
        )

        if not result.get('success'):
            return jsonify(result), 400

        post_id = result.get('post_id')

        # Save/update content library
        if content_id:
            # Update existing content library entry
            try:
                ContentLibraryManager.update_platform_status(
                    user_id=user_id,
                    content_id=content_id,
                    platform='youtube',
                    platform_data={
                        'post_id': post_id,
                        'scheduled_for': scheduled_time,
                        'title': title,
                        'status': 'scheduled' if scheduled_time else 'posted'
                    }
                )
                logger.info(f"Updated content library {content_id} with YouTube video {post_id}")
            except Exception as e:
                logger.error(f"Error updating content library: {e}")
        else:
            # Create new content library entry
            try:
                content_id = ContentLibraryManager.save_content(
                    user_id=user_id,
                    media_url=firebase_url,
                    media_type='video',
                    keywords=keywords,
                    content_description=content_description,
                    platform='youtube',
                    platform_data={
                        'post_id': post_id,
                        'scheduled_for': scheduled_time,
                        'title': title,
                        'status': 'scheduled' if scheduled_time else 'posted'
                    }
                )
                logger.info(f"Created content library {content_id} for YouTube video {post_id}")
            except Exception as e:
                logger.error(f"Error creating content library: {e}")

        # Update linked calendar event OR create a new one
        if title and post_id:
            try:
                from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                calendar_manager = ContentCalendarManager(user_id)

                # Determine status and publish_date based on whether it's scheduled
                if scheduled_time:
                    status = 'ready'
                    publish_date = scheduled_time
                else:
                    status = 'posted'
                    publish_date = datetime.now(timezone.utc).isoformat()

                # Convert tags array to comma-separated string for storage
                tags_string = ', '.join(tags) if isinstance(tags, list) else str(tags)

                if calendar_event_id:
                    # Update the linked calendar event
                    # Don't update title - keep the original requirements/title from the calendar item
                    # The YouTube video title will be stored in description/tags and shown separately
                    success = calendar_manager.update_event(
                        event_id=calendar_event_id,
                        description=f"Video Title: {title}\n\n{description}",  # Prepend video title to description
                        tags=tags_string,
                        publish_date=publish_date,
                        platform='YouTube',
                        status=status,
                        youtube_video_id=post_id,
                        content_id=content_id if content_id else '',
                        media_url=firebase_url  # Store video URL for thumbnail display
                    )
                    if success:
                        logger.info(f"Updated linked calendar event {calendar_event_id} for YouTube video {post_id}")
                    else:
                        logger.warning(f"Failed to update linked calendar event {calendar_event_id}, creating new one")
                        calendar_event_id = None  # Fall through to create new event

                if not calendar_event_id:
                    # Create new calendar event
                    event_id = calendar_manager.create_event(
                        title=title,
                        description=description,
                        tags=tags_string,
                        publish_date=publish_date,
                        platform='YouTube',
                        status=status,
                        content_type='organic',
                        youtube_video_id=post_id,
                        content_id=content_id if content_id else '',
                        notes=f'YouTube Post ID: {post_id}',
                        media_url=firebase_url  # Store video URL for thumbnail display
                    )
                    logger.info(f"Created calendar event {event_id} for YouTube video {post_id} (scheduled={bool(scheduled_time)})")

            except Exception as e:
                logger.error(f"Error managing calendar event: {e}")
                # Don't fail the whole request if calendar creation fails

        return jsonify({
            'success': True,
            'post_id': post_id,
            'message': result.get('message', 'Video uploaded successfully'),
            'content_id': content_id
        })

    except Exception as e:
        logger.error(f"Error uploading to YouTube: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/finalize-youtube-upload', methods=['POST'])
@auth_required
@require_permission('video_title')
def finalize_youtube_upload():
    """Finalize YouTube upload (handle thumbnail, store metadata, create calendar event)"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        video_id = (data.get('video_id') or '').strip()
        thumbnail_path = data.get('thumbnail_path')
        target_keyword = (data.get('target_keyword') or '').strip()
        title = (data.get('title') or '').strip()
        scheduled_time = data.get('scheduled_time')
        firebase_url = (data.get('firebase_url') or '').strip()
        keywords = (data.get('keywords') or '').strip()
        content_description = (data.get('content_description') or '').strip()

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
                    error_str = str(e).lower()
                    logger.error(f"Error uploading thumbnail: {e}")

                    # Check for quota exceeded error
                    if 'quota' in error_str or 'quotaexceeded' in error_str:
                        return jsonify({
                            'success': False,
                            'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                            'error_type': 'quota_exceeded'
                        }), 403
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

        # Save to content library
        content_id = None
        if firebase_url:
            try:
                from app.system.services.content_library_service import ContentLibraryManager

                content_id = ContentLibraryManager.save_content(
                    user_id=user_id,
                    media_url=firebase_url,
                    media_type='video',
                    keywords=keywords,
                    content_description=content_description,
                    platform='youtube',
                    platform_data={
                        'post_id': video_id,
                        'scheduled_for': scheduled_time,
                        'title': title,
                        'status': 'scheduled' if scheduled_time else 'posted'
                    }
                )
                logger.info(f"Created content library {content_id} for YouTube video {video_id}")
            except Exception as e:
                logger.error(f"Error creating content library: {e}")

        # Create calendar event for all videos
        if title and video_id:
            try:
                from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                calendar_manager = ContentCalendarManager(user_id)

                # Determine status and publish_date based on whether it's scheduled
                if scheduled_time:
                    status = 'ready'
                    publish_date = scheduled_time
                else:
                    status = 'posted'
                    publish_date = datetime.now(timezone.utc).isoformat()

                event_id = calendar_manager.create_event(
                    title=title,
                    publish_date=publish_date,
                    platform='YouTube',
                    status=status,
                    content_type='organic',
                    youtube_video_id=video_id,
                    content_id=content_id if content_id else '',
                    notes=f'YouTube Video ID: {video_id}'
                )

                logger.info(f"Created calendar event {event_id} for YouTube video {video_id} (scheduled={bool(scheduled_time)})")
            except Exception as e:
                logger.error(f"Error creating calendar event: {e}")
                # Don't fail the whole request if calendar creation fails

        return jsonify({
            'success': True,
            'message': 'Upload finalized successfully'
        })

    except Exception as e:
        import traceback
        logger.error(f"Error finalizing YouTube upload: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Failed to finalize upload: {str(e)}'
        }), 500

@bp.route('/api/init-youtube-upload', methods=['POST'])
@auth_required
@require_permission('video_title')
def init_youtube_upload():
    """Initialize YouTube upload - creates calendar item and prepares for upload"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Get metadata
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        tags = data.get('tags', [])
        visibility = data.get('visibility', 'private')
        scheduled_time = data.get('scheduled_time')
        keywords = (data.get('keywords') or '').strip()
        content_description = (data.get('content_description') or '').strip()
        calendar_event_id = data.get('calendar_event_id')
        filename = data.get('filename', 'video.mp4')
        content_type = data.get('content_type', 'video/mp4')

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        # Generate unique filename
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'mp4'
        unique_filename = f"video_{timestamp}_{uuid.uuid4().hex[:8]}.{file_ext}"

        # Generate upload metadata
        from app.system.services.firebase_service import StorageService
        upload_info = StorageService.generate_upload_signed_url(
            user_id=user_id,
            directory='youtube_videos',
            filename=unique_filename,
            content_type='video/mp4',
            expiration_seconds=3600  # 1 hour to complete upload
        )

        if not upload_info:
            return jsonify({'success': False, 'error': 'Failed to generate upload info'}), 500

        # Generate public URL for future reference
        public_url = f"https://storage.googleapis.com/{upload_info['bucket_name']}/{upload_info['file_path']}"

        # Store upload metadata in session or return to frontend
        # DO NOT create calendar item yet - wait until Late.dev confirms success
        upload_metadata = {
            'title': title,
            'description': description,
            'tags': tags,
            'visibility': visibility,
            'scheduled_time': scheduled_time,
            'keywords': keywords,
            'content_description': content_description,
            'calendar_event_id': calendar_event_id,  # User-linked calendar item (if any)
            'file_path': upload_info['file_path']
        }

        logger.info(f"Upload initialized. Calendar item will be created after Late.dev success.")

        # Generate a signed URL for direct browser-to-Firebase upload (bypasses Cloud Run 32MB limit)
        resumable_url = None
        try:
            from google.cloud import storage as gcs_storage

            # Get bucket name
            bucket_name = upload_info['bucket_name']

            # Initialize GCS client
            gcs_client = gcs_storage.Client()
            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(upload_info['file_path'])

            # Generate resumable upload session URL (valid for 1 hour)
            resumable_url = blob.create_resumable_upload_session(
                content_type=content_type,
                timeout=3600
            )

            logger.info(f"Generated resumable upload URL for direct browser upload: {upload_info['file_path']}")
        except Exception as e:
            logger.error(f"Error generating resumable upload URL: {e}")
            # Continue without resumable URL - will fall back to old method

        return jsonify({
            'success': True,
            'file_path': upload_info['file_path'],
            'bucket_name': upload_info['bucket_name'],
            'public_url': public_url,
            'upload_metadata': upload_metadata,  # Metadata to pass to complete endpoint
            'resumable_url': resumable_url,  # Browser will upload directly to Firebase using this URL
            'message': 'Ready for upload. Calendar item will be created after Late.dev success.'
        })

    except Exception as e:
        logger.error(f"Error initializing YouTube upload: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/upload-video-to-firebase', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_video_to_firebase():
    """DEPRECATED: Upload video to Firebase Storage for Late.dev posting

    This endpoint is kept for backward compatibility but should not be used for large files.
    Use /api/init-youtube-upload instead for direct client-side uploads.
    """
    try:
        user_id = get_workspace_user_id()

        # Get video file from request
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'}), 400

        video_file = request.files['video']
        if not video_file or video_file.filename == '':
            return jsonify({'success': False, 'error': 'No video file selected'}), 400

        # Get keywords and description from form data
        keywords = request.form.get('keywords', '').strip()
        content_description = request.form.get('content_description', '').strip()

        # Generate unique filename
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = video_file.filename.rsplit('.', 1)[1].lower() if '.' in video_file.filename else 'mp4'
        unique_filename = f"video_{timestamp}_{uuid.uuid4().hex[:8]}.{file_ext}"

        # Upload to Firebase Storage (public URL)
        from app.system.services.firebase_service import StorageService
        result = StorageService.upload_file(
            user_id,
            'youtube_videos',  # Directory for all YouTube videos
            unique_filename,
            video_file,
            make_public=True  # Public URL for Late.dev posting
        )

        if result:
            # Extract URL from result (can be dict or string)
            if isinstance(result, dict):
                firebase_url = result.get('url')
            else:
                firebase_url = result

            logger.info(f"Video uploaded to Firebase: {firebase_url}")

            # Don't save to content library yet - will be saved when actually posting via Late.dev
            # This prevents showing "Posted" status for content that hasn't been scheduled yet

            return jsonify({
                'success': True,
                'firebase_url': firebase_url,
                'filename': unique_filename,
                'content_id': None  # Will be created when posting to YouTube
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to upload to Firebase'}), 500

    except Exception as e:
        logger.error(f"Error uploading video to Firebase: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/confirm-firebase-upload', methods=['POST'])
@auth_required
@require_permission('video_title')
def confirm_firebase_upload():
    """Called by browser after direct Firebase upload completes - generates thumbnail and returns URLs"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        content_id = data.get('content_id')
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({'success': False, 'error': 'File path is required'}), 400

        logger.info(f"Confirming Firebase upload for: {file_path}")

        # Generate thumbnail from uploaded video
        from app.system.services.firebase_service import StorageService

        # Extract filename from path
        filename = file_path.split('/')[-1]
        directory = '/'.join(file_path.split('/')[2:-1])

        # Generate thumbnail and get URLs
        result = StorageService.generate_thumbnail_from_firebase(user_id, directory, filename)

        if not result:
            # If thumbnail generation fails, still return the video URL
            import os
            bucket_name = os.environ.get('FIREBASE_STORAGE_BUCKET', '').replace('gs://', '')
            firebase_url = f"https://storage.googleapis.com/{bucket_name}/{file_path}"

            return jsonify({
                'success': True,
                'firebase_url': firebase_url,
                'thumbnail_url': None,
                'message': 'Upload confirmed (thumbnail generation failed)'
            })

        firebase_url = result.get('url')
        thumbnail_url = result.get('thumbnail_url')

        logger.info(f"Firebase upload confirmed: {firebase_url}")
        if thumbnail_url:
            logger.info(f"Thumbnail generated: {thumbnail_url}")

        return jsonify({
            'success': True,
            'firebase_url': firebase_url,
            'thumbnail_url': thumbnail_url,
            'message': 'Upload confirmed and thumbnail generated'
        })

    except Exception as e:
        logger.error(f"Error confirming Firebase upload: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/upload-video-chunk', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_video_chunk():
    """Upload video file to Firebase in streaming fashion (no size limit)"""
    try:
        user_id = get_workspace_user_id()

        # Get video file from request
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'}), 400

        video_file = request.files['video']
        if not video_file or video_file.filename == '':
            return jsonify({'success': False, 'error': 'No video file selected'}), 400

        # Get metadata from form data
        content_id = request.form.get('content_id')
        file_path = request.form.get('file_path')

        if not file_path:
            return jsonify({'success': False, 'error': 'File path is required'}), 400

        # Upload directly to Firebase using chunked upload
        from app.system.services.firebase_service import StorageService

        # Extract filename from path
        filename = file_path.split('/')[-1]
        directory = '/'.join(file_path.split('/')[2:-1])  # Extract directory from path

        result = StorageService.upload_large_file_chunked(
            user_id=user_id,
            directory=directory,
            filename=filename,
            file_stream=video_file.stream,
            content_type=video_file.content_type or 'video/mp4'
        )

        if not result:
            return jsonify({'success': False, 'error': 'Failed to upload to Firebase'}), 500

        firebase_url = result['url']
        thumbnail_url = result.get('thumbnail_url')
        logger.info(f"Large video uploaded to Firebase: {firebase_url}")
        if thumbnail_url:
            logger.info(f"Thumbnail generated: {thumbnail_url}")

        # Get the content library entry to retrieve scheduling metadata
        content = None
        if content_id:
            try:
                content = ContentLibraryManager.get_content_by_id(user_id, content_id)
            except Exception as e:
                logger.error(f"Error getting content library: {e}")

        # Automatically schedule to Late.dev after upload completes
        if content:
            try:
                platforms_posted = content.get('platforms_posted', {})
                youtube_data = platforms_posted.get('youtube', {})

                title = youtube_data.get('title')
                description = youtube_data.get('description', '')
                tags = youtube_data.get('tags', [])
                visibility = youtube_data.get('visibility', 'private')
                scheduled_time = youtube_data.get('scheduled_for')
                calendar_event_id = youtube_data.get('calendar_event_id')

                if title:
                    logger.info(f"Auto-scheduling video to YouTube via Late.dev: {title}")

                    # Upload to YouTube via Late.dev
                    from app.scripts.video_title.latedev_youtube_service import YouTubeLateDevService

                    result = YouTubeLateDevService.upload_video(
                        user_id=user_id,
                        media_url=firebase_url,
                        title=title,
                        description=description,
                        tags=tags,
                        visibility=visibility,
                        thumbnail_url=thumbnail_url,
                        schedule_time=scheduled_time,
                        timezone='UTC'
                    )

                    if result.get('success'):
                        post_id = result.get('post_id')
                        logger.info(f"Video scheduled to YouTube successfully: {post_id}")

                        # Update content library to 'scheduled' or 'posted'
                        new_status = 'scheduled' if scheduled_time else 'posted'
                        ContentLibraryManager.update_platform_status(
                            user_id=user_id,
                            content_id=content_id,
                            platform='youtube',
                            platform_data={
                                'status': new_status,
                                'post_id': post_id,
                                'media_url': firebase_url,
                                'thumbnail_url': thumbnail_url
                            }
                        )

                        # Update calendar event status
                        if calendar_event_id:
                            try:
                                from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                                calendar_manager = ContentCalendarManager(user_id)
                                calendar_manager.update_event(
                                    event_id=calendar_event_id,
                                    status=new_status,
                                    media_url=firebase_url
                                )
                            except Exception as e:
                                logger.error(f"Error updating calendar event: {e}")
                    else:
                        # Schedule failed - update status to 'failed'
                        logger.error(f"Failed to schedule video: {result.get('error')}")
                        ContentLibraryManager.update_platform_status(
                            user_id=user_id,
                            content_id=content_id,
                            platform='youtube',
                            platform_data={
                                'status': 'failed',
                                'error': result.get('error'),
                                'media_url': firebase_url,
                                'thumbnail_url': thumbnail_url
                            }
                        )

                        if calendar_event_id:
                            try:
                                from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                                calendar_manager = ContentCalendarManager(user_id)
                                calendar_manager.update_event(event_id=calendar_event_id, status='failed')
                            except Exception as e:
                                logger.error(f"Error updating calendar event to failed: {e}")
            except Exception as e:
                logger.error(f"Error auto-scheduling to YouTube: {e}", exc_info=True)
                # Update to failed status
                if content_id:
                    try:
                        ContentLibraryManager.update_platform_status(
                            user_id=user_id,
                            content_id=content_id,
                            platform='youtube',
                            platform_data={
                                'status': 'failed',
                                'error': str(e),
                                'media_url': firebase_url,
                                'thumbnail_url': thumbnail_url
                            }
                        )
                    except:
                        pass

        return jsonify({
            'success': True,
            'firebase_url': firebase_url,
            'thumbnail_url': thumbnail_url,
            'message': 'Video uploaded and scheduled successfully'
        })

    except Exception as e:
        logger.error(f"Error uploading video chunk: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/complete-youtube-upload', methods=['POST'])
@auth_required
@require_permission('video_title')
def complete_youtube_upload():
    """Called after video is uploaded to Firebase - posts to YouTube via Late.dev"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        firebase_url = (data.get('firebase_url') or '').strip()
        content_id = data.get('content_id')
        calendar_event_id = data.get('calendar_event_id')
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        tags = data.get('tags', [])
        visibility = data.get('visibility', 'private')
        scheduled_time = data.get('scheduled_time')
        thumbnail_url = (data.get('thumbnail_url') or '').strip()

        if not firebase_url or not title:
            return jsonify({'success': False, 'error': 'Firebase URL and title are required'}), 400

        # Upload to YouTube via Late.dev
        from app.scripts.video_title.latedev_youtube_service import YouTubeLateDevService

        result = YouTubeLateDevService.upload_video(
            user_id=user_id,
            media_url=firebase_url,
            title=title,
            description=description,
            tags=tags,
            visibility=visibility,
            thumbnail_url=thumbnail_url,
            schedule_time=scheduled_time,
            timezone='UTC'
        )

        if not result.get('success'):
            # Update status to 'failed' in content library and calendar
            if content_id:
                try:
                    ContentLibraryManager.update_platform_status(
                        user_id=user_id,
                        content_id=content_id,
                        platform='youtube',
                        platform_data={'status': 'failed', 'error': result.get('error')}
                    )
                except Exception as e:
                    logger.error(f"Error updating content library to failed: {e}")

            if calendar_event_id:
                try:
                    from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                    calendar_manager = ContentCalendarManager(user_id)
                    calendar_manager.update_event(event_id=calendar_event_id, status='failed')
                except Exception as e:
                    logger.error(f"Error updating calendar event to failed: {e}")

            return jsonify(result), 400

        post_id = result.get('post_id')
        new_status = 'scheduled' if scheduled_time else 'posted'

        # Get upload metadata (keywords, content_description, etc.)
        upload_metadata = data.get('upload_metadata', {})
        keywords = upload_metadata.get('keywords', '')
        content_description = upload_metadata.get('content_description', '')
        user_calendar_event_id = upload_metadata.get('calendar_event_id')  # User-linked existing calendar item

        # CREATE content library entry NOW (after Late.dev success)
        content_id = None
        try:
            content_id = ContentLibraryManager.save_content(
                user_id=user_id,
                media_url=firebase_url,
                media_type='video',
                keywords=keywords,
                content_description=content_description,
                platform='youtube',
                platform_data={
                    'post_id': post_id,
                    'scheduled_for': scheduled_time,
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'visibility': visibility,
                    'status': new_status,
                    'media_url': firebase_url,
                    'thumbnail_url': thumbnail_url
                }
            )
            logger.info(f"Created content library {content_id} with status '{new_status}' after Late.dev success")
        except Exception as e:
            logger.error(f"Error creating content library: {e}")

        # CREATE or UPDATE calendar event NOW (after Late.dev success)
        calendar_event_id = None
        try:
            from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
            calendar_manager = ContentCalendarManager(user_id)

            status = 'ready' if scheduled_time else 'posted'
            publish_date = scheduled_time if scheduled_time else datetime.now(timezone.utc).isoformat()
            tags_string = ', '.join(tags) if isinstance(tags, list) else str(tags)

            if user_calendar_event_id:
                # Update user-linked existing calendar item
                success = calendar_manager.update_event(
                    event_id=user_calendar_event_id,
                    description=f"Video Title: {title}\n\n{description}",
                    tags=tags_string,
                    publish_date=publish_date,
                    platform='YouTube',
                    status=status,
                    youtube_video_id=post_id,
                    media_url=firebase_url,
                    content_id=content_id if content_id else ''
                )
                if success:
                    calendar_event_id = user_calendar_event_id
                    logger.info(f"Updated user-linked calendar event {calendar_event_id} to {status}")
                else:
                    logger.warning(f"Failed to update user-linked calendar event {user_calendar_event_id}")

            if not calendar_event_id:
                # Create new calendar event
                calendar_event_id = calendar_manager.create_event(
                    title=title,
                    description=description,
                    tags=tags_string,
                    publish_date=publish_date,
                    platform='YouTube',
                    status=status,
                    content_type='organic',
                    youtube_video_id=post_id,
                    media_url=firebase_url,
                    content_id=content_id if content_id else ''
                )
                logger.info(f"Created calendar event {calendar_event_id} with status '{status}' after Late.dev success")

            # Update content library with calendar_event_id
            if content_id and calendar_event_id:
                try:
                    ContentLibraryManager.update_platform_status(
                        user_id=user_id,
                        content_id=content_id,
                        platform='youtube',
                        platform_data={'calendar_event_id': calendar_event_id}
                    )
                except Exception as e:
                    logger.error(f"Error updating content library with calendar_event_id: {e}")

        except Exception as e:
            logger.error(f"Error creating/updating calendar event: {e}")

        return jsonify({
            'success': True,
            'post_id': post_id,
            'message': result.get('message', 'Video uploaded successfully'),
            'content_id': content_id
        })

    except Exception as e:
        logger.error(f"Error completing YouTube upload: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# Keep old endpoint for backwards compatibility
@bp.route('/api/upload-short-to-firebase', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_short_to_firebase():
    """Legacy endpoint - redirects to new upload_video_to_firebase"""
    return upload_video_to_firebase()

@bp.route('/api/check-ongoing-uploads', methods=['GET'])
@auth_required
def check_ongoing_uploads():
    """Check if user has any uploads in 'uploading' status"""
    try:
        user_id = get_workspace_user_id()

        # Check content library for uploads with status 'uploading'
        ongoing_uploads = []
        try:
            from app.system.services.content_library_service import ContentLibraryManager

            # Get recent content items (last 3 days)
            content_items = ContentLibraryManager.get_recent_content(user_id, hours=72)

            for item in content_items:
                platforms_posted = item.get('platforms_posted', {})
                youtube_data = platforms_posted.get('youtube', {})

                if youtube_data.get('status') == 'uploading':
                    ongoing_uploads.append({
                        'content_id': item.get('id'),
                        'title': youtube_data.get('title', 'Untitled'),
                        'created_at': item.get('created_at')
                    })
        except Exception as e:
            logger.error(f"Error checking ongoing uploads: {e}", exc_info=True)

        return jsonify({
            'success': True,
            'has_ongoing_uploads': len(ongoing_uploads) > 0,
            'uploads': ongoing_uploads
        })

    except Exception as e:
        logger.error(f"Error checking ongoing uploads: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cancel-upload', methods=['POST'])
@auth_required
def cancel_upload():
    """Cancel an ongoing upload by removing content library entry and calendar event"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()
        content_id = data.get('content_id')

        if not content_id:
            return jsonify({'success': False, 'error': 'Content ID required'}), 400

        from app.system.services.content_library_service import ContentLibraryManager
        from app.scripts.content_calendar.calendar_manager import ContentCalendarManager

        # Get content to find associated calendar event
        content = ContentLibraryManager.get_content_by_id(user_id, content_id)

        if content:
            # Check if upload is actually in progress or already completed
            platforms_posted = content.get('platforms_posted', {})
            youtube_data = platforms_posted.get('youtube', {})
            status = youtube_data.get('status')

            # Only allow cancellation if status is 'uploading'
            if status != 'uploading':
                return jsonify({
                    'success': False,
                    'error': f'Cannot cancel - upload has already completed with status: {status}'
                }), 400

            # Delete from content library
            ContentLibraryManager.delete_content(user_id, content_id)

            # Find and delete associated calendar event using stored calendar_event_id
            platforms_posted = content.get('platforms_posted', {})
            youtube_data = platforms_posted.get('youtube', {})
            calendar_event_id = youtube_data.get('calendar_event_id')

            if calendar_event_id:
                try:
                    calendar_manager = ContentCalendarManager(user_id)
                    calendar_manager.delete_event(calendar_event_id)
                    logger.info(f"Deleted calendar event {calendar_event_id} for cancelled upload")
                except Exception as e:
                    logger.error(f"Error deleting calendar event: {e}")

            logger.info(f"Cancelled upload {content_id} for user {user_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Content not found'}), 404

    except Exception as e:
        logger.error(f"Error cancelling upload: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/youtube-status', methods=['GET'])
@auth_required
@require_permission('video_title')
def youtube_status():
    """Get YouTube connection status and channel info"""
    try:
        user_id = get_workspace_user_id()

        # Get user data from Firestore
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({
                'success': True,
                'connected': False
            })

        user_data = user_doc.to_dict()

        # Check if YouTube credentials exist
        has_credentials = bool(user_data.get('youtube_credentials'))
        channel_name = user_data.get('youtube_account')
        channel_id = user_data.get('youtube_channel_id')

        # Try to get channel thumbnail from YouTube API if connected
        channel_thumbnail = None
        if has_credentials and channel_id:
            try:
                from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
                analytics = YouTubeAnalytics(user_id)

                if analytics.credentials:
                    from googleapiclient.discovery import build
                    youtube = build('youtube', 'v3', credentials=analytics.credentials)

                    # Get channel info including thumbnail
                    channel_response = youtube.channels().list(
                        part='snippet',
                        id=channel_id
                    ).execute()

                    if channel_response.get('items'):
                        thumbnails = channel_response['items'][0]['snippet'].get('thumbnails', {})
                        # Get highest quality thumbnail available
                        channel_thumbnail = (
                            thumbnails.get('high', {}).get('url') or
                            thumbnails.get('medium', {}).get('url') or
                            thumbnails.get('default', {}).get('url')
                        )
            except Exception as e:
                logger.warning(f"Could not fetch YouTube channel thumbnail: {e}")

        return jsonify({
            'success': True,
            'connected': has_credentials,
            'channel_info': {
                'name': channel_name,
                'id': channel_id,
                'thumbnail': channel_thumbnail
            } if has_credentials else None
        })

    except Exception as e:
        logger.error(f"Error checking YouTube status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/upload-youtube-video', methods=['POST'])
@auth_required
@require_permission('video_title')
def upload_youtube_video():
    """Legacy endpoint - kept for backward compatibility. Use init-youtube-upload + finalize-youtube-upload instead."""
    return jsonify({
        'success': False,
        'error': 'This endpoint is deprecated. Please use the new direct upload flow.'
    }), 410
