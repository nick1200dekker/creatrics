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
    # Handle both authenticated and unauthenticated users
    if hasattr(g, 'user') and g.user and not g.user.get('is_guest'):
        # Authenticated user - update login streak
        try:
            update_login_streak(g.user.get('id'))
        except Exception as e:
            logger.error(f"Error updating login streak: {e}")

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
        has_seen_welcome = user_data.get('has_seen_welcome', False)

        return jsonify({
            'credits': credits,
            'login_streak': login_streak,
            'subscription_plan': user_data.get('subscription_plan', 'Free Plan'),
            'has_seen_welcome': has_seen_welcome
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({"error": "Failed to load stats"}), 500

@bp.route('/api/user/update-welcome-status', methods=['POST'])
def update_welcome_status():
    """Update user's welcome modal seen status"""
    if not hasattr(g, 'user') or not g.user or g.user.get('is_guest'):
        return jsonify({"error": "Not authenticated"}), 401

    try:
        user_id = g.user.get('id')
        data = request.get_json()
        has_seen_welcome = data.get('has_seen_welcome', True)

        UserService.update_user(user_id, {
            'has_seen_welcome': has_seen_welcome
        })

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error updating welcome status: {e}")
        return jsonify({"error": "Failed to update status"}), 500

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

                    # Calculate metrics from last 30 days to match Analytics page default
                    posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
                    cutoff_date = datetime.now() - timedelta(days=30)
                    cutoff_timestamp = cutoff_date.timestamp()

                    # Calculate metrics from posts within last 30 days
                    total_views = 0
                    total_engagement = 0
                    post_count = 0

                    for doc in posts_collection.stream():
                        post = doc.to_dict()
                        if post.get('created_at_timestamp', 0) >= cutoff_timestamp:
                            views = post.get('views', 0)
                            engagement = (post.get('likes', 0) +
                                        post.get('retweets', 0) +
                                        post.get('replies', 0) +
                                        post.get('bookmarks', 0))

                            total_views += views
                            total_engagement += engagement
                            post_count += 1

                    # Calculate averages
                    avg_views = int(round(total_views / post_count)) if post_count > 0 else 0
                    engagement_rate = (total_engagement / total_views * 100) if total_views > 0 else 0

                    # Extract key metrics for dashboard (last 30 days)
                    response_data["x_analytics"] = {
                        'followers': x_analytics.get('followers_count', 0),
                        'avg_views': avg_views,
                        'engagement_rate': engagement_rate,
                        'engagement_rate_display': f"{engagement_rate:.1f}%",
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

                    # Calculate metrics from last 30 days of daily_data to match Analytics page
                    daily_data = youtube_analytics.get('daily_data', [])

                    # Filter for last 30 days
                    cutoff_date = datetime.now() - timedelta(days=30)
                    cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')

                    filtered_data = [
                        day for day in daily_data
                        if day.get('date', '') >= cutoff_date_str
                    ]

                    # Calculate totals from last 30 days
                    total_views = sum(day.get('views', 0) for day in filtered_data)
                    total_watch_time_minutes = sum(day.get('watch_time_minutes', 0) for day in filtered_data)
                    total_subscribers_gained = sum(day.get('subscribers_gained', 0) for day in filtered_data)

                    # Extract key metrics for dashboard (last 30 days)
                    response_data["youtube_analytics"] = {
                        'views': total_views,
                        'subscribers_gained': total_subscribers_gained,
                        'watch_time_minutes': total_watch_time_minutes,
                        'watch_time_hours': round(total_watch_time_minutes / 60, 1) if total_watch_time_minutes > 0 else 0,
                        'average_view_percentage': youtube_analytics.get('average_view_percentage', 0),
                        'engagement_rate': youtube_analytics.get('engagement_rate', 0)
                    }
            except Exception as e:
                logger.error(f"Error fetching YouTube analytics: {str(e)}")

        # Get TikTok Analytics Summary if connected
        if response_data['tiktok_connected']:
            try:
                tiktok_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('latest')
                tiktok_doc = tiktok_ref.get()

                if tiktok_doc.exists:
                    tiktok_analytics = tiktok_doc.to_dict()

                    # Get posts from Firestore to calculate metrics from last 30 days
                    posts_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('posts')
                    posts_doc = posts_ref.get()

                    engagement_rate = 0
                    total_views_30 = 0
                    total_likes_30 = 0

                    if posts_doc.exists:
                        posts_data = posts_doc.to_dict()
                        all_posts = posts_data.get('posts', [])

                        # Filter posts from last 30 days
                        cutoff_date = datetime.now() - timedelta(days=30)
                        cutoff_timestamp = cutoff_date.timestamp()

                        # Calculate metrics from posts within last 30 days
                        total_engagement_rate = 0
                        posts_with_views = 0

                        for post in all_posts:
                            create_time = post.get('create_time', 0)
                            if create_time >= cutoff_timestamp:
                                views = post.get('views', 0)
                                likes = post.get('likes', 0)
                                comments = post.get('comments', 0)
                                shares = post.get('shares', 0)

                                total_views_30 += views
                                total_likes_30 += likes

                                if views > 0:
                                    engagement = likes + comments + shares
                                    post_engagement_rate = (engagement / views) * 100
                                    total_engagement_rate += post_engagement_rate
                                    posts_with_views += 1

                        if posts_with_views > 0:
                            engagement_rate = total_engagement_rate / posts_with_views

                    # Extract key metrics for dashboard (last 30 days)
                    response_data["tiktok_analytics"] = {
                        'followers': tiktok_analytics.get('followers', 0),
                        'likes': total_likes_30,  # Likes from last 30 days
                        'engagement_rate': engagement_rate,
                        'total_views_35': total_views_30,  # Actually last 30 days now
                        'total_likes_35': total_likes_30,
                        'total_comments_35': tiktok_analytics.get('total_comments_35', 0),
                        'total_shares_35': tiktok_analytics.get('total_shares_35', 0),
                        'post_count': posts_with_views if posts_doc.exists else 0
                    }
            except Exception as e:
                logger.error(f"Error fetching TikTok analytics: {str(e)}")

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

@bp.route('/api/x-content-suggestions')
def get_x_content_suggestions():
    """Generate X content suggestions based on user's recent posts

    Query parameters:
    - refresh: Set to 'true' to force refresh and bypass cache

    Returns 5 personalized content suggestions (cached for 24 hours)
    """
    if not hasattr(g, 'user') or not g.user or g.user.get('is_guest'):
        return jsonify({"success": False, "error": "Not authenticated"}), 401

    user_id = g.user.get('id')

    try:
        from app.scripts.home.x_content_suggestions import XContentSuggestions

        # Check if force refresh is requested
        force_refresh = request.args.get('refresh', '').lower() == 'true'

        # Initialize the suggestions generator
        suggestions_generator = XContentSuggestions()

        # Generate suggestions (will use cache if available and < 24h old)
        result = suggestions_generator.generate_suggestions(user_id, force_refresh=force_refresh)

        if not result.get('success'):
            return jsonify(result), 400

        # Deduct credits if AI was used (not from cache)
        if not result.get('cached', False):
            token_usage = result.get('token_usage', {})

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                from app.system.credits.credits_manager import CreditsManager
                credits_manager = CreditsManager()

                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description="X Content Suggestions Generation",
                    feature_id="x_content_suggestions",
                    provider_enum=token_usage.get('provider_enum')
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        # Ensure JSON-serializable response: convert AIProvider enum to string
        try:
            token_usage = result.get('token_usage', {})
            provider_enum = token_usage.get('provider_enum')
            if provider_enum is not None:
                # Preserve a readable provider name and replace enum with its value
                token_usage['provider_name'] = getattr(provider_enum, 'value', str(provider_enum))
                token_usage['provider_enum'] = getattr(provider_enum, 'value', str(provider_enum))
                result['token_usage'] = token_usage
        except Exception as conv_err:
            logger.warning(f"Failed to normalize provider_enum for JSON response: {conv_err}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error generating X content suggestions: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to generate suggestions. Please try again later."
        }), 500

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
                    logger.debug(f"User {user_id} already logged in today, streak: {current_streak}")
                    return current_streak

                # If logged in yesterday, increment streak
                if last_login == today - timedelta(days=1):
                    current_streak += 1
                    logger.debug(f"User {user_id} logged in consecutively, incremented streak to {current_streak}")
                # If more than 1 day gap, reset streak to 1
                elif last_login < today - timedelta(days=1):
                    current_streak = 1
                    logger.debug(f"User {user_id} broke streak, reset to 1 (last login: {last_login})")
                # This should never happen, but handle edge case
                else:
                    logger.warning(f"Unexpected date comparison for user {user_id}: last_login={last_login}, today={today}")
                    # Don't change streak in this unexpected case
                    pass

            except ValueError as e:
                # Invalid date format, start fresh
                logger.warning(f"Invalid date format for user {user_id}: {last_login_str}, error: {e}")
                current_streak = 1
        else:
            # First time login
            logger.debug(f"User {user_id} first time login, streak: 1")
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