"""
News Tracker Cron Routes - Automated news ingestion endpoint
"""
from flask import Blueprint, jsonify
import logging
from app.scripts.news_tracker.news_ingestion import run_news_ingestion

logger = logging.getLogger(__name__)
bp = Blueprint('news_tracker_cron', __name__, url_prefix='/api/cron/news')

@bp.route('/ingest', methods=['GET'])
def trigger_news_ingestion():
    """
    Trigger news ingestion process
    This endpoint should be called by a cron job (every 10-60 minutes)

    Example: curl http://localhost:8080/api/cron/news/ingest
    """
    try:
        logger.info("News ingestion triggered via cron endpoint")
        stats = run_news_ingestion()

        return jsonify({
            'success': True,
            'message': 'News ingestion completed',
            'stats': stats
        }), 200

    except Exception as e:
        logger.error(f"Error in news ingestion endpoint: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
