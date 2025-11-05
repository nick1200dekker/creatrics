"""
Instagram Upload Studio Routes
OAuth connection via Late.dev, title/hashtags generation, and scheduled video/image posting
"""

import os
import logging
from flask import render_template, redirect, url_for, request, jsonify, g
from app.routes.instagram_upload_studio import bp
from app.system.auth.middleware import auth_required
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService
from app.scripts.instagram_upload_studio.instagram_upload_service import InstagramUploadService
from app.scripts.instagram_upload_studio.instagram_title_generator import InstagramTitleGenerator
from app.system.services.firebase_service import StorageService
from app.system.auth.permissions import get_workspace_user_id, has_premium_subscription
from app.system.credits.credits_manager import CreditsManager
import uuid

logger = logging.getLogger('instagram_upload_studio')


@bp.route('/')
@auth_required
def index():
    """Render Instagram Upload Studio page"""
    try:
        user_id = g.user.get('id')

        # Check if user has Instagram connected via Late.dev
        is_connected = LateDevOAuthService.is_connected(user_id, 'instagram')

        # Check subscription status (Premium Creator or admin allowed)
        has_premium = has_premium_subscription()

        return render_template(
            'instagram_upload_studio/index.html',
            is_connected=is_connected,
            has_premium=has_premium
        )
    except Exception as e:
        logger.error(f"Error loading Instagram Upload Studio: {str(e)}")
        return render_template('instagram_upload_studio/index.html', error=str(e))


@bp.route('/connect')
@auth_required
def connect():
    """Initiate Instagram OAuth flow via Late.dev (Premium only)"""
    try:
        # Check if user has premium subscription
        if not has_premium_subscription():
            logger.warning(f"Non-premium user attempted to connect Instagram")
            return redirect(url_for('instagram_upload_studio.index', error='premium_required'))

        user_id = g.user.get('id')
        logger.info(f"Instagram connect route called for user {user_id}")

        # Generate Late.dev authorization URL for Instagram
        auth_url = LateDevOAuthService.get_authorization_url(user_id, 'instagram')
        logger.info(f"Generated auth URL: {auth_url}")

        logger.info(f"Redirecting user {user_id} to Late.dev Instagram OAuth")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating Instagram OAuth: {str(e)}", exc_info=True)
        error_msg = str(e)
        # Pass detailed error message to frontend
        return redirect(url_for('instagram_upload_studio.index', error=error_msg))


@bp.route('/callback')
@auth_required
def callback():
    """Handle Late.dev OAuth callback for Instagram"""
    try:
        user_id = g.user.get('id')

        # Log all query params for debugging
        logger.info(f"Instagram callback received for user {user_id}")
        logger.info(f"Query params: {dict(request.args)}")

        # Get success/error from query params
        success = request.args.get('success')
        error = request.args.get('error')
        connected = request.args.get('connected')

        logger.info(f"success={success}, error={error}, connected={connected}")

        if error:
            logger.error(f"Instagram OAuth error: {error}")
            return redirect(url_for('instagram_upload_studio.index', error=f'oauth_error_{error}'))

        # Late.dev uses 'connected' parameter to indicate success
        if success == 'true' or connected:
            logger.info(f"Instagram connected successfully for user {user_id}")
            return redirect(url_for('instagram_upload_studio.index', success='connected'))
        else:
            logger.error(f"Instagram OAuth failed - no success indicator")
            return redirect(url_for('instagram_upload_studio.index', error='connection_failed'))

    except Exception as e:
        logger.error(f"Error in Instagram callback: {str(e)}")
        return redirect(url_for('instagram_upload_studio.index', error='callback_failed'))


