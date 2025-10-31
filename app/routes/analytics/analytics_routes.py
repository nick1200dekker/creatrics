from flask import render_template, g, jsonify, request
from app.routes.analytics import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.services.firebase_service import UserService
import firebase_admin
from firebase_admin import firestore
import logging
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger('analytics_routes')

# Cache for TikTok analytics data
tiktok_cache = {}

@bp.route('/analytics')
@auth_required
@require_permission('analytics')
def index():
    """Render the Analytics page"""
    user_id = get_workspace_user_id()

    # Fetch user data to check connected accounts
    user_data = UserService.get_user(user_id)

    x_connected = bool(user_data.get('x_account', '')) if user_data else False
    youtube_connected = bool(user_data.get('youtube_credentials', '')) if user_data else False
    tiktok_connected = bool(user_data.get('tiktok_account', '')) if user_data else False

    # Get platform from query parameter or default to first connected
    platform = request.args.get('platform')
    if not platform:
        if x_connected:
            platform = 'x'
        elif youtube_connected:
            platform = 'youtube'
        elif tiktok_connected:
            platform = 'tiktok'
        else:
            platform = None

    return render_template('analytics/index.html',
                         x_connected=x_connected,
                         youtube_connected=youtube_connected,
                         tiktok_connected=tiktok_connected,
                         current_platform=platform)

