"""
TikTok Upload Studio Routes
OAuth connection, token management, and video uploading
"""

import os
import logging
from flask import render_template, redirect, url_for, request, jsonify, g
from app.routes.tiktok_upload_studio import bp
from app.system.auth.middleware import auth_required
from app.scripts.tiktok_upload_studio.tiktok_oauth_service import TikTokOAuthService
from app.scripts.tiktok_upload_studio.tiktok_upload_service import TikTokUploadService
from app.system.services.firebase_service import StorageService
import uuid

logger = logging.getLogger('tiktok_upload_studio')


@bp.route('/')
@auth_required
def index():
    """Render TikTok Upload Studio page"""
    try:
        user_id = g.user.get('id')

        # Check if user has TikTok connected
        is_connected = TikTokOAuthService.is_connected(user_id)

        # Get TikTok credentials from env
        client_key = os.environ.get('TIKTOK_CLIENT_KEY')
        redirect_uri = os.environ.get('TIKTOK_REDIRECT_URI', 'https://creatrics.com/tiktok/callback')

        return render_template(
            'tiktok_upload_studio/index.html',
            is_connected=is_connected,
            client_key=client_key,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        logger.error(f"Error loading TikTok Upload Studio: {str(e)}")
        return render_template('tiktok_upload_studio/index.html', error=str(e))


@bp.route('/connect')
@auth_required
def connect():
    """Initiate TikTok OAuth flow"""
    try:
        user_id = g.user.get('id')

        # Generate authorization URL
        auth_url = TikTokOAuthService.get_authorization_url(user_id)

        logger.info(f"Redirecting user {user_id} to TikTok OAuth: {auth_url}")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating TikTok OAuth: {str(e)}")
        return redirect(url_for('tiktok_upload_studio.index', error='oauth_init_failed'))


@bp.route('/callback')
@auth_required
def callback():
    """Handle TikTok OAuth callback"""
    try:
        user_id = g.user.get('id')

        # Get authorization code and state
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            logger.error(f"TikTok OAuth error: {error}")
            return redirect(url_for('tiktok_upload_studio.index', error='oauth_denied'))

        if not code or not state:
            logger.error("Missing code or state in TikTok callback")
            return redirect(url_for('tiktok_upload_studio.index', error='invalid_callback'))

        # Exchange code for access token
        result = TikTokOAuthService.handle_callback(user_id, code, state)

        if result['success']:
            logger.info(f"TikTok connected successfully for user {user_id}")
            return redirect(url_for('tiktok_upload_studio.index', success='connected'))
        else:
            logger.error(f"TikTok OAuth failed: {result.get('error')}")
            return redirect(url_for('tiktok_upload_studio.index', error=result.get('error')))

    except Exception as e:
        logger.error(f"Error in TikTok callback: {str(e)}")
        return redirect(url_for('tiktok_upload_studio.index', error='callback_failed'))


@bp.route('/disconnect', methods=['POST'])
@auth_required
def disconnect():
    """Disconnect TikTok account"""
    try:
        user_id = g.user.get('id')

        result = TikTokOAuthService.disconnect(user_id)

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
    """Check TikTok connection status"""
    try:
        user_id = g.user.get('id')

        is_connected = TikTokOAuthService.is_connected(user_id)
        user_info = None

        if is_connected:
            user_info = TikTokOAuthService.get_user_info(user_id)

        return jsonify({
            'success': True,
            'connected': is_connected,
            'user_info': user_info
        })

    except Exception as e:
        logger.error(f"Error checking TikTok status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/upload', methods=['POST'])
@auth_required
def api_upload():
    """Upload video to TikTok"""
    try:
        user_id = g.user.get('id')

        # Check if user is connected
        if not TikTokOAuthService.is_connected(user_id):
            return jsonify({'success': False, 'error': 'TikTok not connected'}), 403

        # Get form data
        video_file = request.files.get('video')
        title = request.form.get('title', '')
        privacy_level = request.form.get('privacy_level', 'SELF_ONLY')  # Default to private for testing
        mode = request.form.get('mode', 'direct')  # 'direct' or 'inbox'

        if not video_file:
            return jsonify({'success': False, 'error': 'No video file provided'}), 400

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        # Save video temporarily
        filename = f"{uuid.uuid4()}_{video_file.filename}"
        temp_path = f"/tmp/{filename}"
        video_file.save(temp_path)

        logger.info(f"Uploading video to TikTok for user {user_id}: {title} (mode: {mode})")

        # Upload to TikTok
        result = TikTokUploadService.upload_video(
            user_id=user_id,
            video_path=temp_path,
            title=title,
            privacy_level=privacy_level,
            mode=mode
        )

        # Clean up temp file
        try:
            os.remove(temp_path)
        except:
            pass

        if result['success']:
            logger.info(f"Video uploaded successfully: {result.get('publish_id')}")
            return jsonify(result)
        else:
            logger.error(f"Video upload failed: {result.get('error')}")
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error in video upload: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
