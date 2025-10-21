from flask import render_template, request, jsonify, g, redirect, url_for
from datetime import datetime, timedelta
from firebase_admin import firestore
from app.routes.users import users_bp
import logging

logger = logging.getLogger(__name__)

def extract_model_from_description(description):
    """Extract model name from transaction description"""
    desc_lower = description.lower()

    # Check for model name after "tokens," pattern
    if 'tokens,' in desc_lower:
        parts = description.split('tokens,')
        if len(parts) > 1:
            model_part = parts[1].strip()
            # Remove any trailing text after the model name
            model_name = model_part.split()[0] if model_part else 'Unknown'
            return model_name

    # Check for specific model patterns
    if 'deepseek' in desc_lower:
        if 'deepseek-v3.2-exp' in desc_lower:
            return 'deepseek-v3.2-exp'
        return 'DeepSeek'

    if 'claude' in desc_lower:
        if 'claude-sonnet-4.5' in desc_lower:
            return 'claude-sonnet-4.5'
        elif 'claude-3-5-sonnet' in desc_lower:
            return 'claude-3-5-sonnet'
        # Parse model from description like "LLM - claude-3-5-sonnet"
        parts = description.split(',')
        if len(parts) > 1:
            return parts[-1].strip()
        return 'Claude'

    if 'nano banana' in desc_lower:
        return 'Nano Banana'

    if 'seeddream' in desc_lower:
        return 'SeedDream'

    if 'upscaling' in desc_lower:
        return 'Image Upscaling'

    if 'video' in desc_lower:
        return 'Image to Video'

    if 'search' in desc_lower:
        return 'Template Search'

    return 'Unknown'

def extract_feature_from_description(description):
    """Extract feature name from transaction description"""
    desc_lower = description.lower()

    # Map description patterns to feature names (ordered from most specific to least specific)

    # TikTok features
    if 'tiktok title' in desc_lower or 'tiktok titles & hashtags' in desc_lower:
        return 'TikTok Titles & Hashtags'
    if 'tiktok competitor' in desc_lower:
        return 'TikTok Competitor Analysis'

    # Video features
    if 'video deep dive' in desc_lower or 'deep dive analysis' in desc_lower:
        return 'Video Analysis'
    if 'video summary' in desc_lower:
        return 'Video Summary'
    if 'video tags' in desc_lower:
        return 'Video Tags'
    if 'video description' in desc_lower:
        return 'Video Description'
    if 'video title' in desc_lower:
        return 'Video Title'

    # X/Twitter features
    if 'post editor enhancement' in desc_lower or 'post editor' in desc_lower:
        return 'X Post Editor'
    if 'x content suggestions' in desc_lower or 'content suggestions generation' in desc_lower:
        return 'X Content Suggestions'
    if 'reply guy' in desc_lower:
        return 'Reply Guy'

    # Competitor & Analytics
    if 'competitor analysis' in desc_lower:
        return 'Competitor Analysis'
    if 'creator timeline' in desc_lower:
        return 'Creator Timeline Analysis'

    # Keyword Research
    if 'keyword research' in desc_lower or 'ai keyword research' in desc_lower:
        return 'Keyword Research'

    # Brain Dump
    if 'brain dump' in desc_lower:
        return 'Brain Dump'

    # Prompt Improvement
    if 'prompt improvement' in desc_lower:
        return 'Prompt Improvement'

    # Image/Video editing
    if 'nano banana' in desc_lower:
        return 'Nano Banana Edit'
    if 'seeddream' in desc_lower:
        return 'SeedDream Edit'
    if 'upscaling' in desc_lower:
        return 'Image Upscaling'
    if 'image to video' in desc_lower:
        return 'Image to Video'

    return 'Other'

def check_admin_access():
    """Check if user has admin access"""
    if not hasattr(g, 'user') or not g.user:
        return False

    subscription_plan = g.user.get('subscription_plan', '').lower().strip()
    return subscription_plan in ['admin', 'admin plan', 'administrator']

@users_bp.before_request
def require_admin():
    """Require admin access for all routes in this blueprint"""
    if not check_admin_access():
        return redirect(url_for('home.dashboard'))

@users_bp.route('/')
def index():
    """Display all users with their credit usage"""
    return render_template('admin/users_index.html')

