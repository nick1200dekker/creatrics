"""
Credits history routes for displaying user's credit transaction history
"""

from flask import render_template, jsonify, g
from app.routes.credits_history import bp
from app.system.auth.middleware import auth_required
from app.system.credits.credits_manager import CreditsManager
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@bp.route('/credits-history')
@auth_required
def index():
    """Render the credits history page"""
    return render_template('credits_history/index.html')

@bp.route('/credits-history/data')
@auth_required
def get_history_data():
    """Get credits transaction history data"""
    try:
        user_id = g.user.get('id')
        credits_manager = CreditsManager()

        # Get current credits
        current_credits = credits_manager.get_user_credits(user_id)

        # Get transaction history (increased limit for better history view)
        transactions = credits_manager.get_transaction_history(user_id, limit=100)

        # Format transactions for display
        formatted_transactions = []
        for tx in transactions:
            # Parse timestamp
            timestamp_str = tx.get('timestamp', '')
            if timestamp_str:
                try:
                    # Parse ISO format timestamp
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    formatted_date = dt.strftime('%b %d, %Y at %I:%M %p')
                except:
                    formatted_date = timestamp_str
            else:
                formatted_date = 'Unknown date'

            formatted_transactions.append({
                'id': tx.get('id', ''),
                'amount': tx.get('amount', 0),
                'description': tx.get('description', 'Unknown transaction'),
                'type': tx.get('type', 'unknown'),
                'timestamp': tx.get('timestamp', ''),
                'formatted_date': formatted_date,
                'feature_id': tx.get('feature_id', '')
            })

        return jsonify({
            'success': True,
            'current_credits': current_credits,
            'transactions': formatted_transactions
        })

    except Exception as e:
        logger.error(f"Error getting credits history: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500