"""
TikTok Upload Studio Routes
OAuth connection via Late.dev, title generation, and scheduled video posting
"""

import os
import logging
from flask import render_template, redirect, url_for, request, jsonify, g
from app.routes.tiktok_upload_studio import bp
from app.system.auth.middleware import auth_required
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService
from app.scripts.tiktok_upload_studio.latedev_tiktok_service import TikTokLateDevService
from app.scripts.tiktok_upload_studio.tiktok_title_generator import TikTokTitleGenerator
from app.system.services.firebase_service import StorageService
from app.system.services.content_library_service import ContentLibraryManager
from app.system.auth.permissions import get_workspace_user_id, has_premium_subscription
from app.system.credits.credits_manager import CreditsManager
from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
import uuid

logger = logging.getLogger('tiktok_upload_studio')


@bp.route('/')
@auth_required
def index():
    """Render TikTok Upload Studio page"""
    try:
        user_id = g.user.get('id')

        # Check if user has TikTok connected via Late.dev
        is_connected = LateDevOAuthService.is_connected(user_id, 'tiktok')

        # Check subscription status (Premium Creator or admin allowed)
        has_premium = has_premium_subscription()

        return render_template(
            'tiktok_upload_studio/index.html',
            is_connected=is_connected,
            has_premium=has_premium
        )
    except Exception as e:
        logger.error(f"Error loading TikTok Upload Studio: {str(e)}")
        return render_template('tiktok_upload_studio/index.html', error=str(e))


@bp.route('/connect')
@auth_required
def connect():
    """Initiate TikTok OAuth flow via Late.dev (Premium only)"""
    try:
        # Check if user has premium subscription
        if not has_premium_subscription():
            logger.warning(f"Non-premium user attempted to connect TikTok")
            return redirect(url_for('tiktok_upload_studio.index', error='premium_required'))

        user_id = g.user.get('id')
        logger.info(f"TikTok connect route called for user {user_id}")

        # Generate Late.dev authorization URL for TikTok
        auth_url = LateDevOAuthService.get_authorization_url(user_id, 'tiktok')
        logger.info(f"Generated auth URL: {auth_url}")

        logger.info(f"Redirecting user {user_id} to Late.dev TikTok OAuth")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating TikTok OAuth: {str(e)}", exc_info=True)
        error_msg = str(e)
        return redirect(url_for('tiktok_upload_studio.index', error=error_msg))


@bp.route('/callback')
@auth_required
def callback():
    """Handle Late.dev OAuth callback for TikTok"""
    try:
        user_id = g.user.get('id')

        # Log all query params for debugging
        logger.info(f"TikTok callback received for user {user_id}")
        logger.info(f"Query params: {dict(request.args)}")

        # Get success/error from query params
        success = request.args.get('success')
        error = request.args.get('error')
        connected = request.args.get('connected')

        logger.info(f"success={success}, error={error}, connected={connected}")

        if error:
            logger.error(f"TikTok OAuth error: {error}")
            return redirect(url_for('tiktok_upload_studio.index', error=f'oauth_error_{error}'))

        # Late.dev uses 'connected' parameter to indicate success
        if success == 'true' or connected:
            logger.info(f"TikTok connected successfully for user {user_id}")
            return redirect(url_for('tiktok_upload_studio.index', success='connected'))
        else:
            logger.error(f"TikTok OAuth failed - no success indicator")
            return redirect(url_for('tiktok_upload_studio.index', error='connection_failed'))

    except Exception as e:
        logger.error(f"Error in TikTok callback: {str(e)}")
        return redirect(url_for('tiktok_upload_studio.index', error='callback_failed'))


