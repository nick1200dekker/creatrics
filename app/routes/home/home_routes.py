# File: app/routes/home/home_routes.py

from flask import Blueprint, render_template, jsonify, g, request
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import UserService
import logging
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger('home_routes')

# Create home blueprint
bp = Blueprint('home', __name__)

@bp.route('/')
def dashboard():
    """Main landing page - show the dashboard"""
    return render_template('home/dashboard.html')

@bp.route('/dashboard')
@bp.route('/home')
def home():
    """Main dashboard/home page
    
    The primary landing page after authentication with user stats,
    welcome messages, and quick access to all app features.
    """
    # Handle both authenticated and unauthenticated users
    if hasattr(g, 'user') and g.user and not g.user.get('is_guest'):
        # Authenticated user - update login streak
        try:
            update_login_streak(g.user.get('id'))
        except Exception as e:
            logger.error(f"Error updating login streak: {e}")
    
    # Render the home page (template will show different content based on g.user)
    return render_template('home/dashboard.html')

@bp.route('/api/dashboard-stats')
def dashboard_stats():
    """API endpoint to get dashboard statistics
    
    Returns user credits, login streak, and content created count.
    """
    if not hasattr(g, 'user') or not g.user or g.user.get('is_guest'):
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        user_id = g.user.get('id')
        user_data = UserService.get_user(user_id) or {}
        
        # Get user stats
        credits = user_data.get('credits', 0)
        login_streak = user_data.get('login_streak', 0)
        
        return jsonify({
            'credits': credits,
            'login_streak': login_streak,
            'subscription_plan': user_data.get('subscription_plan', 'Free Plan')
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({"error": "Failed to load stats"}), 500

@bp.route('/api/dashboard-data')
def dashboard_data():
    """API endpoint to get comprehensive dashboard data
    
    This endpoint returns user-specific dashboard data including:
    - Connected accounts status
    - Channel analytics summaries
    - Quick access suggestions
    """
    if not hasattr(g, 'user') or not g.user or g.user.get('is_guest'):
        return jsonify({"error": "Not authenticated"}), 401
    
    # Get user data from g.user
    user_id = g.user.get('id')
    
    # Get detailed user data from Firebase
    user_data = UserService.get_user(user_id) or {}
    
    # Prepare response data
    response_data = {
        "user_id": user_id,
        "username": user_data.get('username', g.user.get('data', {}).get('username', 'User')),
        "credits": user_data.get('credits', 0),
        "subscription_plan": user_data.get('subscription_plan', 'Free Plan'),
        
        # Connected accounts
        "x_connected": bool(user_data.get('x_account', '')),
        "x_account": user_data.get('x_account', ''),
        "youtube_connected": bool(user_data.get('youtube_account', '')),
        "youtube_account": user_data.get('youtube_account', ''),
        "tiktok_connected": bool(user_data.get('tiktok_account', '')),
        "tiktok_account": user_data.get('tiktok_account', ''),
    }
    
    # Initialize Firestore if needed
    try:
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get X Analytics Summary if connected
        if response_data['x_connected']:
            try:
                analytics_ref = db.collection('users').document(user_id).collection('x_analytics').document('latest')
                analytics_doc = analytics_ref.get()
                
                if analytics_doc.exists:
                    x_analytics = analytics_doc.to_dict()
                    
                    # Extract key metrics for dashboard
                    response_data["x_analytics"] = {
                        'followers': x_analytics.get('followers_count', 0),
                        'avg_views': int(round(x_analytics.get('rolling_avg_views', 0))),
                        'engagement_rate': x_analytics.get('rolling_avg_engagement', 0),
                        'engagement_rate_display': f"{x_analytics.get('rolling_avg_engagement', 0):.1f}%",
                        'followers_to_following_ratio': x_analytics.get('followers_to_following_ratio', 0),
                        'ratio_status': x_analytics.get('ratio_status', 'N/A')
                    }
            except Exception as e:
                logger.error(f"Error fetching X analytics: {str(e)}")
        
        # Get YouTube Analytics Summary if connected
        if response_data['youtube_connected']:
            try:
                youtube_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
                youtube_doc = youtube_ref.get()
                
                if youtube_doc.exists:
                    youtube_analytics = youtube_doc.to_dict()
                    
                    # Extract key metrics for dashboard
                    response_data["youtube_analytics"] = {
                        'views': youtube_analytics.get('views', 0),
                        'subscribers_gained': youtube_analytics.get('subscribers_gained', 0),
                        'watch_time_minutes': youtube_analytics.get('watch_time_minutes', 0),
                        'watch_time_hours': round(youtube_analytics.get('watch_time_minutes', 0) / 60, 1),
                        'average_view_percentage': youtube_analytics.get('average_view_percentage', 0),
                        'engagement_rate': youtube_analytics.get('engagement_rate', 0)
                    }
            except Exception as e:
                logger.error(f"Error fetching YouTube analytics: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error fetching analytics data: {str(e)}")
    
    return jsonify(response_data)

@bp.route('/api/analytics-history/<platform>')
def get_analytics_history(platform):
    """Get historical analytics data for charts on dashboard
    
    Query parameters:
    - days: number of days to retrieve (default: 7)
    """
    if not hasattr(g, 'user') or not g.user or g.user.get('is_guest'):
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = g.user.get('id')
    
    # Validate platform
    if platform not in ['x', 'youtube', 'tiktok']:
        return jsonify({"error": "Invalid platform"}), 400
    
    try:
        # Initialize Firestore
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get query parameters
        days = request.args.get('days', 7, type=int)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        historical_data = []
        
        if platform == 'x':
            # Get X historical data
            collection_ref = db.collection('users').document(user_id).collection('x_analytics').document('history').collection('daily')
            query = collection_ref.where('__name__', '>=', start_date_str).where('__name__', '<=', end_date_str).order_by('__name__')
            
            docs = query.stream()
            for doc in docs:
                data = doc.to_dict()
                data['date'] = doc.id
                historical_data.append({
                    'date': data['date'],
                    'followers': data.get('followers_count', 0),
                    'views': data.get('rolling_avg_views', 0),
                    'engagement': data.get('rolling_avg_engagement', 0)
                })
                
        elif platform == 'youtube':
            # Get YouTube historical data
            collection_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('history').collection('daily')
            query = collection_ref.where('__name__', '>=', start_date_str).where('__name__', '<=', end_date_str).order_by('__name__')
            
            docs = query.stream()
            for doc in docs:
                data = doc.to_dict()
                data['date'] = doc.id
                historical_data.append({
                    'date': data['date'],
                    'views': data.get('views', 0),
                    'watch_time_minutes': data.get('watch_time_minutes', 0),
                    'subscribers_gained': data.get('subscribers_gained', 0)
                })
        
        return jsonify({
            "platform": platform,
            "data": historical_data,
            "days": days
        })
        
    except Exception as e:
        logger.error(f"Error fetching {platform} analytics history: {str(e)}")
        return jsonify({"error": "Failed to fetch historical data"}), 500

@bp.route('/api/upcoming-content')
def get_upcoming_content():
    """Get upcoming scheduled content from calendar
    
    Returns the next 5 scheduled content pieces
    """
    if not hasattr(g, 'user') or not g.user or g.user.get('is_guest'):
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = g.user.get('id')
    
    try:
        # Initialize Firestore
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get upcoming events from content calendar
        today = datetime.now().strftime('%Y-%m-%d')
        events_ref = db.collection(f'users/{user_id}/content_calendar')
        
        # Query for future events
        query = events_ref.where('publish_date', '>=', today).order_by('publish_date').limit(5)
        
        upcoming_events = []
        for doc in query.stream():
            event = doc.to_dict()
            upcoming_events.append({
                'id': event.get('id'),
                'title': event.get('title'),
                'publish_date': event.get('publish_date'),
                'platform': event.get('platform'),
                'status': event.get('status', 'draft'),
                'content_type': event.get('content_type', 'organic')
            })
        
        return jsonify({
            "events": upcoming_events,
            "count": len(upcoming_events)
        })
        
    except Exception as e:
        logger.error(f"Error fetching upcoming content: {str(e)}")
        return jsonify({"error": "Failed to fetch upcoming content"}), 500

def update_login_streak(user_id):
    """Update user's login streak
    
    Tracks consecutive days of user logins and updates the streak count.
    Resets streak if more than 24 hours have passed since last login.
    """
    try:
        user_data = UserService.get_user(user_id) or {}
        
        # Get current time and last login
        now = datetime.now()
        today = now.date()
        
        last_login_str = user_data.get('last_login_date')
        current_streak = user_data.get('login_streak', 0)
        
        # Check if user logged in today already
        if last_login_str:
            try:
                last_login = datetime.fromisoformat(last_login_str).date()
                
                # If already logged in today, don't update streak
                if last_login == today:
                    return current_streak
                
                # If logged in yesterday, increment streak
                if last_login == today - timedelta(days=1):
                    current_streak += 1
                # If more than 1 day gap, reset streak
                elif last_login < today - timedelta(days=1):
                    current_streak = 1
                else:
                    current_streak = 1
                    
            except ValueError:
                # Invalid date format, start fresh
                current_streak = 1
        else:
            # First time login
            current_streak = 1
        
        # Update user data
        update_data = {
            'last_login_date': now.isoformat(),
            'login_streak': current_streak,
            'last_activity': now.isoformat()
        }
        
        # Reward long streaks (optional)
        if current_streak > 0 and current_streak % 7 == 0:  # Every 7 days
            bonus_credits = 2
            current_credits = user_data.get('credits', 0)
            update_data['credits'] = current_credits + bonus_credits
            
            logger.info(f"User {user_id} earned {bonus_credits} bonus credits for {current_streak}-day streak")
        
        UserService.update_user(user_id, update_data)
        logger.info(f"Updated login streak for user {user_id}: current_streak={current_streak}")

        return current_streak

    except Exception as e:
        logger.error(f"Error updating login streak for user {user_id}: {str(e)}")
        return 0