@bp.route('/analytics/x/overview')
@auth_required
@require_permission('analytics')
def x_overview():
    """Get X analytics overview data with timeframe support"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '6months')  # Default to 6 months
    
    try:
        # Initialize Firestore if needed
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get latest metrics
        latest_ref = db.collection('users').document(user_id).collection('x_analytics').document('latest')
        latest_doc = latest_ref.get()
        
        if not latest_doc.exists:
            logger.warning(f"No latest X analytics data for user {user_id}")
            return jsonify({'error': 'No X analytics data available'}), 404
        
        latest_data = latest_doc.to_dict()
        
        # Calculate timeframe-specific metrics
        timeframe_days = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '6months': 180
        }.get(timeframe, 180)
        
        # Get posts within timeframe for calculations
        posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        # Calculate metrics from posts within timeframe
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
        
        # Update metrics with timeframe-specific calculations
        if post_count > 0:
            latest_data['avg_views_per_post'] = total_views / post_count
            latest_data['timeframe_engagement_rate'] = (total_engagement / total_views * 100) if total_views > 0 else 0
        else:
            latest_data['avg_views_per_post'] = 0
            latest_data['timeframe_engagement_rate'] = 0
        
        latest_data['posts_in_timeframe'] = post_count
        latest_data['timeframe'] = timeframe
        
        # Get historical data for trends
        days_ago = timeframe_days
        start_date = datetime.now() - timedelta(days=days_ago)
        history_ref = db.collection('users').document(user_id).collection('x_analytics').document('history').collection('daily')
        
        # Get all historical documents
        history_docs = history_ref.stream()
        historical_data = []
        
        for doc in history_docs:
            data = doc.to_dict()
            # Parse date from document ID (YYYY-MM-DD format)
            try:
                doc_date = datetime.strptime(doc.id, '%Y-%m-%d')
                if doc_date >= start_date:
                    data['date'] = doc.id
                    historical_data.append(data)
            except:
                pass
        
        # Sort by date
        historical_data.sort(key=lambda x: x['date'])
        
        # Calculate trends
        trends = calculate_trends(historical_data)
        
        return jsonify({
            'current': latest_data,
            'historical': historical_data,
            'trends': trends
        })
        
    except Exception as e:
        logger.error(f"Error fetching X overview: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics data'}), 500

@bp.route('/analytics/x/impressions')
@auth_required
@require_permission('analytics')
def x_impressions():
    """Get X impressions data with daily values and 10-post rolling average"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '6months')
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        
        # Calculate timeframe
        timeframe_days = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '6months': 180
        }.get(timeframe, 180)
        
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        # Get all posts (not just in timeframe for rolling average calculation)
        posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
        
        # Collect all posts
        all_posts = []
        for doc in posts_collection.stream():
            post = doc.to_dict()
            if post.get('created_at_timestamp'):
                all_posts.append(post)
        
        # Sort posts by timestamp (oldest first for rolling calculation)
        all_posts.sort(key=lambda x: x.get('created_at_timestamp', 0))
        
        # Check if we have sufficient data for rolling averages (at least 10 posts total)
        has_sufficient_data = len(all_posts) >= 10
        
        # Calculate rolling averages for ALL posts first
        rolling_avg_by_timestamp = {}
        if has_sufficient_data:
            for i, post in enumerate(all_posts):
                # Get the last 10 posts including current (only when we have at least 10)
                if i >= 9:
                    start_idx = i - 9
                    window_posts = all_posts[start_idx:i+1]
                    
                    total_views = sum(p.get('views', 0) for p in window_posts)
                    avg_views = total_views / len(window_posts)
                    
                    # Store by timestamp for lookup
                    rolling_avg_by_timestamp[post.get('created_at_timestamp')] = avg_views
        
        # Determine grouping based on timeframe
        group_by_week = timeframe == '6months'
        
        # Create complete timeline from cutoff to now
        current_date = datetime.now().date()
        timeline_data = {}
        
        if group_by_week:
            # Generate weeks from cutoff to now
            current_week_start = current_date - timedelta(days=current_date.weekday())
            cutoff_week_start = cutoff_date.date() - timedelta(days=cutoff_date.weekday())
            
            week_start = cutoff_week_start
            while week_start <= current_week_start:
                week_key = week_start.strftime('%Y-%m-%d')
                timeline_data[week_key] = {
                    'total_views': 0,
                    'posts_count': 0,
                    'posts': [],
                    'week_end': (week_start + timedelta(days=6)).strftime('%Y-%m-%d')
                }
                week_start += timedelta(days=7)
        else:
            # Generate daily timeline from cutoff to now
            timeline_date = cutoff_date.date()
            while timeline_date <= current_date:
                date_key = timeline_date.strftime('%Y-%m-%d')
                timeline_data[date_key] = {
                    'total_views': 0,
                    'posts_count': 0,
                    'posts': []
                }
                timeline_date += timedelta(days=1)
        
        # Fill in actual post data
        for post in all_posts:
            timestamp = post.get('created_at_timestamp', 0)
            if timestamp >= cutoff_timestamp:
                post_date = datetime.fromtimestamp(timestamp)
                
                if group_by_week:
                    # Get start of week (Monday)
                    week_start = post_date - timedelta(days=post_date.weekday())
                    date_key = week_start.strftime('%Y-%m-%d')
                else:
                    date_key = post_date.strftime('%Y-%m-%d')
                
                if date_key in timeline_data:
                    timeline_data[date_key]['total_views'] += post.get('views', 0)
                    timeline_data[date_key]['posts_count'] += 1
                    timeline_data[date_key]['posts'].append(post)
        
        # Create rolling average timeline for the timeframe
        rolling_avg_timeline = {}
        if has_sufficient_data:
            # For each date in our timeline, find the most recent rolling average
            for date_key in sorted(timeline_data.keys()):
                if group_by_week:
                    # For weekly view, check all posts in that week
                    week_posts = timeline_data[date_key]['posts']
                    if week_posts:
                        # Use the rolling average from the most recent post in the week
                        latest_post = max(week_posts, key=lambda p: p.get('created_at_timestamp', 0))
                        latest_timestamp = latest_post.get('created_at_timestamp')
                        if latest_timestamp in rolling_avg_by_timestamp:
                            rolling_avg_timeline[date_key] = rolling_avg_by_timestamp[latest_timestamp]
                else:
                    # For daily view, find the latest rolling average up to this date
                    target_date = datetime.strptime(date_key, '%Y-%m-%d')
                    target_timestamp = target_date.timestamp()
                    
                    # Find the most recent rolling average before or on this date
                    latest_avg = None
                    for ts, avg in rolling_avg_by_timestamp.items():
                        if ts <= target_timestamp:
                            latest_avg = avg
                        else:
                            break
                    
                    if latest_avg is not None:
                        rolling_avg_timeline[date_key] = latest_avg
        
        # Convert to sorted list
        impressions_data = []
        for date in sorted(timeline_data.keys()):
            day_data = timeline_data[date]
            
            impressions_data.append({
                'date': date,
                'daily_impressions': day_data['total_views'],
                'posts_count': day_data['posts_count'],
                'rolling_avg': rolling_avg_timeline.get(date),
                'is_week': group_by_week,
                'week_end': day_data.get('week_end') if group_by_week else None
            })
        
        logger.info(f"Returning impressions data: {len(impressions_data)} {'weeks' if group_by_week else 'days'}, {len(all_posts)} total posts, rolling avg available: {has_sufficient_data}")
        
        return jsonify({
            'impressions_data': impressions_data,
            'has_sufficient_data': has_sufficient_data,
            'timeframe': timeframe,
            'total_posts': len(all_posts),
            'grouped_by': 'week' if group_by_week else 'day'
        })
        
    except Exception as e:
        logger.error(f"Error fetching impressions data: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to fetch impressions data'}), 500

@bp.route('/analytics/x/engagement')
@auth_required
@require_permission('analytics')
def x_engagement():
    """Get X engagement data with daily values and 10-post rolling average"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '6months')
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        
        # Calculate timeframe
        timeframe_days = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '6months': 180
        }.get(timeframe, 180)
        
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        # Get all posts (not just in timeframe for rolling average calculation)
        posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
        
        # Collect all posts
        all_posts = []
        for doc in posts_collection.stream():
            post = doc.to_dict()
            if post.get('created_at_timestamp'):
                all_posts.append(post)
        
        # Sort posts by timestamp (oldest first for rolling calculation)
        all_posts.sort(key=lambda x: x.get('created_at_timestamp', 0))
        
        # Check if we have sufficient data for rolling averages
        has_sufficient_data = len(all_posts) >= 10
        
        # Calculate rolling engagement rates for ALL posts first
        rolling_engagement_by_timestamp = {}
        if has_sufficient_data:
            for i, post in enumerate(all_posts):
                # Get the last 10 posts including current (only when we have at least 10)
                if i >= 9:
                    start_idx = i - 9
                    window_posts = all_posts[start_idx:i+1]
                    
                    total_views = sum(p.get('views', 0) for p in window_posts)
                    total_engagement = sum(
                        p.get('likes', 0) + p.get('retweets', 0) + 
                        p.get('replies', 0) + p.get('bookmarks', 0) 
                        for p in window_posts
                    )
                    
                    if total_views > 0:
                        engagement_rate = (total_engagement / total_views) * 100
                        rolling_engagement_by_timestamp[post.get('created_at_timestamp')] = engagement_rate
        
        # Determine grouping based on timeframe
        group_by_week = timeframe == '6months'
        
        # Create complete timeline from cutoff to now
        current_date = datetime.now().date()
        timeline_data = {}
        
        if group_by_week:
            # Generate weeks from cutoff to now
            current_week_start = current_date - timedelta(days=current_date.weekday())
            cutoff_week_start = cutoff_date.date() - timedelta(days=cutoff_date.weekday())
            
            week_start = cutoff_week_start
            while week_start <= current_week_start:
                week_key = week_start.strftime('%Y-%m-%d')
                timeline_data[week_key] = {
                    'total_views': 0,
                    'total_engagement': 0,
                    'posts_count': 0,
                    'posts': [],
                    'week_end': (week_start + timedelta(days=6)).strftime('%Y-%m-%d')
                }
                week_start += timedelta(days=7)
        else:
            # Generate daily timeline from cutoff to now
            timeline_date = cutoff_date.date()
            while timeline_date <= current_date:
                date_key = timeline_date.strftime('%Y-%m-%d')
                timeline_data[date_key] = {
                    'total_views': 0,
                    'total_engagement': 0,
                    'posts_count': 0,
                    'posts': []
                }
                timeline_date += timedelta(days=1)
        
        # Fill in actual post data
        for post in all_posts:
            timestamp = post.get('created_at_timestamp', 0)
            if timestamp >= cutoff_timestamp:
                post_date = datetime.fromtimestamp(timestamp)
                
                if group_by_week:
                    # Get start of week (Monday)
                    week_start = post_date - timedelta(days=post_date.weekday())
                    date_key = week_start.strftime('%Y-%m-%d')
                else:
                    date_key = post_date.strftime('%Y-%m-%d')
                
                if date_key in timeline_data:
                    views = post.get('views', 0)
                    engagement = (post.get('likes', 0) + 
                                post.get('retweets', 0) + 
                                post.get('replies', 0) + 
                                post.get('bookmarks', 0))
                    
                    timeline_data[date_key]['total_views'] += views
                    timeline_data[date_key]['total_engagement'] += engagement
                    timeline_data[date_key]['posts_count'] += 1
                    timeline_data[date_key]['posts'].append(post)
        
        # Create rolling engagement rate timeline for the timeframe
        rolling_engagement_timeline = {}
        if has_sufficient_data:
            # For each date in our timeline, find the most recent rolling engagement rate
            for date_key in sorted(timeline_data.keys()):
                if group_by_week:
                    # For weekly view, check all posts in that week
                    week_posts = timeline_data[date_key]['posts']
                    if week_posts:
                        # Use the rolling engagement from the most recent post in the week
                        latest_post = max(week_posts, key=lambda p: p.get('created_at_timestamp', 0))
                        latest_timestamp = latest_post.get('created_at_timestamp')
                        if latest_timestamp in rolling_engagement_by_timestamp:
                            rolling_engagement_timeline[date_key] = rolling_engagement_by_timestamp[latest_timestamp]
                else:
                    # For daily view, find the latest rolling engagement up to this date
                    target_date = datetime.strptime(date_key, '%Y-%m-%d')
                    target_timestamp = target_date.timestamp()
                    
                    # Find the most recent rolling engagement before or on this date
                    latest_rate = None
                    for ts, rate in rolling_engagement_by_timestamp.items():
                        if ts <= target_timestamp:
                            latest_rate = rate
                        else:
                            break
                    
                    if latest_rate is not None:
                        rolling_engagement_timeline[date_key] = latest_rate
        
        # Convert to sorted list
        engagement_data = []
        for date in sorted(timeline_data.keys()):
            day_data = timeline_data[date]
            
            # Daily/weekly engagement rate
            engagement_rate = 0
            if day_data['total_views'] > 0:
                engagement_rate = (day_data['total_engagement'] / day_data['total_views']) * 100
            
            engagement_data.append({
                'date': date,
                'engagement_rate': engagement_rate,
                'total_engagement': day_data['total_engagement'],
                'rolling_engagement_rate': rolling_engagement_timeline.get(date),
                'is_week': group_by_week,
                'week_end': day_data.get('week_end') if group_by_week else None
            })
        
        logger.info(f"Returning engagement data: {len(engagement_data)} {'weeks' if group_by_week else 'days'}, {len(all_posts)} total posts, rolling avg available: {has_sufficient_data}")
        
        return jsonify({
            'engagement_data': engagement_data,
            'has_sufficient_data': has_sufficient_data,
            'timeframe': timeframe,
            'total_posts': len(all_posts),
            'grouped_by': 'week' if group_by_week else 'day'
        })
        
    except Exception as e:
        logger.error(f"Error fetching engagement data: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to fetch engagement data'}), 500

@bp.route('/analytics/x/posts-count')
@auth_required
@require_permission('analytics')
def x_posts_count():
    """Get daily posts count from posts (weekly for 6 months)"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '6months')
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        
        # Calculate timeframe
        timeframe_days = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '6months': 180
        }.get(timeframe, 180)
        
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        # Get individual posts to count by date
        posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
        
        # Determine if we should group by week
        group_by_week = timeframe == '6months'
        
        # Create complete timeline from cutoff to now
        current_date = datetime.now().date()
        timeline_data = {}
        
        if group_by_week:
            # Generate weeks from cutoff to now
            current_week_start = current_date - timedelta(days=current_date.weekday())
            cutoff_week_start = cutoff_date.date() - timedelta(days=cutoff_date.weekday())
            
            week_start = cutoff_week_start
            while week_start <= current_week_start:
                week_key = week_start.strftime('%Y-%m-%d')
                timeline_data[week_key] = 0
                week_start += timedelta(days=7)
        else:
            # Generate daily timeline from cutoff to now
            timeline_date = cutoff_date.date()
            while timeline_date <= current_date:
                date_key = timeline_date.strftime('%Y-%m-%d')
                timeline_data[date_key] = 0
                timeline_date += timedelta(days=1)
        
        # Count posts by date
        for doc in posts_collection.stream():
            post = doc.to_dict()
            timestamp = post.get('created_at_timestamp', 0)
            
            if timestamp >= cutoff_timestamp:
                post_date = datetime.fromtimestamp(timestamp)
                
                if group_by_week:
                    # Get start of week (Monday)
                    week_start = post_date - timedelta(days=post_date.weekday())
                    date_key = week_start.strftime('%Y-%m-%d')
                else:
                    date_key = post_date.strftime('%Y-%m-%d')
                
                if date_key in timeline_data:
                    timeline_data[date_key] += 1
        
        # Convert to sorted list
        posts_count_data = []
        for date in sorted(timeline_data.keys()):
            posts_count_data.append({
                'date': date,
                'posts_count': timeline_data[date],
                'is_week': group_by_week
            })
        
        logger.info(f"Returning {len(posts_count_data)} {'weeks' if group_by_week else 'days'} of posts count data")
        
        return jsonify({
            'posts_count_data': posts_count_data,
            'timeframe': timeframe,
            'grouped_by': 'week' if group_by_week else 'day'
        })
        
    except Exception as e:
        logger.error(f"Error fetching posts count data: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to fetch posts count data'}), 500

@bp.route('/analytics/x/followers-history')
@auth_required
@require_permission('analytics')
def x_followers_history():
    """Get followers history (simplified to just followers count)"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '6months')
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        
        # Calculate timeframe
        timeframe_days = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '6months': 180
        }.get(timeframe, 180)
        
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        
        # Get historical data from history/daily collection
        history_ref = db.collection('users').document(user_id).collection('x_analytics').document('history').collection('daily')
        
        # Get all documents
        daily_data = []
        history_docs = history_ref.stream()
        
        for doc in history_docs:
            try:
                # Parse date from document ID (YYYY-MM-DD format)
                doc_date = datetime.strptime(doc.id, '%Y-%m-%d')
                if doc_date >= cutoff_date:
                    data = doc.to_dict()
                    data['date'] = doc.id
                    data['doc_date'] = doc_date
                    daily_data.append(data)
            except Exception as e:
                logger.debug(f"Error parsing date {doc.id}: {e}")
        
        # Sort by date
        daily_data.sort(key=lambda x: x['date'])
        
        # Create complete timeline from cutoff to now (extend to current date)
        current_date = datetime.now().date()
        timeline_data = {}
        
        # Determine if we should group by week
        group_by_week = timeframe == '6months'
        
        if group_by_week:
            # Generate weeks from cutoff to now
            current_week_start = current_date - timedelta(days=current_date.weekday())
            cutoff_week_start = cutoff_date.date() - timedelta(days=cutoff_date.weekday())
            
            week_start = cutoff_week_start
            while week_start <= current_week_start:
                week_key = week_start.strftime('%Y-%m-%d')
                timeline_data[week_key] = {'followers_counts': [], 'week_start': week_start}
                week_start += timedelta(days=7)
            
            # Fill in actual data
            for data in daily_data:
                doc_date = data['doc_date']
                week_start = doc_date - timedelta(days=doc_date.weekday())
                week_key = week_start.strftime('%Y-%m-%d')
                
                if week_key in timeline_data:
                    timeline_data[week_key]['followers_counts'].append(data.get('followers_count', 0))
            
            # Calculate weekly averages and extend missing data
            followers_data = []
            last_known_count = None
            
            for week_key in sorted(timeline_data.keys()):
                week_info = timeline_data[week_key]
                
                if week_info['followers_counts']:
                    # Use the latest followers count in the week
                    followers_count = week_info['followers_counts'][-1]
                    last_known_count = followers_count
                else:
                    # Use last known count if no data for this week
                    followers_count = last_known_count or 0
                
                followers_data.append({
                    'date': week_key,
                    'followers_count': followers_count,
                    'is_week': True
                })
        else:
            # Generate daily timeline from cutoff to now
            timeline_date = cutoff_date.date()
            while timeline_date <= current_date:
                date_key = timeline_date.strftime('%Y-%m-%d')
                timeline_data[date_key] = None
                timeline_date += timedelta(days=1)
            
            # Fill in actual data
            for data in daily_data:
                date_key = data['date']
                if date_key in timeline_data:
                    timeline_data[date_key] = data.get('followers_count', 0)
            
            # Extend missing data and convert to list
            followers_data = []
            last_known_count = None
            
            for date_key in sorted(timeline_data.keys()):
                followers_count = timeline_data[date_key]
                
                if followers_count is not None:
                    last_known_count = followers_count
                else:
                    # Use last known count if no data for this date
                    followers_count = last_known_count or 0
                
                followers_data.append({
                    'date': date_key,
                    'followers_count': followers_count,
                    'is_week': False
                })
        
        # Check if we have sufficient data
        has_sufficient_data = len(daily_data) >= 7  # Reduced requirement for followers
        
        logger.info(f"Returning {len(followers_data)} {'weeks' if group_by_week else 'days'} of followers data")
        
        return jsonify({
            'followers_data': followers_data,
            'has_sufficient_data': has_sufficient_data,
            'timeframe': timeframe,
            'grouped_by': 'week' if group_by_week else 'day'
        })
        
    except Exception as e:
        logger.error(f"Error fetching followers history: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to fetch followers data'}), 500

@bp.route('/analytics/x/posts-paginated')
@auth_required
@require_permission('analytics')
def x_posts_paginated():
    """Get X posts data with pagination"""
    user_id = get_workspace_user_id()
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 12))  # Changed to 12 per page
    filter_type = request.args.get('filter', 'all')
    
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        
        # Get all posts from individual posts collection
        posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
        
        # Get all posts
        all_posts = []
        posts_docs = posts_collection.stream()
        
        for doc in posts_docs:
            post = doc.to_dict()
            
            # Calculate engagement rate for each post
            views = post.get('views', 0)
            engagement = post.get('likes', 0) + post.get('retweets', 0) + post.get('replies', 0) + post.get('bookmarks', 0)
            
            if views > 0:
                post['engagement_rate'] = (engagement / views) * 100
            else:
                post['engagement_rate'] = 0
            
            post['total_engagement'] = engagement
            all_posts.append(post)
        
        # Apply filtering
        if filter_type == 'views':
            # Sort by views (highest first)
            all_posts.sort(key=lambda x: x.get('views', 0), reverse=True)
        elif filter_type == 'engagement':
            # Filter posts with meaningful views and sort by engagement rate
            filtered_posts = [p for p in all_posts if p.get('views', 0) > 100]
            filtered_posts.sort(key=lambda x: x.get('engagement_rate', 0), reverse=True)
            all_posts = filtered_posts
        else:
            # Default: all posts sorted by date (most recent first)
            all_posts.sort(key=lambda x: x.get('created_at_timestamp', 0), reverse=True)
        
        # Calculate pagination
        total_posts = len(all_posts)
        total_pages = (total_posts + per_page - 1) // per_page
        
        # Get posts for current page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_posts = all_posts[start_idx:end_idx]
        
        return jsonify({
            'posts': page_posts,
            'total_posts': total_posts,
            'total_pages': total_pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error fetching X posts: {str(e)}")
        return jsonify({'error': 'Failed to fetch posts data'}), 500

@bp.route('/analytics/youtube/overview')
@auth_required
@require_permission('analytics')
def youtube_overview():
    """Get YouTube analytics overview data with 30-day authorization verification"""
    user_id = get_workspace_user_id()

    try:
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass

        db = firestore.client()

        # Get latest metrics
        latest_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
        latest_doc = latest_ref.get()

        if not latest_doc.exists:
            return jsonify({'error': 'No YouTube analytics data available'}), 404

        latest_data = latest_doc.to_dict()

        # Calculate data age for compliance display
        data_age_info = calculate_data_age(latest_data)

        # COMPLIANCE CHECK (Policy III.E.4.b): Verify authorization every 30 days
        # If data is >= 30 days old, MUST verify token is still valid before displaying
        if data_age_info['age_days'] is not None and data_age_info['age_days'] >= 30:
            logger.info(f"Data is {data_age_info['age_days']} days old - verifying authorization for user {user_id}")

            # Verify authorization by attempting to refresh credentials
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            try:
                yt = YouTubeAnalytics(user_id)
                if not yt.credentials:
                    logger.warning(f"No valid credentials found for user {user_id} - data is stale")
                    return jsonify({
                        'error': 'YouTube authorization expired. Please reconnect your account.',
                        'needs_reconnect': True
                    }), 401

                # Test if token is valid by refreshing if needed
                if yt.credentials.expired and yt.credentials.refresh_token:
                    yt._refresh_credentials()
                    logger.info(f"Successfully verified authorization for user {user_id}")
                elif yt.credentials.expired:
                    logger.warning(f"Token expired and no refresh token for user {user_id}")
                    return jsonify({
                        'error': 'YouTube authorization expired. Please reconnect your account.',
                        'needs_reconnect': True
                    }), 401

            except Exception as e:
                logger.error(f"Authorization verification failed for user {user_id}: {str(e)}")
                return jsonify({
                    'error': 'YouTube authorization expired. Please reconnect your account.',
                    'needs_reconnect': True
                }), 401

        # Get historical data for trends (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        history_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('history').collection('daily')

        # Get all historical documents
        history_docs = history_ref.stream()
        historical_data = []

        for doc in history_docs:
            data = doc.to_dict()
            # Parse date from document ID (YYYY-MM-DD format)
            try:
                doc_date = datetime.strptime(doc.id, '%Y-%m-%d')
                if doc_date >= thirty_days_ago:
                    data['date'] = doc.id
                    historical_data.append(data)
            except:
                pass

        # Sort by date
        historical_data.sort(key=lambda x: x['date'])

        return jsonify({
            'current': latest_data,
            'historical': historical_data,
            'data_age': data_age_info  # Compliance: Show data age
        })

    except Exception as e:
        logger.error(f"Error fetching YouTube overview: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics data'}), 500

@bp.route('/analytics/youtube/daily-views')
@auth_required
@require_permission('analytics')
def youtube_daily_views():
    """Get YouTube daily views data with timeframe support"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '30days')

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        db = firestore.client()

        # Get latest data which includes daily_data
        latest_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
        latest_doc = latest_ref.get()

        if not latest_doc.exists:
            return jsonify({'error': 'No YouTube analytics data available'}), 404

        latest_data = latest_doc.to_dict()

        # COMPLIANCE CHECK: Verify authorization if data >= 30 days old
        data_age_info = calculate_data_age(latest_data)
        if data_age_info['age_days'] is not None and data_age_info['age_days'] >= 30:
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            try:
                yt = YouTubeAnalytics(user_id)
                if not yt.credentials or (yt.credentials.expired and not yt.credentials.refresh_token):
                    return jsonify({'error': 'YouTube authorization expired', 'needs_reconnect': True}), 401
                if yt.credentials.expired:
                    yt._refresh_credentials()
            except Exception:
                return jsonify({'error': 'YouTube authorization expired', 'needs_reconnect': True}), 401
        daily_data = latest_data.get('daily_data', [])
        
        if not daily_data:
            return jsonify({'error': 'No daily data available'}), 404
        
        # Filter by timeframe
        timeframe_days = {
            '7days': 7,
            '30days': 30,
            '90days': 90,
            '6months': 180,
            '1year': 365
        }.get(timeframe, 30)
        
        cutoff_date = datetime.now() - timedelta(days=timeframe_days)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        
        filtered_data = [
            day for day in daily_data 
            if day.get('date', '') >= cutoff_date_str
        ]
        
        # Sort by date
        filtered_data.sort(key=lambda x: x.get('date', ''))
        
        # Calculate overview metrics from filtered daily data
        total_views = sum(day.get('views', 0) for day in filtered_data)
        total_watch_time_minutes = sum(day.get('watch_time_minutes', 0) for day in filtered_data)
        total_watch_time_hours = round(total_watch_time_minutes / 60, 2) if total_watch_time_minutes > 0 else 0
        total_subscribers_gained = sum(day.get('subscribers_gained', 0) for day in filtered_data)
        
        # Calculate averages
        num_days = len(filtered_data) if filtered_data else 1
        avg_daily_views = round(total_views / num_days, 1) if num_days > 0 else 0
        avg_daily_watch_time = round(total_watch_time_minutes / num_days, 1) if num_days > 0 else 0
        
        # Calculate average view duration from daily data
        total_watch_time_seconds = total_watch_time_minutes * 60
        avg_view_duration_seconds = round(total_watch_time_seconds / total_views) if total_views > 0 else 0
        
        # Get traffic sources from timeframe-specific data
        latest_data = latest_doc.to_dict()
        traffic_sources_by_timeframe = latest_data.get('traffic_sources_by_timeframe', {})
        
        # Get traffic sources for the requested timeframe
        timeframe_traffic_sources = traffic_sources_by_timeframe.get(timeframe, [])
        
        calculated_metrics = {
            'views': total_views,
            'watch_time_minutes': total_watch_time_minutes,
            'watch_time_hours': total_watch_time_hours,
            'subscribers_gained': total_subscribers_gained,
            'avg_daily_views': avg_daily_views,
            'avg_daily_watch_time': avg_daily_watch_time,
            'avg_view_duration_seconds': avg_view_duration_seconds,
            'traffic_sources': timeframe_traffic_sources,
            'timeframe': timeframe,
            'date_range': f"Last {timeframe_days} days" if timeframe_days < 365 else "Last year"
        }
        
        return jsonify({
            'daily_data': filtered_data,
            'calculated_metrics': calculated_metrics,
            'timeframe': timeframe
        })
        
    except Exception as e:
        logger.error(f"Error fetching YouTube daily views: {str(e)}")
        return jsonify({'error': 'Failed to fetch daily views data'}), 500

@bp.route('/analytics/x/refresh', methods=['POST'])
@auth_required
@require_permission('analytics')
def refresh_x_data():
    """Manually refresh X analytics data"""
    user_id = get_workspace_user_id()
    
    try:
        # Import the X analytics function
        from app.scripts.accounts.x_analytics import fetch_x_analytics
        
        logger.info(f"Manual X analytics refresh requested for user {user_id}")

        # Fetch fresh data (is_initial=False to only fetch last 7 days)
        result = fetch_x_analytics(user_id, is_initial=False)
        
        if result:
            logger.info(f"X analytics refresh completed successfully for user {user_id}")
            return jsonify({
                'success': True,
                'message': 'X analytics data refreshed successfully',
                'timestamp': result.get('timestamp')
            })
        else:
            logger.error(f"X analytics refresh failed for user {user_id}")
            return jsonify({
                'success': False,
                'error': 'Failed to refresh X analytics data'
            }), 500
            
    except Exception as e:
        logger.error(f"Error refreshing X analytics for user {user_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh analytics data'
        }), 500

