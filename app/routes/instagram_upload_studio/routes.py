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
from app.system.services.content_library_service import ContentLibraryManager
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

        # Get keywords and description from form data
        keywords = request.form.get('keywords', '').strip()
        content_description = request.form.get('content_description', '').strip()

        # Determine media type
        file_ext = os.path.splitext(media_file.filename)[1].lower()
        media_type = 'image' if file_ext in ['.jpg', '.jpeg', '.png', '.gif'] else 'video'

        # Generate unique filename
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
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
        media_items = data.get('media_items', [])  # Array of {url, type}
        content_id = data.get('content_id')  # Content library ID (optional)
        calendar_event_id = data.get('calendar_event_id')  # Calendar event ID (optional)
        schedule_time = data.get('schedule_time')  # ISO 8601 format or null for immediate
        timezone = data.get('timezone', 'UTC')

        if not caption:
            return jsonify({'success': False, 'error': 'Caption is required'}), 400

        if not media_items or len(media_items) == 0:
            return jsonify({'success': False, 'error': 'At least one media item is required'}), 400

        logger.info(f"Starting Instagram post for user {user_id}: {len(media_items)} media items, caption: {caption[:50]}...")

        # Post to Instagram via Late.dev using the Firebase URLs
        result = InstagramUploadService.upload_media_from_url(
            user_id=user_id,
            media_items=media_items,
            caption=caption,
            schedule_time=schedule_time,
            timezone=timezone
        )

        if result['success']:
            logger.info(f"Instagram post successful: {result.get('post_id')}")

            # Save/update content library
            post_id = result.get('post_id')
            if content_id:
                # Update existing content library entry
                try:
                    ContentLibraryManager.update_platform_status(
                        user_id=user_id,
                        content_id=content_id,
                        platform='instagram',
                        platform_data={
                            'post_id': post_id,
                            'scheduled_for': schedule_time,
                            'title': caption,
                            'status': 'scheduled' if schedule_time else 'posted'
                        }
                    )
                    logger.info(f"Updated content library {content_id} with Instagram post {post_id}")
                except Exception as e:
                    logger.error(f"Error updating content library: {e}")
            else:
                # Create new content library entry (use first media item)
                try:
                    first_media = media_items[0] if media_items else {}
                    media_url = first_media.get('url', '')
                    media_type = first_media.get('type', 'image')

                    content_id = ContentLibraryManager.save_content(
                        user_id=user_id,
                        media_url=media_url,
                        media_type=media_type,
                        keywords=data.get('keywords', ''),
                        content_description=data.get('content_description', ''),
                        platform='instagram',
                        platform_data={
                            'post_id': post_id,
                            'scheduled_for': schedule_time,
                            'title': caption,
                            'status': 'scheduled' if schedule_time else 'posted'
                        }
                    )
                    logger.info(f"Created content library {content_id} for Instagram post {post_id}")
                    result['content_id'] = content_id
                except Exception as e:
                    logger.error(f"Error creating content library: {e}")

            # Create or update calendar event for all posts
            if post_id:
                try:
                    from app.scripts.content_calendar.calendar_manager import ContentCalendarManager
                    from datetime import datetime, timezone as tz
                    import json
                    calendar_manager = ContentCalendarManager(user_id)

                    # Determine status and publish_date based on whether it's scheduled
                    if schedule_time:
                        status = 'ready'
                        publish_date = schedule_time
                    else:
                        status = 'posted'
                        publish_date = datetime.now(tz.utc).isoformat()

                    # Use first media URL for backward compatibility
                    first_media = media_items[0] if media_items else {}
                    media_url = first_media.get('url', '')

                    # Store all media items as JSON metadata
                    media_metadata = json.dumps(media_items) if media_items else ''

                    if calendar_event_id:
                        # Update the linked calendar event
                        # Keep the original title (requirements), store Instagram caption in description
                        success = calendar_manager.update_event(
                            event_id=calendar_event_id,
                            description=f"Caption: {caption}",  # Store Instagram caption in description
                            publish_date=publish_date,
                            platform='Instagram',
                            status=status,
                            instagram_post_id=post_id,
                            content_id=content_id if content_id else '',
                            media_url=media_url,  # Store first media URL for preview
                            media_metadata=media_metadata  # Store all media items
                        )
                        if success:
                            logger.info(f"Updated linked calendar event {calendar_event_id} for Instagram post {post_id}")
                            result['calendar_event_id'] = calendar_event_id
                        else:
                            logger.warning(f"Failed to update linked calendar event {calendar_event_id}, creating new one")
                            calendar_event_id = None  # Fall through to create new event

                    if not calendar_event_id:
                        # Create new calendar event
                        title = caption.split('\n')[0][:100] if caption else 'Instagram Post'
                        event_id = calendar_manager.create_event(
                            title=title,
                            description=caption,  # Store full caption in description
                            publish_date=publish_date,
                            platform='Instagram',
                            status=status,
                            content_type='organic',
                            instagram_post_id=post_id,
                            content_id=content_id if content_id else '',
                            notes=f'Instagram Post ID: {post_id}',
                            media_url=media_url,  # Store first media URL for preview
                            media_metadata=media_metadata  # Store all media items
                        )
                        logger.info(f"Created calendar event {event_id} for Instagram post {post_id} (scheduled={bool(schedule_time)})")
                        result['calendar_event_id'] = event_id

                except Exception as e:
                    logger.error(f"Error creating/updating calendar event: {e}")
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


@bp.route('/api/check-ongoing-uploads', methods=['GET'])
@auth_required
def check_ongoing_uploads():
    """Check if user has any uploads in 'uploading' status for Instagram"""
    try:
        user_id = g.user.get('id')

        # Check content library for uploads with status 'uploading'
        ongoing_uploads = []
        try:
            from app.system.services.content_library_service import ContentLibraryManager

            # Get recent content items (last 3 days)
            content_items = ContentLibraryManager.get_recent_content(user_id, hours=72)

            for item in content_items:
                platforms_posted = item.get('platforms_posted', {})
                instagram_data = platforms_posted.get('instagram', {})

                if instagram_data.get('status') == 'uploading':
                    ongoing_uploads.append({
                        'content_id': item.get('id'),
                        'title': instagram_data.get('title') or instagram_data.get('caption', 'Untitled')[:50],
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
        user_id = g.user.get('id')
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
            instagram_data = platforms_posted.get('instagram', {})
            status = instagram_data.get('status')

            # Only allow cancellation if status is 'uploading'
            if status != 'uploading':
                return jsonify({
                    'success': False,
                    'error': f'Cannot cancel - upload has already completed with status: {status}'
                }), 400

            # Delete from content library
            ContentLibraryManager.delete_content(user_id, content_id)

            # Find and delete associated calendar event using stored calendar_event_id
            calendar_event_id = instagram_data.get('calendar_event_id')

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
