from flask import Blueprint, render_template, redirect, url_for, request, flash, g, jsonify
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import UserService
from app.scripts.instagram_upload_studio.latedev_oauth_service import LateDevOAuthService
from google.cloud import firestore
import firebase_admin
import logging
import threading
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger('accounts_routes')

# Create accounts blueprint
bp = Blueprint('accounts', __name__, url_prefix='/accounts')

# Track if we've checked for incomplete setups on startup
_startup_check_done = False

def check_incomplete_setups():
    """Check for incomplete setups on server startup and resume them"""
    global _startup_check_done

    if _startup_check_done:
        return

    _startup_check_done = True

    try:
        logger.info("[SETUP] Checking for incomplete setups on startup...")

        # Initialize Firestore if needed
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass

        db = firestore.client()
        users_ref = db.collection('users')

        # Check for incomplete X setups
        x_query = users_ref.where('x_setup_complete', '==', False).where('x_account', '!=', '')
        x_incomplete_users = []

        for doc in x_query.stream():
            user_data = doc.to_dict()
            user_id = doc.id

            # Check if connection was started recently (within last 24 hours)
            connected_at = user_data.get('x_connected_at')
            if connected_at:
                try:
                    connected_time = datetime.fromisoformat(connected_at)
                    if datetime.now() - connected_time < timedelta(hours=24):
                        x_incomplete_users.append(user_id)
                except:
                    pass

        if x_incomplete_users:
            logger.info(f"[X_SETUP] Found {len(x_incomplete_users)} incomplete X setups to resume")
            for user_id in x_incomplete_users:
                logger.info(f"[X_SETUP] Resuming X setup for user {user_id}")
                resume_x_setup(user_id)
        else:
            logger.info("[X_SETUP] No incomplete X setups found")

        # Check for incomplete TikTok setups
        tiktok_query = users_ref.where('tiktok_setup_complete', '==', False).where('tiktok_account', '!=', '')
        tiktok_incomplete_users = []

        for doc in tiktok_query.stream():
            user_data = doc.to_dict()
            user_id = doc.id
            tiktok_incomplete_users.append(user_id)

        if tiktok_incomplete_users:
            logger.info(f"[SETUP] Found {len(tiktok_incomplete_users)} incomplete TikTok setups to resume")
            for user_id in tiktok_incomplete_users:
                logger.info(f"[SETUP] Resuming TikTok setup for user {user_id}")
                resume_tiktok_setup(user_id)
        else:
            logger.info("[SETUP] No incomplete TikTok setups found")

    except Exception as e:
        logger.error(f"[SETUP] Error checking incomplete setups: {str(e)}")