@bp.route('/analytics/youtube/refresh', methods=['POST'])
@auth_required
@require_permission('analytics')
def refresh_youtube_data():
    """Manually refresh YouTube analytics data"""
    user_id = get_workspace_user_id()

    try:
        # Import the YouTube analytics function
        from app.scripts.accounts.youtube_analytics import fetch_youtube_analytics

        logger.info(f"Manual YouTube analytics refresh requested for user {user_id}")

        # Force refresh (bypass 30-day cache check for manual refresh)
        result = fetch_youtube_analytics(user_id, force_refresh=True)

        if result:
            logger.info(f"YouTube analytics refresh completed successfully for user {user_id}")
            return jsonify({
                'success': True,
                'message': 'YouTube analytics data refreshed successfully',
                'timestamp': result.get('data_fetched_at')
            })
        else:
            logger.error(f"YouTube analytics refresh failed for user {user_id}")
            return jsonify({
                'success': False,
                'error': 'Failed to refresh YouTube analytics data. Your YouTube connection may have expired. Please reconnect your account in Settings.',
                'needs_reconnect': True
            }), 401

    except Exception as e:
        logger.error(f"Error refreshing YouTube analytics for user {user_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh analytics data'
        }), 500

@bp.route('/analytics/youtube/top-videos')
@auth_required
@require_permission('analytics')
def youtube_top_videos():
    """Get YouTube top videos for specific timeframe"""
    user_id = get_workspace_user_id()
    timeframe = request.args.get('timeframe', '30days')

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        db = firestore.client()

        # Get latest data which includes top_videos_by_timeframe
        latest_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
        latest_doc = latest_ref.get()

        if not latest_doc.exists:
            return jsonify({'error': 'No YouTube analytics data available'}), 404

        latest_data = latest_doc.to_dict()

        # COMPLIANCE CHECK: Verify authorization if data >= 30 days old
        data_age_info = calculate_data_age(latest_data)
        if data_age_info['age_days'] is not None and data_age_info['age_days'] >= 30:
            from app.scripts.accounts.youtube_analytics import YouTubeAnalytics
            try:
                yt = YouTubeAnalytics(user_id)
                if not yt.credentials or (yt.credentials.expired and not yt.credentials.refresh_token):
                    return jsonify({'error': 'YouTube authorization expired', 'needs_reconnect': True}), 401
                if yt.credentials.expired:
                    yt._refresh_credentials()
            except Exception:
                return jsonify({'error': 'YouTube authorization expired', 'needs_reconnect': True}), 401
        top_videos_by_timeframe = latest_data.get('top_videos_by_timeframe', {})
        
        # Get videos for the requested timeframe
        videos = top_videos_by_timeframe.get(timeframe, [])
        
        return jsonify({
            'top_videos': videos,
            'timeframe': timeframe
        })
        
    except Exception as e:
        logger.error(f"Error fetching YouTube top videos: {str(e)}")
        return jsonify({'error': 'Failed to fetch top videos data'}), 500

