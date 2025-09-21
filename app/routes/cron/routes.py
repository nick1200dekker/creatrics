# File: app/routes/cron/routes.py

from flask import Blueprint, jsonify, request
from app.system.services.firebase_service import db
from app.scripts.player_stats.player_service import PlayerStatsService
import logging
import os
from functools import wraps
from datetime import datetime

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
            "service": "soccer_stats_cron",
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
    """Placeholder cron job for cleaning up temporary files"""
    try:
        # TODO: Implement cleanup logic for temporary files
        # - Remove old generated files from temp storage
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

@bp.route('/update-players')
@verify_cron_request
def scheduled_player_update():
    """Scheduled job to update player data every 12 hours"""
    try:
        logger.info("Starting scheduled player update job")
        
        # Initialize player service
        player_service = PlayerStatsService()
        
        # Get batch size from query parameter (default 50)
        batch_size = int(request.args.get('batch_size', 50))
        
        # Perform bulk update
        update_summary = player_service.bulk_update_players(max_players=batch_size)
        
        # Log results
        logger.info(f"Player update completed: {update_summary['successful_updates']}/{update_summary['total_attempted']} successful")
        
        if update_summary['errors']:
            logger.warning(f"Update had {len(update_summary['errors'])} errors")
            for error in update_summary['errors'][:5]:  # Log first 5 errors
                logger.error(f"Player update error: {error}")
        
        return jsonify({
            "status": "success",
            "job": "scheduled_player_update",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_attempted": update_summary['total_attempted'],
                "successful_updates": update_summary['successful_updates'],
                "failed_updates": update_summary['failed_updates'],
                "error_count": len(update_summary['errors']),
                "batch_size": batch_size
            },
            "updated_players": update_summary['updated_players'],
            "errors": update_summary['errors'][:10]  # Return first 10 errors
        }), 200
        
    except Exception as e:
        logger.error(f"Scheduled player update failed: {e}")
        return jsonify({
            "status": "error",
            "job": "scheduled_player_update",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@bp.route('/registry-stats')
@verify_cron_request
def registry_statistics():
    """Get player registry statistics for monitoring"""
    try:
        player_service = PlayerStatsService()
        
        # Get all registry players
        registry_players = player_service.get_all_registry_players()
        
        # Calculate statistics
        total_players = len(registry_players)
        active_players = len([p for p in registry_players if p.get('status') == 'active'])
        error_players = len([p for p in registry_players if p.get('status') == 'error'])
        
        # Find players that haven't been updated recently
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        stale_players = [
            p for p in registry_players 
            if not p.get('last_updated') or p.get('last_updated') < cutoff_time
        ]
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "registry_stats": {
                "total_players": total_players,
                "active_players": active_players,
                "error_players": error_players,
                "stale_players": len(stale_players),
                "stale_player_names": [p.get('name', 'Unknown') for p in stale_players[:10]]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Registry stats failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500