@bp.route('/disconnect', methods=['POST'])
@auth_required
def disconnect():
    """Disconnect Instagram account from Late.dev"""
    try:
        user_id = g.user.get('id')

        result = LateDevOAuthService.disconnect(user_id, 'instagram')

        if result['success']:
            return jsonify({'success': True, 'message': 'Instagram account disconnected'})
        else:
            return jsonify({'success': False, 'error': result.get('error')}), 500

    except Exception as e:
        logger.error(f"Error disconnecting Instagram: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/status')
@auth_required
def api_status():
    """Check Instagram connection status via Late.dev"""
    try:
        user_id = g.user.get('id')

        is_connected = LateDevOAuthService.is_connected(user_id, 'instagram')
        account_info = None

        if is_connected:
            account_info = LateDevOAuthService.get_account_info(user_id, 'instagram')

        return jsonify({
            'success': True,
            'connected': is_connected,
            'account_info': account_info
        })

    except Exception as e:
        logger.error(f"Error checking Instagram status: {str(e)}")
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

        # Generate unique filename
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = os.path.splitext(media_file.filename)[1]
        unique_filename = f"instagram_{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"

        # Upload to Firebase Storage with long-lived URL (7 days)
        directory = 'instagram_uploads'
        logger.info(f"Uploading media to Firebase: {directory}/{unique_filename}")

        # Reset file pointer to beginning
        media_file.seek(0)

        # Upload as public URL for Instagram scheduled posts (never expires)
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

            logger.info(f"Media uploaded successfully with 7-day URL: {public_url}")
            return jsonify({
                'success': True,
                'media_url': public_url
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to upload to storage'}), 500

    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/upload', methods=['POST'])
@auth_required
def api_upload():
    """Post to Instagram via Late.dev using Firebase Storage URL (Premium only)"""
    try:
        # Check if user has premium subscription
        if not has_premium_subscription():
            return jsonify({'success': False, 'error': 'Premium subscription required', 'premium_required': True}), 403

        user_id = g.user.get('id')

        # Check if user is connected
        if not LateDevOAuthService.is_connected(user_id, 'instagram'):
            return jsonify({'success': False, 'error': 'Instagram not connected'}), 403

        # Get JSON data
        data = request.json
        caption = data.get('caption', '').strip()
        media_url = data.get('media_url', '').strip()  # Firebase Storage URL
        schedule_time = data.get('schedule_time')  # ISO 8601 format or null for immediate
        timezone = data.get('timezone', 'UTC')

        if not caption:
            return jsonify({'success': False, 'error': 'Caption is required'}), 400

        if not media_url:
            return jsonify({'success': False, 'error': 'Media URL is required'}), 400

        logger.info(f"Starting Instagram post for user {user_id}: {caption[:50]}...")

        # Post to Instagram via Late.dev using the Firebase URL
        result = InstagramUploadService.upload_media_from_url(
            user_id=user_id,
            media_url=media_url,
            caption=caption,
            schedule_time=schedule_time,
            timezone=timezone
        )

        if result['success']:
            logger.info(f"Instagram post successful: {result.get('post_id')}")

            # Create calendar event if post is scheduled
            post_id = result.get('post_id')
            if schedule_time and post_id:
                try:
                    from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                    calendar_manager = ContentCalendarManager(user_id)

                    # Extract first line of caption for title
                    title = caption.split('\n')[0][:100] if caption else 'Instagram Post'

                    event_id = calendar_manager.create_event(
                        title=title,
                        publish_date=schedule_time,
                        platform='Instagram',
                        status='ready',
                        content_type='organic',
                        instagram_post_id=post_id,
                        notes=f'Instagram Post ID: {post_id}'
                    )

                    logger.info(f"Created calendar event {event_id} for scheduled Instagram post {post_id}")
                    result['calendar_event_id'] = event_id
                except Exception as e:
                    logger.error(f"Error creating calendar event: {e}")
                    # Don't fail the whole request if calendar creation fails

            return jsonify(result)
        else:
            logger.error(f"Failed to post: {result.get('error')}")
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error in Instagram post: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/update-instagram-schedule', methods=['POST'])
@auth_required
def update_instagram_schedule():
    """Update Instagram post's scheduled publish time via Late.dev"""
    try:
        user_id = g.user.get('id')
        data = request.json

        post_id = data.get('post_id', '').strip()
        new_publish_time = data.get('publish_time', '').strip()

        if not post_id or not new_publish_time:
            return jsonify({
                'success': False,
                'error': 'Post ID and publish time are required'
            }), 400

        # Check if user is connected
        if not LateDevOAuthService.is_connected(user_id, 'instagram'):
            return jsonify({'success': False, 'error': 'Instagram not connected'}), 403

        # Update post schedule via Late.dev API
        try:
            from datetime import datetime

            # Validate datetime format
            try:
                dt = datetime.fromisoformat(new_publish_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                logger.info(f"Updating Instagram post {post_id} schedule to {formatted_time}")
            except Exception as e:
                logger.error(f"Error parsing datetime: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid datetime format'
                }), 400

            # Update via Late.dev API
            headers = {
                'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
                'Content-Type': 'application/json'
            }

            update_data = {
                'scheduledFor': formatted_time,
                'timezone': 'UTC'
            }

            response = requests.patch(
                f"https://getlate.dev/api/v1/posts/{post_id}",
                headers=headers,
                json=update_data,
                timeout=30
            )

            if response.status_code in [200, 201]:
                logger.info(f"Updated Instagram post {post_id} schedule successfully")
                return jsonify({
                    'success': True,
                    'message': 'Instagram schedule updated successfully'
                })
            else:
                error_msg = response.text
                logger.error(f"Failed to update schedule: {response.status_code} - {error_msg}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to update schedule: {error_msg}'
                }), 500

        except Exception as e:
            logger.error(f"Error updating Instagram schedule: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to update schedule: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Error in update_instagram_schedule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/generate-captions', methods=['POST'])
@auth_required
def api_generate_captions():
    """Generate Instagram captions with hashtags using AI"""
    try:
        data = request.json
        keywords = data.get('keywords', '').strip()
        content_description = data.get('content_description', '').strip()

        if not keywords:
            return jsonify({'success': False, 'error': 'Please provide target keywords'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        caption_generator = InstagramTitleGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        input_text = f"{keywords}\n{content_description}" if content_description else keywords
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

        # Step 2: Generate captions
        generation_result = caption_generator.generate_captions(
            keywords=keywords,
            content_description=content_description,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Caption generation failed')
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
                    description="Instagram Caption & Hashtags Generation",
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
            'captions': generation_result.get('captions', []),
            'message': 'Captions generated successfully',
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating Instagram captions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/delete-instagram-post', methods=['POST'])
@auth_required
def delete_instagram_post():
    """Delete Instagram post via Late.dev"""
    try:
        user_id = g.user.get('id')
        data = request.json

        post_id = data.get('post_id', '').strip()

        if not post_id:
            return jsonify({
                'success': False,
                'error': 'Post ID is required'
            }), 400

        # Check if user is connected
        if not LateDevOAuthService.is_connected(user_id, 'instagram'):
            return jsonify({'success': False, 'error': 'Instagram not connected'}), 403

        # Delete post via Late.dev API
        headers = {
            'Authorization': f'Bearer {os.environ.get("LATEDEV_API_KEY")}',
            'Content-Type': 'application/json'
        }

        response = requests.delete(
            f"https://getlate.dev/api/v1/posts/{post_id}",
            headers=headers,
            timeout=30
        )

        if response.status_code in [200, 201, 204]:
            logger.info(f"Deleted Instagram post {post_id} successfully")
            return jsonify({
                'success': True,
                'message': 'Instagram post deleted successfully'
            })
        else:
            error_msg = response.text
            logger.error(f"Failed to delete post: {response.status_code} - {error_msg}")
            return jsonify({
                'success': False,
                'error': f'Failed to delete post: {error_msg}'
            }), 500

    except Exception as e:
        logger.error(f"Error in delete_instagram_post: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
