"""
News Tracker Cron Routes - Automated news ingestion endpoint
"""
from flask import Blueprint, jsonify
import logging
import threading
from app.scripts.news_tracker.news_ingestion import run_news_ingestion

logger = logging.getLogger(__name__)
bp = Blueprint('news_tracker_cron', __name__, url_prefix='/api/cron/news')

@bp.route('/ingest', methods=['GET'])
def trigger_news_ingestion():
    """
    Trigger news ingestion process in background thread
    This endpoint should be called by a cron job (every 10-60 minutes)

    Example: curl http://localhost:8080/api/cron/news/ingest

    Returns immediately while processing continues in background.
    """
    try:
        logger.info("News ingestion triggered via cron endpoint - starting background thread")

        def run_ingestion_bg():
            """Background thread function"""
            try:
                logger.info("Background news ingestion started")
                stats = run_news_ingestion()
                logger.info(f"Background news ingestion completed: {stats}")
            except Exception as e:
                logger.error(f"Error in background news ingestion: {e}", exc_info=True)

        # Start ingestion in background thread (frees worker immediately)
        thread = threading.Thread(target=run_ingestion_bg)
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'News ingestion started in background'
        }), 200

    except Exception as e:
        logger.error(f"Error starting news ingestion: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