@users_bp.route('/api/list')
def get_users_list():
    """Get list of all users with their monthly credit usage"""
    try:
        db = firestore.client()

        # Get all users
        users_ref = db.collection('users')
        users_data = []

        # Calculate start of current month
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)

        for user_doc in users_ref.stream():
            user = user_doc.to_dict()
            user_id = user_doc.id

            # Get current month transactions
            transactions_ref = db.collection('users').document(user_id).collection('transactions')
            transactions_query = transactions_ref.where('timestamp', '>=', month_start.isoformat()).stream()

            # Calculate credits spent per model and feature
            model_usage = {}
            feature_usage = {}
            total_spent = 0

            for tx_doc in transactions_query:
                tx = tx_doc.to_dict()
                if tx.get('type') == 'deduction':
                    amount = abs(tx.get('amount', 0))
                    description = tx.get('description', '')

                    # Extract model and feature from description
                    model = extract_model_from_description(description)
                    feature = extract_feature_from_description(description)

                    if model not in model_usage:
                        model_usage[model] = 0
                    model_usage[model] += amount

                    if feature not in feature_usage:
                        feature_usage[feature] = 0
                    feature_usage[feature] += amount

                    total_spent += amount

            # Format model usage for display
            model_breakdown = [
                {'model': model, 'credits': round(credits, 2)}
                for model, credits in model_usage.items()
            ]
            model_breakdown.sort(key=lambda x: x['credits'], reverse=True)

            # Get last login time
            last_login = user.get('last_login')
            if last_login:
                if isinstance(last_login, str):
                    try:
                        last_login_dt = datetime.fromisoformat(last_login.replace('Z', '+00:00'))
                        last_login_formatted = last_login_dt.strftime('%b %d, %Y at %I:%M %p')
                    except:
                        last_login_formatted = last_login
                else:
                    # Firestore timestamp
                    last_login_formatted = last_login.strftime('%b %d, %Y at %I:%M %p')
            else:
                last_login_formatted = 'Never'

            users_data.append({
                'id': user_id,
                'email': user.get('email', 'N/A'),
                'subscription_plan': user.get('subscription_plan', 'Free Plan'),
                'current_credits': round(user.get('credits', 0), 2),
                'total_spent_this_month': round(total_spent, 2),
                'model_breakdown': model_breakdown,
                'last_login': last_login_formatted,
                'streak': user.get('login_streak', 0),
                'created_at': user.get('created_at')
            })

        # Sort by total spent (descending)
        users_data.sort(key=lambda x: x['total_spent_this_month'], reverse=True)

        return jsonify({
            'success': True,
            'users': users_data,
            'total_users': len(users_data)
        })

    except Exception as e:
        logger.error(f"Error getting users list: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/<user_id>/daily-usage')
def get_user_daily_usage(user_id):
    """Get daily credit usage breakdown for a specific user"""
    try:
        db = firestore.client()

        # Get all transactions for the user (no date filtering)
        transactions_ref = db.collection('users').document(user_id).collection('transactions')
        transactions_query = transactions_ref.stream()

        # Organize by day and model
        daily_usage = {}

        for tx_doc in transactions_query:
            tx = tx_doc.to_dict()
            if tx.get('type') == 'deduction':
                timestamp_str = tx.get('timestamp', '')
                if timestamp_str:
                    try:
                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        day_key = dt.strftime('%Y-%m-%d')

                        if day_key not in daily_usage:
                            daily_usage[day_key] = {
                                'date': dt.strftime('%b %d, %Y'),
                                'models': {},
                                'total': 0
                            }

                        amount = abs(tx.get('amount', 0))
                        description = tx.get('description', '')

                        # Extract model from description
                        model = extract_model_from_description(description)

                        if model not in daily_usage[day_key]['models']:
                            daily_usage[day_key]['models'][model] = 0

                        daily_usage[day_key]['models'][model] += amount
                        daily_usage[day_key]['total'] += amount

                    except Exception as e:
                        logger.warning(f"Error parsing timestamp {timestamp_str}: {e}")

        # Convert to sorted list
        daily_list = []
        for day_key in sorted(daily_usage.keys(), reverse=True):
            day_data = daily_usage[day_key]
            model_breakdown = [
                {'model': model, 'credits': round(credits, 2)}
                for model, credits in day_data['models'].items()
            ]
            model_breakdown.sort(key=lambda x: x['credits'], reverse=True)

            daily_list.append({
                'date': day_data['date'],
                'total': round(day_data['total'], 2),
                'models': model_breakdown
            })

        # Get user info
        user_doc = db.collection('users').document(user_id).get()
        user_info = user_doc.to_dict() if user_doc.exists else {}

        return jsonify({
            'success': True,
            'user_id': user_id,
            'user_email': user_info.get('email', 'N/A'),
            'daily_usage': daily_list
        })

    except Exception as e:
        logger.error(f"Error getting daily usage for user {user_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@users_bp.route('/api/stats')
def get_overall_stats():
    """Get overall statistics for all users (models and features usage)"""
    try:
        db = firestore.client()

        # Calculate start of current month
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)

        # Get all users
        users_ref = db.collection('users')

        # Aggregate stats
        total_model_usage = {}
        total_feature_usage = {}

        for user_doc in users_ref.stream():
            user_id = user_doc.id

            # Get current month transactions
            transactions_ref = db.collection('users').document(user_id).collection('transactions')
            transactions_query = transactions_ref.where('timestamp', '>=', month_start.isoformat()).stream()

            for tx_doc in transactions_query:
                tx = tx_doc.to_dict()
                if tx.get('type') == 'deduction':
                    amount = abs(tx.get('amount', 0))
                    description = tx.get('description', '')

                    # Extract model and feature
                    model = extract_model_from_description(description)
                    feature = extract_feature_from_description(description)

                    if model not in total_model_usage:
                        total_model_usage[model] = 0
                    total_model_usage[model] += amount

                    if feature not in total_feature_usage:
                        total_feature_usage[feature] = 0
                    total_feature_usage[feature] += amount

        # Sort and format for charts
        model_stats = [
            {'name': model, 'credits': round(credits, 2)}
            for model, credits in total_model_usage.items()
        ]
        model_stats.sort(key=lambda x: x['credits'], reverse=True)

        feature_stats = [
            {'name': feature, 'credits': round(credits, 2)}
            for feature, credits in total_feature_usage.items()
        ]
        feature_stats.sort(key=lambda x: x['credits'], reverse=True)

        return jsonify({
            'success': True,
            'model_usage': model_stats[:10],  # Top 10 models
            'feature_usage': feature_stats[:10]  # Top 10 features
        })

    except Exception as e:
        logger.error(f"Error getting overall stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