def resume_x_setup(user_id):
    """Resume X analytics fetch for a user"""
    from app.scripts.accounts.x_analytics import fetch_x_analytics

    def fetch_analytics_bg():
        try:
            logger.info(f"[X_SETUP] Resuming X analytics fetch for user {user_id}")
            fetch_x_analytics(user_id, is_initial=True)
            logger.info(f"[X_SETUP] Completed resumed X analytics fetch for user {user_id}")
        except Exception as e:
            import traceback
            logger.error(f"[X_SETUP] Error in resumed X analytics fetch for user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            # Mark setup as complete even on error so UI isn't stuck
            try:
                UserService.update_user(user_id, {'x_setup_complete': True})
                logger.info(f"[X_SETUP] Marked setup as complete after error for user {user_id}")
            except:
                pass

    bg_thread = threading.Thread(target=fetch_analytics_bg)
    bg_thread.daemon = True
    bg_thread.start()

def resume_tiktok_setup(user_id):
    """Resume TikTok analytics fetch for a user"""
    try:
        user_data = UserService.get_user(user_id)
        username = user_data.get('tiktok_account')

        if not username:
            logger.error(f"[SETUP] No TikTok username found for user {user_id}")
            return

        logger.info(f"[SETUP] Resuming TikTok setup for user {user_id}, username: {username}")

        bg_thread = threading.Thread(target=fetch_initial_tiktok_data, args=(user_id, username))
        bg_thread.daemon = True
        bg_thread.start()

    except Exception as e:
        logger.error(f"[SETUP] Error resuming TikTok setup: {str(e)}")

@bp.route('/', methods=['GET'])
@auth_required
def index():
    """Render accounts connection page"""
    # Check for incomplete setups on first request
    check_incomplete_setups()

    user_id = g.user.get('id')
    
    # Fetch user data from Firebase
    user_data = UserService.get_user(user_id)
    
    # Check if accounts are connected via Late.dev (for X, TikTok, Instagram, YouTube posting)
    x_latedev_info = LateDevOAuthService.get_account_info(user_id, 'x')
    tiktok_latedev_info = LateDevOAuthService.get_account_info(user_id, 'tiktok')
    instagram_latedev_info = LateDevOAuthService.get_account_info(user_id, 'instagram')
    youtube_latedev_info = LateDevOAuthService.get_account_info(user_id, 'youtube')

    # Check connection status
    x_connected = bool(x_latedev_info and x_latedev_info.get('username'))
    youtube_analytics_connected = bool(user_data.get('youtube_account', '')) if user_data else False
    youtube_posting_connected = bool(youtube_latedev_info and youtube_latedev_info.get('username'))
    tiktok_connected = bool(tiktok_latedev_info and tiktok_latedev_info.get('username'))
    instagram_connected = bool(instagram_latedev_info and instagram_latedev_info.get('username'))

    # Get account usernames
    x_username = x_latedev_info.get('username', '').lstrip('@') if x_latedev_info else ''
    youtube_channel = user_data.get('youtube_account', '') if user_data else ''
    youtube_posting_username = youtube_latedev_info.get('username', '').lstrip('@') if youtube_latedev_info else ''
    tiktok_username = tiktok_latedev_info.get('username', '').lstrip('@') if tiktok_latedev_info else ''
    instagram_username = instagram_latedev_info.get('username', '').lstrip('@') if instagram_latedev_info else ''

    # Check setup completion status
    x_setup_complete = user_data.get('x_setup_complete', True) if user_data else True
    tiktok_setup_complete = user_data.get('tiktok_setup_complete', True) if user_data else True
    youtube_setup_complete = user_data.get('youtube_setup_complete', True) if user_data else True

    # Check if we need to show super powers modal
    show_super_powers = request.args.get('show_super_powers', 'false').lower() == 'true'

    return render_template(
        'accounts/index.html',
        x_connected=x_connected,
        youtube_analytics_connected=youtube_analytics_connected,
        youtube_posting_connected=youtube_posting_connected,
        tiktok_connected=tiktok_connected,
        instagram_connected=instagram_connected,
        x_username=x_username,
        youtube_channel=youtube_channel,
        youtube_posting_username=youtube_posting_username,
        tiktok_username=tiktok_username,
        instagram_username=instagram_username,
        x_setup_complete=x_setup_complete,
        tiktok_setup_complete=tiktok_setup_complete,
        youtube_setup_complete=youtube_setup_complete,
        show_super_powers=show_super_powers,
        user_data=user_data
    )

@bp.route('/connect/<platform>')
@auth_required
def connect_platform(platform):
    """Initiate OAuth flow via Late.dev for X, TikTok, Instagram, or YouTube posting"""
    try:
        user_id = g.user.get('id')
        logger.info(f"Connect {platform} route called for user {user_id}")

        # Validate platform
        if platform not in ['x', 'tiktok', 'instagram', 'youtube']:
            flash("Invalid platform specified", "error")
            return redirect(url_for('accounts.index'))

        # Generate Late.dev authorization URL
        auth_url = LateDevOAuthService.get_authorization_url(user_id, platform)
        logger.info(f"Generated auth URL for {platform}: {auth_url}")

        logger.info(f"Redirecting user {user_id} to Late.dev {platform} OAuth")
        return redirect(auth_url)

    except Exception as e:
        logger.error(f"Error initiating {platform} OAuth: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f"Error connecting {platform} account. Please try again.", "error")
        return redirect(url_for('accounts.index'))

@bp.route('/callback/<platform>')
@auth_required
def oauth_callback(platform):
    """Handle Late.dev OAuth callback for all platforms"""
    try:
        user_id = g.user.get('id')
        logger.info(f"{platform.capitalize()} callback received for user {user_id}")
        logger.info(f"Query params: {dict(request.args)}")

        # Get success/error from query params
        success = request.args.get('success')
        error = request.args.get('error')
        connected = request.args.get('connected')

        if error:
            logger.error(f"{platform.capitalize()} OAuth error: {error}")
            flash(f"Error connecting {platform} account: {error}", "error")
            return redirect(url_for('accounts.index'))

        # Late.dev uses 'connected' parameter to indicate success
        if success == 'true' or connected:
            logger.info(f"{platform.capitalize()} connected successfully for user {user_id}")

            # Get username from Late.dev API
            account_info = LateDevOAuthService.get_account_info(user_id, platform)

            if account_info and account_info.get('username'):
                username = account_info.get('username').lstrip('@')
                logger.info(f"Got username from Late.dev: {username}")

                # Store username and mark setup as incomplete
                if platform == 'x':
                    UserService.update_user(user_id, {
                        'x_account': username,
                        'x_connected_at': datetime.now().isoformat(),
                        'x_setup_complete': False
                    })

                    # Start background analytics fetch
                    from app.scripts.accounts.x_analytics import fetch_x_analytics
                    def fetch_analytics_bg():
                        try:
                            logger.info(f"[X_SETUP] Starting initial X analytics fetch for user {user_id}")
                            fetch_x_analytics(user_id, is_initial=True)
                            logger.info(f"[X_SETUP] Completed initial X analytics fetch for user {user_id}")
                        except Exception as e:
                            import traceback
                            logger.error(f"[X_SETUP] Error: {str(e)}")
                            logger.error(traceback.format_exc())
                            try:
                                UserService.update_user(user_id, {'x_setup_complete': True})
                            except:
                                pass

                    bg_thread = threading.Thread(target=fetch_analytics_bg)
                    bg_thread.daemon = True
                    bg_thread.start()

                elif platform == 'tiktok':
                    UserService.update_user(user_id, {
                        'tiktok_account': username,
                        'tiktok_setup_complete': False
                    })

                    # Start background analytics fetch
                    logger.info(f"Starting initial TikTok analytics fetch for user {user_id}")
                    bg_thread = threading.Thread(target=fetch_initial_tiktok_data, args=(user_id, username))
                    bg_thread.daemon = True
                    bg_thread.start()

                elif platform == 'instagram':
                    # Instagram - no analytics yet, just store username
                    UserService.update_user(user_id, {
                        'instagram_account': username
                    })
                    logger.info(f"Stored Instagram username: {username}")

                elif platform == 'youtube':
                    # YouTube posting via Late.dev - no analytics, just store for posting capability
                    logger.info(f"Stored YouTube posting account: {username}")

                flash(f"Successfully connected {platform} account @{username}", "success")
            else:
                logger.error(f"Could not get username from Late.dev for {platform}")
                flash(f"Connected {platform} but could not retrieve username", "warning")

            return redirect(url_for('accounts.index'))
        else:
            logger.error(f"{platform.capitalize()} OAuth failed - no success indicator")
            flash(f"Failed to connect {platform} account", "error")
            return redirect(url_for('accounts.index'))

    except Exception as e:
        logger.error(f"Error in {platform} callback: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f"Error processing {platform} connection", "error")
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

@bp.route('/force-complete-setup', methods=['POST', 'GET'])
@auth_required
def force_complete_setup():
    """Force mark setup as complete (for when it gets stuck)"""
    user_id = g.user.get('id')

    # Support both POST form data and GET query params
    if request.method == 'POST':
        platform = request.form.get('platform')
    else:
        platform = request.args.get('platform')

    try:
        if platform == 'x':
            UserService.update_user(user_id, {'x_setup_complete': True})
            logger.info(f"[X_SETUP] Manually marked X setup as complete for user {user_id}")
            message = 'X setup marked as complete'
        elif platform == 'tiktok':
            UserService.update_user(user_id, {'tiktok_setup_complete': True})
            logger.info(f"Manually marked TikTok setup as complete for user {user_id}")
            message = 'TikTok setup marked as complete'
        elif platform == 'youtube':
            UserService.update_user(user_id, {'youtube_setup_complete': True})
            logger.info(f"Manually marked YouTube setup as complete for user {user_id}")
            message = 'YouTube setup marked as complete'
        else:
            return jsonify({'error': 'Invalid platform'}), 400

        if request.method == 'GET':
            flash(message, 'success')
            return redirect(url_for('accounts.index'))

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error force completing setup: {str(e)}")
        if request.method == 'GET':
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('accounts.index'))
        return jsonify({'error': 'Failed to complete setup'}), 500

@bp.route('/disconnect', methods=['POST'])
@auth_required
def disconnect_account():
    """Disconnect a social media account"""
    user_id = g.user.get('id')
    platform = request.form.get('platform')
    
    if platform == 'x':
        # Disconnect from Late.dev first
        try:
            LateDevOAuthService.disconnect(user_id, 'x')
            logger.info(f"Disconnected X from Late.dev for user {user_id}")
        except Exception as e:
            logger.error(f"Error disconnecting X from Late.dev: {str(e)}")

        # Remove X account from Firebase
        UserService.update_user(user_id, {'x_account': ''})

        # Clean up X analytics data and brand voice data
        try:
            from app.scripts.accounts.x_analytics import clean_user_data
            import firebase_admin
            from firebase_admin import firestore

            def clean_data_bg():
                try:
                    # Clean X analytics data
                    clean_user_data(user_id)

                    # Clean brand voice data (x_replies collection)
                    logger.info(f"Cleaning brand voice data for user {user_id}")

                    # Initialize Firestore if needed
                    if not firebase_admin._apps:
                        try:
                            firebase_admin.initialize_app()
                        except ValueError:
                            pass

                    db = firestore.client()

                    # Delete x_replies collection data
                    x_replies_collection = db.collection('users').document(user_id).collection('x_replies')

                    # Delete 'data' document (where brand voice replies are stored)
                    data_ref = x_replies_collection.document('data')
                    if data_ref.get().exists:
                        data_ref.delete()
                        logger.info(f"Deleted x_replies/data document for user {user_id}")

                    # Delete any other documents in x_replies collection
                    docs = x_replies_collection.stream()
                    for doc in docs:
                        doc.reference.delete()
                        logger.info(f"Deleted x_replies/{doc.id} document for user {user_id}")

                    # Clean up reply_guy collection data (lists, analyses, etc.)
                    reply_guy_collection = db.collection('users').document(user_id).collection('reply_guy')

                    # Delete lists
                    lists_docs = reply_guy_collection.where('type', 'in', ['default', 'custom']).stream()
                    for doc in lists_docs:
                        doc.reference.delete()
                        logger.info(f"Deleted reply_guy list {doc.id} for user {user_id}")

                    # Delete analyses
                    analyses_docs = reply_guy_collection.where('list_id', '!=', '').stream()
                    for doc in analyses_docs:
                        doc.reference.delete()
                        logger.info(f"Deleted reply_guy analysis {doc.id} for user {user_id}")

                    logger.info(f"Successfully cleaned brand voice and reply guy data for user {user_id}")

                except Exception as e:
                    logger.error(f"Error cleaning X data: {str(e)}")

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
        # Disconnect from Late.dev first
        try:
            LateDevOAuthService.disconnect(user_id, 'tiktok')
            logger.info(f"Disconnected TikTok from Late.dev for user {user_id}")
        except Exception as e:
            logger.error(f"Error disconnecting TikTok from Late.dev: {str(e)}")

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

    elif platform == 'instagram':
        # Disconnect from Late.dev
        try:
            LateDevOAuthService.disconnect(user_id, 'instagram')
            logger.info(f"Disconnected Instagram from Late.dev for user {user_id}")
        except Exception as e:
            logger.error(f"Error disconnecting Instagram from Late.dev: {str(e)}")

        # Remove Instagram account from Firebase
        UserService.update_user(user_id, {
            'instagram_account': ''
        })

        flash("Successfully disconnected Instagram account", "success")

    elif platform == 'youtube_posting':
        # Disconnect YouTube posting (Late.dev) only
        try:
            LateDevOAuthService.disconnect(user_id, 'youtube')
            logger.info(f"Disconnected YouTube posting from Late.dev for user {user_id}")
            flash("Successfully disconnected YouTube posting", "success")
        except Exception as e:
            logger.error(f"Error disconnecting YouTube posting from Late.dev: {str(e)}")
            flash("Error disconnecting YouTube posting", "error")

    else:
        flash("Invalid platform specified", "error")

    return redirect(url_for('accounts.index'))

# YouTube Analytics OAuth route (separate from Late.dev posting)
@bp.route('/connect/youtube-analytics', methods=['GET'])
@auth_required
def youtube_connect_redirect():
    """Redirect to YouTube Analytics OAuth flow"""
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