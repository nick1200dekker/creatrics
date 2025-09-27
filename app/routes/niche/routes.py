# File: app/routes/niche/routes.py

from flask import Blueprint, render_template, request, jsonify, g
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.services.firebase_service import UserService
from app.scripts.niche.tracker_service import TrackerService
from app.scripts.niche.x_list_manager import XListManager
from app.scripts.niche.creator_analyzer import CreatorAnalyzer
from firebase_admin import firestore
import logging
import threading
from datetime import datetime
import time

# Setup logger
logger = logging.getLogger('niche_routes')

# Create niche blueprint
bp = Blueprint('niche', __name__, url_prefix='/niche')

# Initialize services
tracker_service = TrackerService()
x_list_manager = XListManager()
creator_analyzer = CreatorAnalyzer()
db = firestore.client()

# ENHANCED: Global analysis status tracking with better cleanup
analysis_status = {}

def update_analysis_status(user_id: str, list_name: str, status: str, step: str = '', progress: int = 0, error: str = None):
    """Update analysis status with detailed tracking"""
    key = f"{user_id}_{list_name}"
    analysis_status[key] = {
        'user_id': user_id,
        'list_name': list_name,
        'status': status,  # 'processing', 'completed', 'error', 'idle'
        'step': step,
        'progress': progress,
        'error': error,
        'timestamp': time.time(),
        'running': status == 'processing'
    }
    logger.info(f"Analysis status updated: {key} - {status} - {step} ({progress}%)")

def get_analysis_status(user_id: str) -> dict:
    """Get current analysis status for user with improved cleanup"""
    current_time = time.time()
    
    # Clean up old statuses (older than 4 hours)
    keys_to_remove = []
    for key, data in analysis_status.items():
        if current_time - data['timestamp'] > 14400:  # 4 hours
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del analysis_status[key]
        logger.info(f"Cleaned up old analysis status: {key}")
    
    # FIXED: Find most recent analysis for this user
    user_analyses = []
    for key, status_data in analysis_status.items():
        if status_data['user_id'] == user_id:
            user_analyses.append((status_data['timestamp'], status_data))
    
    if user_analyses:
        # Return the most recent analysis status
        user_analyses.sort(key=lambda x: x[0], reverse=True)
        return user_analyses[0][1]
    
    # Return idle status if no analysis found
    return {
        'user_id': user_id,
        'status': 'idle',
        'step': 'Ready to analyze',
        'progress': 0,
        'running': False,
        'timestamp': current_time
    }

def clear_analysis_status(user_id: str, list_name: str = None):
    """Clear analysis status for user with improved logic"""
    if list_name:
        key = f"{user_id}_{list_name}"
        if key in analysis_status:
            logger.info(f"Clearing specific analysis status: {key}")
            del analysis_status[key]
    else:
        # Clear all for user
        keys_to_remove = [k for k in analysis_status.keys() if analysis_status[k]['user_id'] == user_id]
        for key in keys_to_remove:
            logger.info(f"Clearing user analysis status: {key}")
            del analysis_status[key]