@bp.route('/analytics/tiktok/overview')
@auth_required
@require_permission('analytics')
def tiktok_overview():
    """Get TikTok analytics overview data - ONLY returns cached data, never fetches from API"""
    user_id = get_workspace_user_id()

    try:
        # Initialize Firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        db = firestore.client()

        # Get cached data from Firestore
        tiktok_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('latest')
        tiktok_doc = tiktok_ref.get()

        if tiktok_doc.exists:
            cached_data = tiktok_doc.to_dict()
            logger.info(f"Returning cached TikTok data for user {user_id}")
            return jsonify({'current': cached_data})

        # No cached data available - user needs to wait for cronjob or use refresh button
        logger.warning(f"No cached TikTok overview found for user {user_id}")
        return jsonify({
            'error': 'No TikTok analytics data available yet. Please use the refresh button or wait for automatic sync.'
        }), 404

    except Exception as e:
        logger.error(f"Error fetching TikTok overview: {str(e)}")
        return jsonify({'error': 'Failed to fetch TikTok analytics data'}), 500

@bp.route('/analytics/tiktok/posts')
@auth_required
@require_permission('analytics')
def tiktok_posts():
    """Get TikTok posts data - ONLY returns cached data, never fetches from API"""
    user_id = get_workspace_user_id()

    try:
        # Initialize Firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        db = firestore.client()

        # Get cached posts from Firestore
        posts_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('posts')
        posts_doc = posts_ref.get()

        if posts_doc.exists:
            cached_data = posts_doc.to_dict()
            logger.info(f"Returning cached TikTok posts for user {user_id}")
            return jsonify({
                'posts': cached_data.get('posts', []),
                'has_more': cached_data.get('has_more', False)
            })

        # No cached data available - user needs to wait for cronjob or use refresh button
        logger.warning(f"No cached TikTok posts found for user {user_id}")
        return jsonify({
            'error': 'No TikTok posts data available yet. Please use the refresh button or wait for automatic sync.',
            'posts': [],
            'has_more': False
        }), 404

    except Exception as e:
        logger.error(f"Error fetching TikTok posts: {str(e)}")
        return jsonify({'error': 'Failed to fetch TikTok posts'}), 500

