from flask import Blueprint, render_template, redirect, url_for, request, flash, g, jsonify
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import UserService
from google.cloud import firestore
import firebase_admin
import logging
import threading
from datetime import datetime

# Setup logger
logger = logging.getLogger('accounts_routes')

# Create accounts blueprint
bp = Blueprint('accounts', __name__, url_prefix='/accounts')

@bp.route('/', methods=['GET'])
@auth_required
def index():
    """Render accounts connection page"""
    user_id = g.user.get('id')
    
    # Fetch user data from Firebase
    user_data = UserService.get_user(user_id)
    
    # Check if accounts are connected
    x_connected = bool(user_data.get('x_account', '')) if user_data else False
    youtube_connected = bool(user_data.get('youtube_account', '')) if user_data else False
    tiktok_connected = bool(user_data.get('tiktok_account', '')) if user_data else False
    
    # Get account usernames
    x_username = user_data.get('x_account', '') if user_data else ''
    youtube_channel = user_data.get('youtube_account', '') if user_data else ''
    tiktok_username = user_data.get('tiktok_account', '') if user_data else ''

    # Check setup completion status
    x_setup_complete = user_data.get('x_setup_complete', True) if user_data else True
    tiktok_setup_complete = user_data.get('tiktok_setup_complete', True) if user_data else True
    youtube_setup_complete = user_data.get('youtube_setup_complete', True) if user_data else True

    # Check if we need to show super powers modal
    show_super_powers = request.args.get('show_super_powers', 'false').lower() == 'true'

    return render_template(
        'accounts/index.html',
        x_connected=x_connected,
        youtube_connected=youtube_connected,
        tiktok_connected=tiktok_connected,
        x_username=x_username,
        youtube_channel=youtube_channel,
        tiktok_username=tiktok_username,
        x_setup_complete=x_setup_complete,
        tiktok_setup_complete=tiktok_setup_complete,
        youtube_setup_complete=youtube_setup_complete,
        show_super_powers=show_super_powers,
        user_data=user_data
    )