def analyze_creators_async(user_id: str, list_name: str, time_range: str):
    """Perform creator analysis in background thread with enhanced status tracking"""
    try:
        # Update initial status
        update_analysis_status(user_id, list_name, 'processing', 'Starting analysis...', 5)
        
        # Get creators from list
        update_analysis_status(user_id, list_name, 'processing', 'Loading creator list...', 10)
        creators = tracker_service.get_list_creators(user_id, list_name)
        if not creators:
            logger.error(f"No creators found in list {list_name} for user {user_id}")
            update_analysis_status(user_id, list_name, 'error', 'No creators found in list', 0, 'No creators found in list')
            return
        
        logger.info(f"Starting analysis for {len(creators)} creators")
        update_analysis_status(user_id, list_name, 'processing', f'Analyzing {len(creators)} creators...', 20)
        
        # FIXED: Create a simplified status callback that doesn't show individual creators
        def status_callback(step: str, progress: int):
            # Simplify the step message to just show "Analyzing..."
            simplified_step = "Analyzing creators..."
            update_analysis_status(user_id, list_name, 'processing', simplified_step, progress)
        
        # Perform analysis with status callback
        update_analysis_status(user_id, list_name, 'processing', 'Collecting tweets and engagement data...', 40)
        analysis_result = creator_analyzer.analyze_creators(
            user_id, 
            creators, 
            time_range, 
            list_name,
            status_callback=status_callback
        )
        
        if not analysis_result:
            logger.error(f"Analysis failed for user {user_id}")
            update_analysis_status(user_id, list_name, 'error', 'Analysis failed', 0, 'Analysis failed to complete')
            return
        
        # Save analysis to database - CHANGED: Save to single "latest" document
        update_analysis_status(user_id, list_name, 'processing', 'Saving analysis results...', 90)
        analysis_data = {
            'list_name': list_name,
            'timestamp': datetime.now(),
            'parameters': {
                'analyzed_creators': creators,
                'creator_count': len(creators)
            },
            'hot_on_timeline': analysis_result['hot_on_timeline'],
            'top_performing_tweets': analysis_result['top_performing_tweets'],
            'creator_stats': analysis_result['creator_stats'],
            'performance_chart_data': analysis_result['performance_chart_data']
        }
        
        # CHANGED: Save to single "latest" document instead of creating new documents
        latest_analysis_ref = (db.collection('users')
                              .document(str(user_id))
                              .collection('creator_tracker')
                              .document('latest_analysis'))
        
        latest_analysis_ref.set(analysis_data)
        
        logger.info(f"Creator analysis completed successfully for user {user_id}, list {list_name}")
        
        # Mark as completed
        update_analysis_status(user_id, list_name, 'completed', 'Analysis completed successfully!', 100)
        
        # FIXED: Keep completed status for much longer to ensure frontend detects it
        def cleanup_status():
            time.sleep(120)  # Keep completed status for 2 minutes
            clear_analysis_status(user_id, list_name)
        
        cleanup_thread = threading.Thread(target=cleanup_status)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"Error during analysis for user {user_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        update_analysis_status(user_id, list_name, 'error', f'Analysis failed: {str(e)}', 0, str(e))

@bp.route('/', methods=['GET'])
@auth_required
@require_permission('niche_radar')
def index():
    """Render niche radar tool page with lists and analysis"""
    try:
        user_id = get_workspace_user_id()
        logger.info(f"Niche Radar page accessed by user {user_id}")
        
        # Get user's creator lists
        creator_lists = tracker_service.get_user_lists(user_id)
        
        # Get default/active list
        default_list = tracker_service.get_default_list(user_id)
        
        # CHANGED: Get latest analysis from single document
        latest_analysis = None
        top_tweets = []
        creators = []
        creator_stats = {}
        hot_on_timeline = ""
        timestamp = ""
        performance_chart_data = None
        
        try:
            # CHANGED: Get from single "latest_analysis" document
            latest_analysis_ref = (db.collection('users')
                                  .document(str(user_id))
                                  .collection('creator_tracker')
                                  .document('latest_analysis'))
            
            analysis_doc = latest_analysis_ref.get()
            
            if analysis_doc.exists:
                latest_analysis = analysis_doc.to_dict()
                logger.info(f"Found latest analysis for user {user_id}")
                
                # Process analysis data
                top_tweets = latest_analysis.get('top_performing_tweets', [])
                creators = latest_analysis.get('parameters', {}).get('analyzed_creators', [])
                creator_stats = latest_analysis.get('creator_stats', {})
                hot_on_timeline = latest_analysis.get('hot_on_timeline', "")
                
                # Handle timestamp
                timestamp_obj = latest_analysis.get('timestamp')
                if timestamp_obj:
                    if hasattr(timestamp_obj, 'seconds'):
                        timestamp = datetime.fromtimestamp(timestamp_obj.seconds).strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(timestamp_obj, datetime):
                        timestamp = timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp = str(timestamp_obj)
                
                performance_chart_data = tracker_service.transform_chart_data(
                    latest_analysis.get('performance_chart_data', [])
                )
                
                logger.info(f"Analysis data processed: {len(top_tweets)} tweets, {len(creators)} creators")
            else:
                logger.info(f"No analysis found for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error loading latest analysis: {e}")
            # Continue without analysis data
        
        return render_template(
            'niche/index.html',
            creator_lists=creator_lists,
            default_list=default_list,
            latest_analysis=latest_analysis,
            top_tweets=top_tweets,
            creators=creators,
            creator_stats=creator_stats,
            hot_on_timeline=hot_on_timeline,
            timestamp=timestamp,
            performance_chart_data=performance_chart_data
        )
        
    except Exception as e:
        logger.error(f"Error loading niche page: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return render_template(
            'niche/index.html',
            creator_lists=[],
            default_list=None,
            latest_analysis=None,
            top_tweets=[],
            creators=[],
            creator_stats={},
            hot_on_timeline="",
            timestamp="",
            performance_chart_data=None,
            error="Failed to load niche data"
        )