@bp.route('/analytics/tiktok/refresh', methods=['POST'])
@auth_required
@require_permission('analytics')
def refresh_tiktok_data():
    """Manually refresh TikTok analytics data"""
    user_id = get_workspace_user_id()

    try:
        user_data = UserService.get_user(user_id)
        tiktok_username = user_data.get('tiktok_account', '')

        if not tiktok_username:
            return jsonify({'error': 'No TikTok account connected'}), 404

        logger.info(f"Manual TikTok analytics refresh requested for user {user_id}")

        # Import the TikTok analytics function
        from app.scripts.accounts.tiktok_analytics import fetch_tiktok_analytics

        # Call the fetch function
        try:
            fetch_tiktok_analytics(user_id)

            return jsonify({
                'success': True,
                'message': 'TikTok analytics data refreshed successfully',
                'timestamp': datetime.now().isoformat()
            })

        except Exception as fetch_error:
            logger.warning(f"TikTok API error during refresh for user {user_id}: {str(fetch_error)}")

            # Try to return cached data if API fails
            import firebase_admin
            from firebase_admin import firestore

            if not firebase_admin._apps:
                try:
                    firebase_admin.initialize_app()
                except ValueError:
                    pass

            db = firestore.client()
            tiktok_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('latest')
            tiktok_doc = tiktok_ref.get()

            if tiktok_doc.exists:
                cached_data = tiktok_doc.to_dict()
                return jsonify({
                    'success': True,
                    'message': 'TikTok API temporarily unavailable, showing cached data',
                    'cached': True,
                    'timestamp': cached_data.get('fetched_at')
                })

            return jsonify({
                'success': False,
                'error': 'TikTok API is temporarily unavailable. Please try again later.'
            }), 503

    except Exception as e:
        logger.error(f"Error refreshing TikTok analytics for user {user_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to refresh analytics data'
        }), 500

