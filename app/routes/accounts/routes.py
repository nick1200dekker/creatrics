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
        show_super_powers=show_super_powers
    )

@bp.route('/connect', methods=['POST'])
@auth_required
def connect_account():
    """Connect a social media account"""
    user_id = g.user.get('id')
    platform = request.form.get('platform')
    
    if platform == 'x':
        username = request.form.get('x_username', '').strip()
        if not username:
            flash("Please enter your X username", "error")
            return redirect(url_for('accounts.index'))
        
        # Store X account in Firebase
        UserService.update_user(user_id, {'x_account': username})
        
        # Mark account as newly connected for initial fetch
        UserService.update_user(user_id, {
            'x_account': username,
            'x_connected_at': datetime.now().isoformat()
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
                    logger.error(f"Error fetching initial X analytics: {str(e)}")
            
            thread = threading.Thread(target=fetch_analytics_bg)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Error setting up X analytics: {str(e)}")
        
        flash(f"Successfully connected X account @{username}", "success")
        return redirect(url_for('accounts.index', show_super_powers='true', platform='x'))
        
    elif platform == 'tiktok':
        username = request.form.get('tiktok_username', '').strip()
        if not username:
            flash("Please enter your TikTok username", "error")
            return redirect(url_for('accounts.index'))
        
        # Store TikTok account in Firebase
        UserService.update_user(user_id, {'tiktok_account': username})
        flash(f"Successfully connected TikTok account @{username}", "success")
        return redirect(url_for('accounts.index', show_super_powers='true', platform='tiktok'))
        
    else:
        flash("Invalid platform specified", "error")
        return redirect(url_for('accounts.index'))

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
        UserService.update_user(user_id, {'tiktok_account': ''})
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