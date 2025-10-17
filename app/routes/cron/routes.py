# File: app/routes/cron/routes.py

from flask import Blueprint, jsonify, request
from app.system.services.firebase_service import db
import logging
import os
from functools import wraps
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Setup logger
logger = logging.getLogger('cron_routes')

# Create cron blueprint
bp = Blueprint('cron', __name__, url_prefix='/cron')

def verify_cron_request(f):
    """Decorator to verify cron requests are authorized"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for authorization header
        auth_header = request.headers.get('Authorization', '')

        # For development, allow localhost requests
        if request.remote_addr in ['127.0.0.1', '::1'] or request.host.startswith('localhost'):
            logger.info("Cron request from localhost - allowed for development")
            return f(*args, **kwargs)

        # Check for API key
        api_key = request.headers.get('X-Cron-Key')
        expected_key = os.environ.get('CRON_SECRET_KEY', 'your-secret-cron-key')

        if api_key == expected_key:
            logger.info("Cron request authenticated with API key")
            return f(*args, **kwargs)

        logger.warning(f"Unauthorized cron request from {request.remote_addr}")
        return jsonify({"error": "Unauthorized"}), 401

    return decorated_function

@bp.route('/health')
@verify_cron_request
def health_check():
    """Health check endpoint for monitoring cron service"""
    try:
        return jsonify({
            "status": "healthy",
            "service": "creaver_cron",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Cron service is running"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@bp.route('/cleanup-temp-files')
@verify_cron_request
def cleanup_temp_files():
    """Cron job for cleaning up temporary files"""
    try:
        # TODO: Implement cleanup logic for temporary files
        # - Remove old generated thumbnails/banners
        # - Clean up failed uploads
        # - Remove expired user sessions data

        logger.info("Temp file cleanup job started")

        # Placeholder logic
        cleanup_count = 0
        # cleanup_count = perform_actual_cleanup()

        return jsonify({
            "status": "success",
            "job": "cleanup_temp_files",
            "files_cleaned": cleanup_count,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Cleaned up {cleanup_count} temporary files"
        }), 200

    except Exception as e:
        logger.error(f"Temp file cleanup failed: {e}")
        return jsonify({
            "status": "error",
            "job": "cleanup_temp_files",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@bp.route('/cleanup-generated-content')
@verify_cron_request
def cleanup_generated_content():
    """Clean up old generated content (thumbnails, banners, etc.)"""
    try:
        logger.info("Starting generated content cleanup job")

        # TODO: Implement cleanup for:
        # - Thumbnails older than 30 days
        # - Banners older than 30 days
        # - Temporary AI generation files

        cleanup_summary = {
            "thumbnails_cleaned": 0,
            "banners_cleaned": 0,
            "temp_files_cleaned": 0
        }

        return jsonify({
            "status": "success",
            "job": "cleanup_generated_content",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": cleanup_summary,
            "message": "Generated content cleanup completed"
        }), 200

    except Exception as e:
        logger.error(f"Generated content cleanup failed: {e}")
        return jsonify({
            "status": "error",
            "job": "cleanup_generated_content",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@bp.route('/usage-stats')
@verify_cron_request
def usage_statistics():
    """Get usage statistics for monitoring"""
    try:
        # TODO: Implement stats collection for:
        # - Daily/weekly/monthly active users
        # - Content generation counts
        # - Popular features

        stats = {
            "total_users": 0,
            "active_today": 0,
            "content_generated": {
                "thumbnails": 0,
                "banners": 0,
                "tags_generated": 0,
                "descriptions": 0
            }
        }

        return jsonify({
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "usage_stats": stats
        }), 200

    except Exception as e:
        logger.error(f"Usage stats failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@bp.route('/update-default-reply-lists')
@verify_cron_request
def update_default_reply_lists():
    """Daily cron job to update default reply lists with fresh opportunities"""
    try:
        logger.info("Starting default reply lists update job")

        # Import the reply guy service
        from app.scripts.reply_guy.reply_guy_service import ReplyGuyService

        reply_service = ReplyGuyService()

        # Run analysis for the content_creators default list
        # We use a dummy user_id since this is a global operation
        analysis_result = reply_service.run_analysis(
            user_id='system',
            list_id='content_creators',
            list_type='default',
            time_range='24h'
        )

        if analysis_result:
            logger.info(f"Successfully updated default list: {analysis_result}")

            return jsonify({
                "status": "success",
                "job": "update_default_reply_lists",
                "timestamp": datetime.utcnow().isoformat(),
                "updated_lists": [analysis_result],
                "message": "Default reply lists updated successfully"
            }), 200
        else:
            logger.warning("Default list update returned no result")
            return jsonify({
                "status": "warning",
                "job": "update_default_reply_lists",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Default list update completed but no result returned"
            }), 200

    except Exception as e:
        logger.error(f"Default reply lists update failed: {e}")
        return jsonify({
            "status": "error",
            "job": "update_default_reply_lists",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

def update_user_analytics(user_id, user_data):
    """Update analytics for a single user (used in parallel processing)"""
    from app.scripts.accounts.x_analytics import fetch_x_analytics
    from app.scripts.accounts.youtube_analytics import fetch_youtube_analytics

    result = {
        'user_id': user_id,
        'x_updated': False,
        'youtube_updated': False,
        'tiktok_updated': False,
        'x_error': None,
        'youtube_error': None,
        'tiktok_error': None
    }

    # Update X Analytics if connected
    if user_data.get('x_account'):
        try:
            logger.info(f"Updating X analytics for user {user_id}")
            fetch_x_analytics(user_id, is_initial=False)
            result['x_updated'] = True
        except Exception as x_error:
            logger.error(f"Failed to update X analytics for user {user_id}: {str(x_error)}")
            result['x_error'] = str(x_error)

    # Update YouTube Analytics if connected
    if user_data.get('youtube_account'):
        try:
            logger.info(f"Updating YouTube analytics for user {user_id}")
            fetch_youtube_analytics(user_id)
            result['youtube_updated'] = True
        except Exception as yt_error:
            logger.error(f"Failed to update YouTube analytics for user {user_id}: {str(yt_error)}")
            result['youtube_error'] = str(yt_error)

    # Update TikTok Analytics if connected
    if user_data.get('tiktok_account'):
        try:
            logger.info(f"Updating TikTok analytics for user {user_id}")
            from app.scripts.accounts.tiktok_analytics import fetch_tiktok_analytics
            fetch_tiktok_analytics(user_id)
            result['tiktok_updated'] = True
        except Exception as tt_error:
            logger.error(f"Failed to update TikTok analytics for user {user_id}: {str(tt_error)}")
            result['tiktok_error'] = str(tt_error)

    return result

@bp.route('/update-all-users-analytics')
@verify_cron_request
def update_all_users_analytics():
    """
    Daily cron job to update analytics for all connected accounts (X, YouTube, TikTok)
    Uses parallel processing to handle 100+ users efficiently
    """
    try:
        logger.info("Starting parallel analytics update for all users")

        # Get all users from Firestore
        users_ref = db.collection('users')
        users = users_ref.stream()

        # Collect user data
        users_data = []
        for user_doc in users:
            user_data = user_doc.to_dict()
            # Only process users with at least one connected account
            if user_data.get('x_account') or user_data.get('youtube_account') or user_data.get('tiktok_account'):
                users_data.append((user_doc.id, user_data))

        total_users = len(users_data)
        logger.info(f"Found {total_users} users with connected accounts to update")

        stats = {
            'total_users': total_users,
            'x_updated': 0,
            'youtube_updated': 0,
            'tiktok_updated': 0,
            'x_errors': 0,
            'youtube_errors': 0,
            'tiktok_errors': 0
        }

        # Process users in parallel (max 10 concurrent workers to avoid API rate limits)
        max_workers = min(10, total_users) if total_users > 0 else 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_user = {
                executor.submit(update_user_analytics, user_id, user_data): user_id
                for user_id, user_data in users_data
            }

            # Collect results as they complete
            for future in as_completed(future_to_user):
                try:
                    result = future.result()

                    if result['x_updated']:
                        stats['x_updated'] += 1
                    if result['x_error']:
                        stats['x_errors'] += 1

                    if result['youtube_updated']:
                        stats['youtube_updated'] += 1
                    if result['youtube_error']:
                        stats['youtube_errors'] += 1

                    if result['tiktok_updated']:
                        stats['tiktok_updated'] += 1
                    if result['tiktok_error']:
                        stats['tiktok_errors'] += 1

                except Exception as e:
                    user_id = future_to_user[future]
                    logger.error(f"Unexpected error processing user {user_id}: {str(e)}")

        logger.info(f"Analytics update completed: {stats}")

        return jsonify({
            "status": "success",
            "job": "update_all_users_analytics",
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats,
            "message": f"Updated analytics for {stats['total_users']} users in parallel",
            "performance": {
                "concurrent_workers": max_workers,
                "processing_mode": "parallel"
            }
        }), 200

    except Exception as e:
        logger.error(f"Analytics update job failed: {e}")
        return jsonify({
            "status": "error",
            "job": "update_all_users_analytics",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500