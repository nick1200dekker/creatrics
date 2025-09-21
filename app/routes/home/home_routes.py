# File: app/routes/home/routes.py

from flask import Blueprint, render_template, jsonify, g, request
from app.system.auth.middleware import auth_required  # Changed from optional_auth
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
    return render_template('core/home.html')

@bp.route('/api/dashboard-stats')
def dashboard_stats():
    """API endpoint to get dashboard statistics
    
    Returns user credits, login streak, and content created count.
    """
    if not hasattr(g, 'user') or not g.user:
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
# @auth_required - Removed since middleware now handles authentication
def dashboard_data():
    """API endpoint to get dashboard data
    
    This endpoint requires authentication and returns user-specific
    dashboard data, including X and YouTube analytics if available.
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Get user data from g.user
    user_id = g.user.get('id')
    
    # Try to get more detailed user data from Firebase
    user_data = UserService.get_user(user_id) or {}
    
    # Check if X is connected
    x_connected = bool(user_data.get('x_account', ''))
    x_analytics = None
    
    if x_connected:
        try:
            # Initialize Firestore if needed
            if not firebase_admin._apps:
                try:
                    firebase_admin.initialize_app()
                except ValueError:
                    pass
            
            # Get Firestore client
            db = firestore.client()
            
            # Get analytics document from X subcollection structure - NEW: Read from 'latest'
            analytics_ref = db.collection('users').document(user_id).collection('x_analytics').document('latest')
            analytics_doc = analytics_ref.get()
            
            if analytics_doc.exists:
                x_analytics = analytics_doc.to_dict()
                
                # Format metrics for display on dashboard
                if x_analytics:
                    # Format followers_to_following_ratio for display
                    ratio = x_analytics.get('followers_to_following_ratio', 0)
                    x_analytics['followers_to_following_ratio_display'] = f"{ratio:.1f}%"
                    
                    # Format rolling_avg_engagement for display
                    engagement = x_analytics.get('rolling_avg_engagement', 0)
                    x_analytics['engagement_rate_display'] = f"{engagement:.1f}%"
                    
                    # Format rolling_avg_views for display - rounded to nearest whole number
                    avg_views = int(round(x_analytics.get('rolling_avg_views', 0)))
                    x_analytics['avg_views'] = avg_views
                    
                    # Format followers for display
                    x_analytics['followers'] = x_analytics.get('followers_count', 0)
                
        except Exception as e:
            logger.error(f"Error fetching X analytics data: {str(e)}")
            x_analytics = None
    
    # Check if YouTube is connected
    youtube_connected = bool(user_data.get('youtube_account', ''))
    youtube_analytics = None
    
    if youtube_connected:
        try:
            # Initialize Firestore if needed
            if not firebase_admin._apps:
                try:
                    firebase_admin.initialize_app()
                except ValueError:
                    pass
            
            # Get Firestore client
            db = firestore.client()
            
            # Get YouTube analytics document from subcollection structure - NEW: Read from 'latest'
            youtube_analytics_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
            youtube_analytics_doc = youtube_analytics_ref.get()
            
            if youtube_analytics_doc.exists:
                youtube_analytics = youtube_analytics_doc.to_dict()
                
                # Format metrics for display on dashboard
                if youtube_analytics:
                    # Format views for display
                    views = youtube_analytics.get('views', 0)
                    youtube_analytics['views_display'] = f"{views:,}" if views > 0 else "0"
                    
                    # Format average view percentage for display
                    avg_view_percentage = youtube_analytics.get('average_view_percentage', 0)
                    youtube_analytics['avg_watch_time_display'] = f"{avg_view_percentage:.1f}%"
                    
                    # Format subscribers gained for display
                    subscribers_gained = youtube_analytics.get('subscribers_gained', 0)
                    youtube_analytics['new_subscribers'] = subscribers_gained
                    youtube_analytics['new_subscribers_display'] = f"+{subscribers_gained}" if subscribers_gained > 0 else "0"
                    
                    # Format engagement rate for display
                    engagement_rate = youtube_analytics.get('engagement_rate', 0)
                    youtube_analytics['engagement_rate_display'] = f"{engagement_rate:.1f}%"
                
        except Exception as e:
            logger.error(f"Error fetching YouTube analytics data: {str(e)}")
            youtube_analytics = None
    
    # Prepare response data
    response_data = {
        "user_id": user_id,
        "username": user_data.get('username', g.user.get('data', {}).get('username', 'User')),
        "credits": user_data.get('credits', 100),  # Use actual credits or default
        "subscription_plan": user_data.get('subscription_plan', 'Free Plan'),
        "x_connected": x_connected,
        "x_account": user_data.get('x_account', ''),
        "youtube_connected": youtube_connected,
        "youtube_account": user_data.get('youtube_account', ''),
        "widgets": [
            {"id": "recent_posts", "title": "Recent Posts"},
            {"id": "analytics", "title": "Analytics"},
            {"id": "tasks", "title": "Upcoming Tasks"}
        ]
    }
    
    # Include X analytics if available
    if x_analytics:
        response_data["x_analytics"] = x_analytics
    
    # Include YouTube analytics if available
    if youtube_analytics:
        response_data["youtube_analytics"] = youtube_analytics
    
    return jsonify(response_data)

@bp.route('/api/analytics-history/<platform>')
# @auth_required - Removed since middleware now handles authentication
def get_analytics_history(platform):
    """Get historical analytics data for a platform
    
    Optional endpoint to retrieve historical data for charts/trends
    Query parameters:
    - days: number of days to retrieve (default: 30)
    - start_date: start date in YYYY-MM-DD format
    - end_date: end date in YYYY-MM-DD format
    """
    if not hasattr(g, 'user') or not g.user:
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = g.user.get('id')
    
    # Validate platform
    if platform not in ['x', 'youtube']:
        return jsonify({"error": "Invalid platform"}), 400
    
    try:
        # Initialize Firestore if needed
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get query parameters
        days = request.args.get('days', 30, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build collection reference
        if platform == 'x':
            collection_ref = db.collection('users').document(user_id).collection('x_analytics').document('history').collection('daily')
        else:
            collection_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('history').collection('daily')
        
        # Query historical data
        if start_date and end_date:
            # Use date range
            query = collection_ref.where('__name__', '>=', start_date).where('__name__', '<=', end_date).order_by('__name__')
        else:
            # Use days limit - get most recent documents
            from datetime import datetime, timedelta
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)
            start_date_str = start_dt.strftime('%Y-%m-%d')
            end_date_str = end_dt.strftime('%Y-%m-%d')
            
            query = collection_ref.where('__name__', '>=', start_date_str).where('__name__', '<=', end_date_str).order_by('__name__')
        
        # Execute query
        docs = query.stream()
        
        historical_data = []
        for doc in docs:
            data = doc.to_dict()
            data['date'] = doc.id  # Document ID is the date
            historical_data.append(data)
        
        return jsonify({
            "platform": platform,
            "data": historical_data,
            "count": len(historical_data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching {platform} analytics history: {str(e)}")
        return jsonify({"error": "Failed to fetch historical data"}), 500


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
        logger.info(f"Updated login streak for user {user_id}: {current_streak} days")
        
        return current_streak
        
    except Exception as e:
        logger.error(f"Error updating login streak for user {user_id}: {e}")
        return 0