# REMOVED: get_analysis_history and get_analysis routes since we only store latest

@bp.route('/get-status', methods=['GET'])
@auth_required
@require_permission('niche_radar')
def get_status():
    """ENHANCED: Get current analysis status with improved cleanup and detailed tracking"""
    try:
        user_id = get_workspace_user_id()
        
        # Get current analysis status for user (includes automatic cleanup)
        status_data = get_analysis_status(user_id)
        
        logger.debug(f"Status check for user {user_id}: {status_data['status']} - {status_data.get('step', '')}")
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({
            'running': False,
            'step': 'Error checking status',
            'progress': 0,
            'status': 'error',
            'error': str(e)
        }), 500

@bp.route('/analyze-creators', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def analyze_creators():
    """ENHANCED: Start creator analysis with improved status tracking and validation"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name')
        time_range = data.get('time_range', '24h')
        
        if not list_name:
            return jsonify({
                'success': False, 
                'error': 'List name is required'
            }), 400
        
        # Check if user already has an analysis running
        current_status = get_analysis_status(user_id)
        if current_status['status'] == 'processing':
            return jsonify({
                'success': False,
                'error': f'Analysis already in progress for list: {current_status.get("list_name", "unknown")}'
            }), 400
        
        # Verify the list exists and has creators
        creators = tracker_service.get_list_creators(user_id, list_name)
        if not creators:
            return jsonify({
                'success': False, 
                'error': f'List "{list_name}" not found or has no creators'
            }), 400
        
        # Clear any old status for this user
        clear_analysis_status(user_id)
        
        # Set initial status
        update_analysis_status(user_id, list_name, 'processing', 'Initializing analysis...', 0)
        
        # Start analysis in background thread
        thread = threading.Thread(
            target=analyze_creators_async, 
            args=(user_id, list_name, time_range)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started analysis for user {user_id}, list {list_name}, time_range {time_range}")
        
        return jsonify({
            'success': True, 
            'message': 'Analysis started',
            'list_name': list_name
        })
            
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Internal server error'
        }), 500

@bp.route('/stop-analysis', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def stop_analysis():
    """ENHANCED: Stop ongoing analysis with proper cleanup"""
    try:
        user_id = get_workspace_user_id()
        
        # Clear analysis status to effectively "stop" it
        clear_analysis_status(user_id)
        
        logger.info(f"Analysis stopped for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Analysis stopped'
        })
        
    except Exception as e:
        logger.error(f"Error stopping analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to stop analysis'
        }), 500

@bp.route('/create-list', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def create_list():
    """Create a new creator list"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name', '').strip()
        list_type = data.get('list_type', 'manual')
        x_list_id = data.get('x_list_id', '').strip() if data.get('x_list_id') else None
        
        if not list_name:
            return jsonify({
                'success': False, 
                'message': 'Please enter a valid list name'
            }), 400
        
        if list_type == 'x_list' and not x_list_id:
            return jsonify({
                'success': False, 
                'message': 'X List ID required for X lists'
            }), 400
        
        result = tracker_service.create_list(user_id, list_name, list_type, x_list_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating list: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error creating list: {str(e)}'
        }), 500