def calculate_data_age(data):
    """
    Calculate data age for YouTube policy compliance
    Policy III.E.4.f requires displaying data age context

    Returns dict with age info and warning levels
    """
    fetched_at = data.get('data_fetched_at')

    if not fetched_at:
        return {
            'age_days': None,
            'age_text': 'Unknown',
            'warning_level': 'error',
            'needs_refresh': True
        }

    try:
        fetched_time = datetime.fromisoformat(fetched_at)
        age = datetime.now() - fetched_time
        age_days = age.days
        age_hours = age.seconds // 3600

        # Format age text
        if age_days == 0:
            if age_hours == 0:
                age_text = 'Just now'
            elif age_hours == 1:
                age_text = '1 hour ago'
            else:
                age_text = f'{age_hours} hours ago'
        elif age_days == 1:
            age_text = '1 day ago'
        else:
            age_text = f'{age_days} days ago'

        # Determine warning level based on age
        if age_days >= 30:
            warning_level = 'critical'  # Red - must refresh
        elif age_days >= 7:
            warning_level = 'warning'   # Yellow - should refresh
        elif age_days >= 1:
            warning_level = 'info'      # Neutral
        else:
            warning_level = 'success'   # Green - fresh

        return {
            'age_days': age_days,
            'age_hours': age_hours,
            'age_text': age_text,
            'fetched_at': fetched_at,
            'warning_level': warning_level,
            'needs_refresh': age_days >= 30
        }

    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing data age: {e}")
        return {
            'age_days': None,
            'age_text': 'Unknown',
            'warning_level': 'error',
            'needs_refresh': True
        }

def calculate_trends(historical_data):
    """Calculate trends from historical data"""
    if len(historical_data) < 2:
        return {
            'followers_trend': 0,
            'engagement_trend': 0,
            'views_trend': 0
        }
    
    # Get data from 7 days ago and today
    seven_days_ago = None
    today = None
    
    for data in historical_data[-8:]:  # Last 8 days of data
        if seven_days_ago is None:
            seven_days_ago = data
        today = data
    
    if not seven_days_ago or not today:
        return {
            'followers_trend': 0,
            'engagement_trend': 0,
            'views_trend': 0
        }
    
    # Calculate percentage changes
    def calc_percentage_change(old_val, new_val):
        if old_val == 0:
            return 100 if new_val > 0 else 0
        return ((new_val - old_val) / old_val) * 100
    
    return {
        'followers_trend': calc_percentage_change(
            seven_days_ago.get('followers_count', 0),
            today.get('followers_count', 0)
        ),
        'engagement_trend': calc_percentage_change(
            seven_days_ago.get('rolling_avg_engagement', 0),
            today.get('rolling_avg_engagement', 0)
        ),
        'views_trend': calc_percentage_change(
            seven_days_ago.get('rolling_avg_views', 0),
            today.get('rolling_avg_views', 0)
        )
    }