@bp.route('/disconnect', methods=['POST'])
@auth_required
def disconnect():
    """Disconnect TikTok account from Late.dev"""
    try:
        user_id = g.user.get('id')

        result = LateDevOAuthService.disconnect(user_id, 'tiktok')

        if result['success']:
            return jsonify({'success': True, 'message': 'TikTok account disconnected'})
        else:
            return jsonify({'success': False, 'error': result.get('error')}), 500

    except Exception as e:
        logger.error(f"Error disconnecting TikTok: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/status')
@auth_required
def api_status():
    """Check TikTok connection status via Late.dev"""
    try:
        user_id = g.user.get('id')

        account_info = LateDevOAuthService.get_account_info(user_id, 'tiktok')

        logger.info(f"TikTok account info from Late.dev: {account_info}")

        # Format user info for frontend
        user_info = None
        if account_info:
            user_info = {
                'display_name': account_info.get('name') or account_info.get('username') or 'TikTok User',
                'avatar_url': account_info.get('profile_picture') or account_info.get('profilePicture') or account_info.get('profilePictureUrl'),
                'username': account_info.get('username')
            }
            logger.info(f"Formatted user info: {user_info}")

        return jsonify({
            'success': True,
            'connected': account_info is not None,
            'user_info': user_info
        })

    except Exception as e:
        logger.error(f"Error checking TikTok status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/upload-media', methods=['POST'])
@auth_required
def api_upload_media():
    """Upload media file to Firebase Storage with long-lived URL for scheduled posts"""
    try:
        user_id = g.user.get('id')

        # Get file from request
        if 'media' not in request.files:
            return jsonify({'success': False, 'error': 'No media file provided'}), 400

        media_file = request.files['media']
        if not media_file or media_file.filename == '':
            return jsonify({'success': False, 'error': 'No media file selected'}), 400

        # Get keywords and description from form data
        keywords = request.form.get('keywords', '').strip()
        content_description = request.form.get('content_description', '').strip()

        # Generate unique filename
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = os.path.splitext(media_file.filename)[1]
        unique_filename = f"tiktok_{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"

        # Upload to Firebase Storage with public URL (no expiration for scheduled posts)
        directory = 'tiktok_uploads'
        logger.info(f"Uploading media to Firebase: {directory}/{unique_filename}")

        # Reset file pointer to beginning
        media_file.seek(0)

        # Upload as public URL for TikTok scheduled posts (never expires)
        result = StorageService.upload_file(
            user_id,
            directory,
            unique_filename,
            media_file,
            make_public=True  # Public URL for scheduled posts
        )

        if result:
            # Extract URL from result (can be dict or string)
            if isinstance(result, dict):
                public_url = result.get('url')
            else:
                public_url = result

            logger.info(f"Media uploaded successfully: {public_url}")

            # Don't save to content library yet - will be saved when actually scheduling/posting
            # This prevents showing "Posted" status for content that hasn't been scheduled yet

            return jsonify({
                'success': True,
                'media_url': public_url,
                'content_id': None  # Will be created when scheduling/posting
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to upload to storage'}), 500

    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/upload', methods=['POST'])
@auth_required
def api_upload():
    """Post to TikTok via Late.dev using Firebase Storage URL (Premium only)"""
    try:
        # Check if user has premium subscription
        if not has_premium_subscription():
            return jsonify({'success': False, 'error': 'Premium subscription required', 'premium_required': True}), 403

        user_id = g.user.get('id')

        # Check if user is connected
        if not LateDevOAuthService.is_connected(user_id, 'tiktok'):
            return jsonify({'success': False, 'error': 'TikTok not connected'}), 403

        # Get JSON data
        data = request.json
        title = data.get('title', '').strip()
        media_url = data.get('media_url', '').strip()  # Firebase Storage URL
        content_id = data.get('content_id')  # Content library ID (optional)
        mode = data.get('mode', 'direct')  # 'direct', 'inbox', or 'scheduled'
        privacy_level = data.get('privacy_level', 'PUBLIC_TO_EVERYONE')
        schedule_time = data.get('schedule_time')  # ISO 8601 format or null for immediate
        timezone = data.get('timezone', 'UTC')

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        if not media_url:
            return jsonify({'success': False, 'error': 'Media URL is required'}), 400

        logger.info(f"Starting TikTok post for user {user_id}: {title[:50]}... (mode: {mode})")

        # Post to TikTok via Late.dev using the Firebase URL
        result = TikTokLateDevService.upload_video(
            user_id=user_id,
            media_url=media_url,
            title=title,
            mode=mode,
            privacy_level=privacy_level,
            schedule_time=schedule_time,
            timezone=timezone
        )

        if result['success']:
            logger.info(f"TikTok post successful: {result.get('post_id')}")

            # Save/update content library
            post_id = result.get('post_id')
            if content_id:
                # Update existing content library entry
                try:
                    ContentLibraryManager.update_platform_status(
                        user_id=user_id,
                        content_id=content_id,
                        platform='tiktok',
                        platform_data={
                            'post_id': post_id,
                            'scheduled_for': schedule_time,
                            'title': title,
                            'status': 'scheduled' if mode == 'scheduled' else 'posted'
                        }
                    )
                    logger.info(f"Updated content library {content_id} with TikTok post {post_id}")
                except Exception as e:
                    logger.error(f"Error updating content library: {e}")
            else:
                # Create new content library entry
                try:
                    content_id = ContentLibraryManager.save_content(
                        user_id=user_id,
                        media_url=media_url,
                        media_type='video',
                        keywords=data.get('keywords', ''),
                        content_description=data.get('content_description', ''),
                        platform='tiktok',
                        platform_data={
                            'post_id': post_id,
                            'scheduled_for': schedule_time,
                            'title': title,
                            'status': 'scheduled' if mode == 'scheduled' else 'posted'
                        }
                    )
                    logger.info(f"Created content library {content_id} for TikTok post {post_id}")
                    result['content_id'] = content_id
                except Exception as e:
                    logger.error(f"Error creating content library: {e}")

            # If scheduled, create calendar event
            if mode == 'scheduled' and schedule_time and post_id:
                try:
                    calendar_manager = ContentCalendarManager(user_id)
                    event_title = title.split('\n')[0][:100] if title else 'TikTok Video'

                    event_id = calendar_manager.create_event(
                        title=event_title,
                        publish_date=schedule_time,
                        platform='TikTok',
                        status='ready',
                        content_type='organic',
                        tiktok_post_id=post_id,
                        content_id=content_id if content_id else '',
                        notes=f'TikTok Post ID: {post_id}'
                    )

                    logger.info(f"Created calendar event {event_id} for scheduled TikTok post {post_id}")
                except Exception as e:
                    logger.error(f"Failed to create calendar event: {e}")
                    # Continue even if calendar creation fails

            return jsonify(result), 200
        else:
            logger.error(f"TikTok post failed: {result.get('error')}")
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error in TikTok upload: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/generate-titles', methods=['POST'])
@auth_required
def api_generate_titles():
    """Generate TikTok titles with hooks and hashtags using AI"""
    try:
        data = request.json
        keywords = data.get('keywords', '').strip()
        video_input = data.get('video_input', '').strip()

        if not keywords:
            return jsonify({'success': False, 'error': 'Please provide target keywords'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        title_generator = TikTokTitleGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        input_text = f"{keywords}\n{video_input}" if video_input else keywords
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=input_text,
            model_name=None  # Uses current AI provider model
        )

        required_credits = cost_estimate['final_cost']
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        # Check for sufficient credits
        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }), 402

        # Step 2: Generate titles
        generation_result = title_generator.generate_titles(
            keywords=keywords,
            video_input=video_input,
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

            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="TikTok Title & Hashtags Generation",
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
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating TikTok titles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