@bp.route('/connect', methods=['POST'])
@auth_required
def connect_account():
    """Connect a social media account"""
    user_id = g.user.get('id')
    platform = request.form.get('platform')
    
    if platform == 'x':
        username = request.form.get('x_username', '').strip()
        # Remove @ symbol if user included it
        username = username.lstrip('@')
        if not username:
            flash("Please enter your X username", "error")
            return redirect(url_for('accounts.index'))

        # Store X account in Firebase
        UserService.update_user(user_id, {'x_account': username})
        
        # Mark account as newly connected for initial fetch
        UserService.update_user(user_id, {
            'x_account': username,
            'x_connected_at': datetime.now().isoformat(),
            'x_setup_complete': False
        })
        
        # Start background process to fetch X analytics with 6 months of historical data
        try:
            from app.scripts.accounts.x_analytics import fetch_x_analytics

            def fetch_analytics_bg():
                try:
                    # Initial fetch with 6 months of historical data
                    logger.info(f"Starting initial X analytics fetch for user {user_id} with 6 months of data")
                    fetch_x_analytics(user_id, is_initial=True)
                    logger.info(f"Completed initial X analytics fetch for user {user_id}")
                except Exception as e:
                    import traceback
                    logger.error(f"Error fetching initial X analytics: {str(e)}")
                    logger.error(traceback.format_exc())

            bg_thread = threading.Thread(target=fetch_analytics_bg)
            bg_thread.daemon = True
            bg_thread.start()

        except Exception as e:
            import traceback
            logger.error(f"Error setting up X analytics: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Just redirect back without query params - modal will show via JavaScript
        flash(f"Successfully connected X account @{username}", "success")
        return redirect(url_for('accounts.index'))
        
    elif platform == 'tiktok':
        username = request.form.get('tiktok_username', '').strip()
        # Remove @ symbol if user included it
        username = username.lstrip('@')
        if not username:
            flash("Please enter your TikTok username", "error")
            return redirect(url_for('accounts.index'))

        # Store TikTok account in Firebase
        UserService.update_user(user_id, {
            'tiktok_account': username,
            'tiktok_setup_complete': False
        })

        # Start initial TikTok data fetch in background
        logger.info(f"Starting initial TikTok analytics fetch for user {user_id}")
        bg_thread = threading.Thread(target=fetch_initial_tiktok_data, args=(user_id, username))
        bg_thread.daemon = True
        bg_thread.start()

        # Just redirect back without query params - modal will show via JavaScript
        flash(f"Successfully connected TikTok account @{username}", "success")
        return redirect(url_for('accounts.index'))
        
    else:
        flash("Invalid platform specified", "error")
        return redirect(url_for('accounts.index'))

@bp.route('/fetch-x-replies', methods=['POST'])
@auth_required
def fetch_x_replies():
    """Manually fetch just X replies data"""
    user_id = g.user.get('id')

    try:
        from app.scripts.accounts.x_analytics import XAnalytics

        logger.info(f"Manually fetching X replies for user {user_id}")
        analytics = XAnalytics(user_id)

        # Fetch and store replies
        replies_data = analytics.get_replies_data()
        if replies_data:
            logger.info(f"Fetched {len(replies_data)} replies")
            analytics._store_replies(replies_data)
            flash(f"Successfully fetched {len(replies_data)} replies!", "success")
        else:
            logger.warning("No replies data fetched")
            flash("No replies found. Make sure you have replies on your X profile.", "warning")

        return redirect(url_for('accounts.index'))

    except Exception as e:
        logger.error(f"Error fetching X replies: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        flash("Error fetching replies. Please try again.", "error")
        return redirect(url_for('accounts.index'))

@bp.route('/connection-status')
@auth_required
def connection_status():
    """Check the status of account connection setup"""
    user_id = g.user.get('id')
    platform = request.args.get('platform')

    try:
        user_data = UserService.get_user(user_id)

        if platform == 'x':
            is_complete = user_data.get('x_setup_complete', False)
        elif platform == 'tiktok':
            is_complete = user_data.get('tiktok_setup_complete', False)
        elif platform == 'youtube':
            is_complete = user_data.get('youtube_setup_complete', False)
        else:
            return jsonify({'error': 'Invalid platform'}), 400

        return jsonify({
            'complete': is_complete,
            'platform': platform
        })

    except Exception as e:
        logger.error(f"Error checking connection status: {str(e)}")
        return jsonify({'error': 'Failed to check status'}), 500

@bp.route('/disconnect', methods=['POST'])
@auth_required
def disconnect_account():
    """Disconnect a social media account"""
    user_id = g.user.get('id')
    platform = request.form.get('platform')
    
    if platform == 'x':
        # Remove X account from Firebase
        UserService.update_user(user_id, {'x_account': ''})
        
        # Clean up X analytics data
        try:
            from app.scripts.accounts.x_analytics import clean_user_data
            
            def clean_data_bg():
                try:
                    clean_user_data(user_id)
                except Exception as e:
                    logger.error(f"Error cleaning X analytics data: {str(e)}")
            
            thread = threading.Thread(target=clean_data_bg)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Error cleaning X analytics data: {str(e)}")
        
        flash("Successfully disconnected X account", "success")
        
    elif platform == 'youtube':
        # Clean up YouTube analytics data first
        try:
            from app.scripts.accounts.youtube_analytics import clean_youtube_user_data
            clean_youtube_user_data(user_id)
        except Exception as e:
            logger.error(f"Error cleaning YouTube analytics data: {str(e)}")
        
        # Remove YouTube account from Firebase
        UserService.update_user(user_id, {
            'youtube_account': None,
            'youtube_credentials': None,
            'youtube_channel_id': None,
            'youtube_connected_at': None
        })
        
        flash("Successfully disconnected YouTube channel", "success")
        
    elif platform == 'tiktok':
        # Remove TikTok account from Firebase
        UserService.update_user(user_id, {
            'tiktok_account': '',
            'tiktok_sec_uid': ''
        })

        # Clean up TikTok analytics data
        try:
            def clean_tiktok_data():
                try:
                    logger.info(f"Cleaning TikTok analytics data for user {user_id}")

                    import firebase_admin
                    from firebase_admin import firestore

                    # Initialize Firestore if needed
                    if not firebase_admin._apps:
                        try:
                            firebase_admin.initialize_app()
                        except ValueError:
                            pass

                    db = firestore.client()

                    # Delete TikTok analytics documents
                    tiktok_collection = db.collection('users').document(user_id).collection('tiktok_analytics')

                    # Delete 'latest' document
                    latest_ref = tiktok_collection.document('latest')
                    if latest_ref.get().exists:
                        latest_ref.delete()
                        logger.info(f"Deleted TikTok 'latest' document for user {user_id}")

                    # Delete 'posts' document
                    posts_ref = tiktok_collection.document('posts')
                    if posts_ref.get().exists:
                        posts_ref.delete()
                        logger.info(f"Deleted TikTok 'posts' document for user {user_id}")

                    logger.info(f"Successfully cleaned TikTok analytics data for user {user_id}")

                except Exception as e:
                    logger.error(f"Error cleaning TikTok analytics data: {str(e)}")

            thread = threading.Thread(target=clean_tiktok_data)
            thread.daemon = True
            thread.start()

        except Exception as e:
            logger.error(f"Error starting TikTok cleanup thread: {str(e)}")

        flash("Successfully disconnected TikTok account", "success")
        
    else:
        flash("Invalid platform specified", "error")
    
    return redirect(url_for('accounts.index'))

# YouTube OAuth route
@bp.route('/connect/youtube', methods=['GET'])
@auth_required
def youtube_connect_redirect():
    """Redirect to YouTube OAuth flow"""
    return redirect(url_for('youtube.connect_youtube'))

# Data endpoints for dashboard/analytics display
@bp.route('/youtube/data', methods=['GET'])
@auth_required
def get_youtube_data():
    """Get YouTube analytics data for display"""
    user_id = g.user.get('id')
    
    user_data = UserService.get_user(user_id)
    if not user_data or not user_data.get('youtube_credentials'):
        return jsonify({'error': 'YouTube account not properly connected'}), 400
    
    try:
        # Initialize Firestore if needed
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        # Get analytics from subcollection
        analytics_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('metrics')
        analytics_doc = analytics_ref.get()
        
        if not analytics_doc.exists:
            return jsonify({'error': 'No YouTube analytics data available yet'}), 404
        
        analytics_data = analytics_doc.to_dict()
        return jsonify({'data': analytics_data})
        
    except Exception as e:
        logger.error(f"Error fetching YouTube analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics data'}), 500

# X analytics endpoints
@bp.route('/x/analytics', methods=['GET'])
@auth_required
def get_x_analytics():
    """Get X analytics metrics for display"""
    user_id = g.user.get('id')
    
    try:
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        analytics_ref = db.collection('users').document(user_id).collection('x_analytics').document('metrics')
        analytics_doc = analytics_ref.get()
        
        if not analytics_doc.exists:
            return jsonify({'error': 'No X analytics data available yet'}), 404
        
        analytics_data = analytics_doc.to_dict()
        return jsonify({'data': analytics_data})
        
    except Exception as e:
        logger.error(f"Error fetching X analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics data'}), 500

@bp.route('/x/posts', methods=['GET'])
@auth_required  
def get_x_posts():
    """Get X posts data for display"""
    user_id = g.user.get('id')
    
    try:
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        posts_ref = db.collection('users').document(user_id).collection('x_posts').document('timeline')
        posts_doc = posts_ref.get()
        
        if not posts_doc.exists:
            return jsonify({'error': 'No X posts data available yet'}), 404
        
        posts_data = posts_doc.to_dict()
        return jsonify({'data': posts_data})
        
    except Exception as e:
        logger.error(f"Error fetching X posts: {str(e)}")
        return jsonify({'error': 'Failed to fetch posts data'}), 500

def fetch_initial_tiktok_data(user_id, username):
    """Background function to fetch initial TikTok analytics data"""
    try:
        logger.info(f"Fetching initial TikTok data for user {user_id}, username: {username}")

        from app.system.services.tiktok_service import TikTokService
        import firebase_admin
        from firebase_admin import firestore
        from datetime import datetime, timedelta

        # Initialize Firestore if needed
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

        db = firestore.client()

        # Fetch user info
        user_info = TikTokService.get_user_info(username)

        if not user_info:
            logger.error(f"Failed to fetch TikTok user info for {username}")
            # Mark setup as complete (even though failed) so modal closes
            UserService.update_user(user_id, {'tiktok_setup_complete': True})
            return

        # Store secUid
        sec_uid = user_info.get('sec_uid')
        UserService.update_user(user_id, {'tiktok_sec_uid': sec_uid})

        # Fetch posts from last 6 months with pagination (like X Analytics)
        six_months_ago = datetime.now() - timedelta(days=180)
        all_posts = []
        cursor = "0"
        max_pages = 30  # Limit to prevent infinite loops
        page = 0

        logger.info(f"Starting pagination to fetch 6 months of TikTok posts for {username}")
        logger.info(f"Six months ago cutoff: {six_months_ago.strftime('%Y-%m-%d')}")

        while page < max_pages:
            page += 1
            logger.info(f"Fetching page {page} with cursor: {cursor}")

            # Retry logic for API calls
            posts_data = None
            max_retries = 3
            for retry in range(max_retries):
                posts_data = TikTokService.get_user_posts(sec_uid, count=35, cursor=cursor)

                if posts_data:
                    break

                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 5  # 5s, 10s, 15s
                    logger.warning(f"Failed to fetch page {page}, retrying in {wait_time}s (attempt {retry + 1}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch TikTok posts for {username} on page {page} after {max_retries} attempts")

            if not posts_data:
                break

            posts = posts_data.get('posts', [])
            logger.info(f"Page {page}: Got {len(posts)} posts from API")

            # Add all posts - TikTok API returns old videos first with cursor="0"
            # We need to go through ALL available cursors to reach recent videos
            # Then filter by date at the end
            all_posts.extend(posts)
            logger.info(f"Page {page}: Added {len(posts)} posts (total now: {len(all_posts)})")

            # Check if there are more pages
            has_more = posts_data.get('has_more', False)
            next_cursor = posts_data.get('cursor')

            if not has_more or not next_cursor:
                logger.info(f"No more pages available (has_more: {has_more}, cursor: {next_cursor})")
                break

            cursor = next_cursor
            logger.info(f"Page {page}: Has more pages, continuing with cursor: {cursor}")

            # Add delay between pages to avoid rate limiting
            import time
            time.sleep(2)

        logger.info(f"Completed pagination: Fetched {len(all_posts)} posts across {page} pages")

        # Filter posts to only include those from last 6 months
        posts_before_filter = len(all_posts)
        filtered_posts = []
        for post in all_posts:
            create_time = post.get('create_time')
            if create_time:
                try:
                    post_date = datetime.fromtimestamp(create_time)
                    if post_date >= six_months_ago:
                        filtered_posts.append(post)
                except Exception as e:
                    logger.error(f"Error parsing post date: {e}")
                    filtered_posts.append(post)
            else:
                filtered_posts.append(post)

        logger.info(f"Filtered posts: {posts_before_filter} total -> {len(filtered_posts)} within 6 months (removed {posts_before_filter - len(filtered_posts)} old posts)")
        all_posts = filtered_posts

        # Sort posts by date (most recent first) and take last 35 for metrics calculation
        posts_sorted = sorted(all_posts, key=lambda p: p.get('create_time', 0), reverse=True)
        last_35_posts = posts_sorted[:35]

        # Calculate metrics from last 35 posts only
        engagement_rate = 0
        total_views_35 = 0
        total_likes_35 = 0
        total_comments_35 = 0
        total_shares_35 = 0

        total_engagement_rate = 0
        posts_count = 0

        for post in last_35_posts:
            views = post.get('views', 0)
            likes = post.get('likes', 0)
            comments = post.get('comments', 0)
            shares = post.get('shares', 0)

            total_views_35 += views
            total_likes_35 += likes
            total_comments_35 += comments
            total_shares_35 += shares

            if views > 0:
                engagement = likes + comments + shares
                post_engagement_rate = (engagement / views) * 100
                total_engagement_rate += post_engagement_rate
                posts_count += 1

        if posts_count > 0:
            engagement_rate = total_engagement_rate / posts_count

        # Calculate engagement rate for all posts (for display in posts table)
        for post in all_posts:
            views = post.get('views', 0)
            likes = post.get('likes', 0)
            comments = post.get('comments', 0)
            shares = post.get('shares', 0)

            if views > 0:
                post['engagement_rate'] = ((likes + comments + shares) / views) * 100
            else:
                post['engagement_rate'] = 0

        # Add calculated metrics to user info
        user_info['engagement_rate'] = engagement_rate
        user_info['total_views_35'] = total_views_35
        user_info['total_likes_35'] = total_likes_35
        user_info['total_comments_35'] = total_comments_35
        user_info['total_shares_35'] = total_shares_35
        user_info['post_count'] = len(last_35_posts)
        user_info['fetched_at'] = datetime.now().isoformat()

        # Store overview data in Firestore
        tiktok_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('latest')
        tiktok_ref.set(user_info)

        # Store all posts data in Firestore
        posts_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('posts')
        posts_ref.set({
            'posts': all_posts,
            'has_more': False,  # We've fetched all available posts within 6 months
            'fetched_at': datetime.now().isoformat(),
            'total_posts': len(all_posts)
        })

        logger.info(f"Successfully fetched and stored {len(all_posts)} TikTok posts for user {user_id}")

        # Mark setup as complete
        UserService.update_user(user_id, {'tiktok_setup_complete': True})

    except Exception as e:
        logger.error(f"Error fetching initial TikTok data: {str(e)}", exc_info=True)
        # Mark setup as failed
        UserService.update_user(user_id, {'tiktok_setup_complete': False})