@bp.route('/delete-list', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def delete_list():
    """Delete a creator list"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name', '').strip()
        
        if not list_name:
            return jsonify({
                'success': False, 
                'error': 'List name is required'
            }), 400
        
        success = tracker_service.delete_list(user_id, list_name)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'List "{list_name}" deleted successfully'
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Failed to delete list or list not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error deleting list: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'Internal server error'
        }), 500

@bp.route('/add-creator', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def add_creator():
    """Add a creator to a list"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name', '').strip()
        creator_handle = data.get('creator_handle', '').strip()
        
        if not list_name or not creator_handle:
            return jsonify({
                'success': False,
                'message': 'Please select a list and enter a creator handle'
            }), 400
        
        # Remove @ if present
        if creator_handle.startswith('@'):
            creator_handle = creator_handle[1:]
        
        result = tracker_service.add_creator_to_list(user_id, list_name, creator_handle)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error adding creator: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error adding creator: {str(e)}'
        }), 500

@bp.route('/remove-creator', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def remove_creator():
    """Remove a creator from a list"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name', '').strip()
        creator_handle = data.get('creator_handle', '').strip()
        
        if not list_name or not creator_handle:
            return jsonify({
                'success': False,
                'error': 'List name and creator handle are required'
            }), 400
        
        # Remove @ if present
        if creator_handle.startswith('@'):
            creator_handle = creator_handle[1:]
        
        result = tracker_service.remove_creator_from_list(user_id, list_name, creator_handle)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error removing creator: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@bp.route('/get-creators', methods=['GET'])
@auth_required
@require_permission('niche_radar')
def get_creators():
    """Get creators for a specific list"""
    try:
        user_id = get_workspace_user_id()
        list_name = request.args.get('list_name', '').strip()
        
        if not list_name:
            return jsonify({
                'success': False, 
                'message': 'No list name provided'
            }), 400
        
        creators = tracker_service.get_list_creators(user_id, list_name)
        
        return jsonify({
            'success': True,
            'creators': creators,
            'list_name': list_name
        })
        
    except Exception as e:
        logger.error(f"Error getting creators: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error reading creators: {str(e)}'
        }), 500

@bp.route('/set-default-list', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def set_default_list():
    """Set a list as the default list"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name', '').strip()
        
        if not list_name:
            return jsonify({
                'success': False, 
                'message': 'Please select a valid list'
            }), 400
        
        success = tracker_service.set_default_list(user_id, list_name)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'List "{list_name}" set as default'
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'Error setting default list'
            }), 500
            
    except Exception as e:
        logger.error(f"Error setting default list: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error setting default list: {str(e)}'
        }), 500

@bp.route('/update-x-list', methods=['POST'])
@auth_required
@require_permission('niche_radar')
def update_x_list():
    """Update an X list with latest members"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json() if request.is_json else request.form
        
        list_name = data.get('list_name', '').strip()
        
        if not list_name:
            return jsonify({
                'success': False, 
                'message': 'List name is required'
            }), 400
        
        result = tracker_service.update_x_list(user_id, list_name)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating X list: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error updating X list: {str(e)}'
        }), 500

# Error handlers
@bp.errorhandler(400)
def bad_request(error):
    return jsonify({'success': False, 'error': 'Bad request'}), 400

@bp.errorhandler(401)
def unauthorized(error):
    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

@bp.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500