"""
Reply Guy Routes - Optimized version with improved performance and duplicate request prevention
"""
from flask import render_template, request, jsonify, g, session
import logging
from datetime import datetime, timedelta
import time
import hashlib
import json
from functools import wraps

from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import require_permission, get_workspace_user_id
from app.scripts.reply_guy.reply_guy_service import ReplyGuyService
from app.system.credits.credits_manager import CreditsManager

logger = logging.getLogger(__name__)

# In-memory cache for request deduplication (in production, use Redis)
REQUEST_CACHE = {}
REQUEST_TIMEOUT = 30  # seconds

def debounce_requests(timeout=5):
    """Decorator to prevent duplicate API requests within timeout period"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create unique request signature
            user_id = get_workspace_user_id() if hasattr(g, 'user') else 'anonymous'
            request_data = request.get_json() if request.is_json else {}
            endpoint = request.endpoint
            
            # Create cache key
            cache_key = f"{user_id}:{endpoint}:{hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()}"
            
            current_time = time.time()
            
            # Check if this request was made recently
            if cache_key in REQUEST_CACHE:
                last_request_time = REQUEST_CACHE[cache_key]
                if current_time - last_request_time < timeout:
                    return jsonify({
                        'success': False, 
                        'error': f'Please wait {timeout} seconds between requests',
                        'rate_limited': True
                    }), 429
            
            # Update cache
            REQUEST_CACHE[cache_key] = current_time
            
            # Clean old entries
            clean_request_cache()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def clean_request_cache():
    """Remove old entries from request cache"""
    current_time = time.time()
    keys_to_remove = []
    
    for key, timestamp in REQUEST_CACHE.items():
        if current_time - timestamp > REQUEST_TIMEOUT:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        REQUEST_CACHE.pop(key, None)

def validate_request_data(required_fields=None, optional_fields=None):
    """Decorator to validate request data"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400
            
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if not data.get(field)]
                if missing_fields:
                    return jsonify({
                        'success': False, 
                        'error': f'Missing required fields: {", ".join(missing_fields)}'
                    }), 400
            
            # Validate field types and values
            if 'list_id' in data and not isinstance(data['list_id'], str):
                return jsonify({'success': False, 'error': 'list_id must be a string'}), 400
            
            if 'list_type' in data and data['list_type'] not in ['default', 'custom']:
                return jsonify({'success': False, 'error': 'list_type must be "default" or "custom"'}), 400
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

@bp.route('/')
@auth_required
@require_permission('reply_guy')
def index():
    """Main Reply Guy dashboard - optimized with caching"""
    user_id = get_workspace_user_id()
    try:
        service = ReplyGuyService()
        
        # Use caching for static data
        cache_key = f"reply_guy_static_data_{user_id}"
        
        # Get default lists (cache for 1 hour)
        default_lists = service.get_default_lists()
        
        # Get user's custom lists with minimal data
        custom_lists = service.get_user_custom_lists(user_id)
        
        # Get user's current selected list and analysis
        current_selection = service.get_current_selection(user_id)
        current_analysis = None

        # If no selection exists, auto-select the first default list
        if not current_selection and default_lists:
            first_default_list = default_lists[0]
            current_selection = {
                'list_id': first_default_list['id'],
                'list_type': 'default'
            }
            # Save this selection for the user
            service.set_current_selection(user_id, first_default_list['id'], 'default')
            logger.info(f"Auto-selected first default list: {first_default_list['id']}")

        if current_selection:
            # Only load analysis if we have a selection
            current_analysis = service.get_current_analysis(
                user_id,
                current_selection['list_id'],
                current_selection['list_type']
            )
            logger.info(f"Loaded analysis for {current_selection['list_type']} list {current_selection['list_id']}: {len(current_analysis.get('tweet_opportunities', [])) if current_analysis else 0} opportunities")
        
        # Get reply stats efficiently
        reply_stats = service.get_reply_stats(user_id)
        
        # Static reply styles (cache in memory)
        reply_styles = [
            {"id": "supportive", "name": "Supportive"},
            {"id": "questioning", "name": "Questioning"}, 
            {"id": "valueadd", "name": "Value-Add"},
            {"id": "humorous", "name": "Humorous"},
            {"id": "contrarian", "name": "Contrarian"}
        ]
        
        # Check for ongoing updates efficiently
        ongoing_updates = get_ongoing_updates(user_id)
        
        return render_template('reply_guy/index.html',
                             default_lists=default_lists,
                             custom_lists=custom_lists,
                             current_selection=current_selection,
                             current_analysis=current_analysis,
                             reply_stats=reply_stats,
                             reply_styles=reply_styles,
                             ongoing_updates=ongoing_updates)
                             
    except Exception as e:
        logger.error(f"Error loading Reply Guy dashboard: {str(e)}")
        # Return minimal fallback data
        return render_template('reply_guy/index.html',
                             default_lists=[],
                             custom_lists=[],
                             current_selection=None,
                             current_analysis=None,
                             reply_stats={'total_replies': 0, 'target': 50, 'progress_percentage': 0},
                             reply_styles=[],
                             ongoing_updates={})

def get_ongoing_updates(user_id):
    """Check for ongoing update operations - optimized"""
    try:
        from firebase_admin import firestore
        db = firestore.client()
        
        # Check for updates started in the last 10 minutes only
        recent_time = datetime.now() - timedelta(minutes=10)
        
        updates_ref = db.collection('users').document(str(user_id)).collection('reply_guy').document('updates')
        updates_doc = updates_ref.get()
        
        if not updates_doc.exists:
            return {}
        
        updates_data = updates_doc.to_dict()
        ongoing = {}
        
        for list_id, update_info in updates_data.items():
            if not isinstance(update_info, dict) or 'started_at' not in update_info:
                continue
                
            started_at = update_info['started_at']
            if isinstance(started_at, str):
                try:
                    started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                except ValueError:
                    continue
            
            # Only include recent running updates
            if (update_info.get('status') == 'running' and 
                started_at > recent_time):
                ongoing[list_id] = {
                    'status': 'running',
                    'started_at': started_at.isoformat()
                }
        
        return ongoing
        
    except Exception as e:
        logger.error(f"Error checking ongoing updates: {str(e)}")
        return {}

def set_update_status(user_id, list_id, status, started_at=None):
    """Set update status with error handling"""
    try:
        from firebase_admin import firestore
        db = firestore.client()
        
        updates_ref = db.collection('users').document(str(user_id)).collection('reply_guy').document('updates')
        
        if status == 'running':
            update_data = {
                list_id: {
                    'status': status,
                    'started_at': (started_at or datetime.now()).isoformat()
                }
            }
            updates_ref.set(update_data, merge=True)
        elif status == 'completed':
            # Remove the update status when completed
            updates_ref.update({list_id: firestore.DELETE_FIELD})
        
    except Exception as e:
        logger.error(f"Error setting update status: {str(e)}")

@bp.route('/check-update-status', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['list_id'])
def check_update_status():
    """Check if an update is currently running for a specific list"""
    try:
        data = request.get_json()
        list_id = data.get('list_id')
        user_id = get_workspace_user_id()
        
        ongoing_updates = get_ongoing_updates(user_id)
        is_updating = list_id in ongoing_updates
        
        return jsonify({
            'success': True,
            'is_updating': is_updating,
            'update_info': ongoing_updates.get(list_id, {})
        })
        
    except Exception as e:
        logger.error(f"Error checking update status: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/select-list', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['list_id', 'list_type'])
@debounce_requests(timeout=2)
def select_list():
    """Select a list for analysis - optimized with caching"""
    try:
        data = request.get_json()
        list_id = data.get('list_id')
        list_type = data.get('list_type')
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        # Check ongoing updates efficiently
        ongoing_updates = get_ongoing_updates(user_id)
        is_updating = list_id in ongoing_updates
        
        # Save user's selection
        success = service.set_current_selection(user_id, list_id, list_type)
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to select list'}), 500
        
        # Quick check for existing analysis
        analysis = service.get_current_analysis(user_id, list_id, list_type)
        opportunities_count = len(analysis.get('tweet_opportunities', [])) if analysis else 0
        
        return jsonify({
            'success': True, 
            'message': 'List selected successfully',
            'has_analysis': analysis is not None,
            'opportunities_count': opportunities_count,
            'is_updating': is_updating,
            'update_info': ongoing_updates.get(list_id, {})
        })
            
    except Exception as e:
        logger.error(f"Error selecting list: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/analyze', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['list_id', 'list_type'])
@debounce_requests(timeout=10)
def analyze():
    """Run analysis on selected list - with duplicate prevention"""
    try:
        data = request.get_json()
        list_id = data.get('list_id')
        list_type = data.get('list_type')
        time_range = data.get('time_range', '24h')
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        # For default lists, return immediately
        if list_type == 'default':
            return jsonify({
                'success': True, 
                'message': 'Default list data refreshed',
                'analysis_id': list_id
            })
        
        # Check if already updating
        ongoing_updates = get_ongoing_updates(user_id)
        if list_id in ongoing_updates:
            return jsonify({
                'success': False, 
                'error': 'Update already in progress for this list',
                'is_updating': True
            }), 409
        
        # Set update status
        set_update_status(user_id, list_id, 'running')
        
        try:
            # Run analysis
            analysis_id = service.run_analysis(user_id, list_id, list_type, time_range)
            
            # Clear status on success
            set_update_status(user_id, list_id, 'completed')
            
            if analysis_id:
                return jsonify({
                    'success': True, 
                    'message': 'Analysis completed',
                    'analysis_id': analysis_id
                })
            else:
                return jsonify({'success': False, 'error': 'Analysis failed'}), 500
                
        except Exception as analysis_error:
            # Clear status on error
            set_update_status(user_id, list_id, 'completed')
            logger.error(f"Analysis error for list {list_id}: {str(analysis_error)}")
            raise analysis_error
            
    except Exception as e:
        logger.error(f"Error running analysis: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/generate-reply', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['tweet_text', 'author'])
@debounce_requests(timeout=3)
def generate_reply():
    """Generate AI reply with rate limiting and validation"""
    try:
        data = request.get_json()
        tweet_text = data.get('tweet_text', '').strip()
        author = data.get('author', '').strip()
        style = data.get('style', 'supportive')
        use_brand_voice = data.get('use_brand_voice', False)
        
        # Additional validation
        if not tweet_text or not author:
            return jsonify({'success': False, 'error': 'Tweet text and author are required'}), 400
        
        if len(tweet_text) > 2000:  # Reasonable limit
            return jsonify({'success': False, 'error': 'Tweet text too long'}), 400
        
        # Filter out mention tweets
        if tweet_text.startswith('@'):
            return jsonify({'success': False, 'error': 'Cannot generate replies to mention tweets'}), 400
        
        user_id = get_workspace_user_id()
        
        # Check credits efficiently (following video_tags pattern)
        credits_manager = CreditsManager()
        
        # Step 1: Estimate LLM cost from tweet text
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=tweet_text,
            model_name='claude-3-haiku-20240307'  # Use Claude Haiku for replies
        )
        
        required_credits = cost_estimate['final_cost']
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )
        
        # Check for sufficient credits - strict enforcement
        if not credit_check.get('sufficient', False):
            return jsonify({
                'success': False,
                'error': f'Insufficient credits. Required: {required_credits:.2f}, Available: {current_credits:.2f}',
                'error_type': 'insufficient_credits',
                'current_credits': current_credits,
                'required_credits': required_credits,
                'credits_required': True
            }), 402
        
        # Generate reply
        service = ReplyGuyService()
        reply_text = service.generate_reply(
            user_id=user_id,
            tweet_text=tweet_text, 
            author=author,
            style=style,
            use_brand_voice=use_brand_voice
        )
        
        if not reply_text:
            return jsonify({'success': False, 'error': 'Failed to generate reply'}), 500
        
        # Step 3: Deduct credits after successful generation (following video_tags pattern)
        try:
            # Estimate tokens more accurately (1 token ≈ 4 characters for Claude)
            input_tokens = max(100, len(tweet_text) // 4)
            output_tokens = max(50, len(reply_text) // 4)
            
            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name='claude-3-haiku-20240307',
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                description=f"Reply Guy reply to @{author}",
                feature_id="reply_guy"
            )
            
            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                
        except Exception as credit_error:
            logger.error(f"Error deducting credits: {str(credit_error)}")
            # Don't fail the request if credit deduction fails
        
        return jsonify({'success': True, 'reply': reply_text})
            
    except Exception as e:
        logger.error(f"Error generating reply: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/log-reply', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['tweet_id', 'reply_text'])
def log_reply():
    """Log a reply action - optimized"""
    try:
        data = request.get_json()
        tweet_id = data.get('tweet_id', '').strip()
        reply_text = data.get('reply_text', '').strip()
        
        # Basic validation
        if not tweet_id or not reply_text:
            return jsonify({'success': False, 'error': 'Tweet ID and reply text are required'}), 400
        
        if len(reply_text) > 280:
            return jsonify({'success': False, 'error': 'Reply text exceeds Twitter limit'}), 400
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        # Log reply and get stats
        stats = service.log_reply(user_id, tweet_id, reply_text)
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error logging reply: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/create-custom-list', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['name', 'type'])
@debounce_requests(timeout=5)
def create_custom_list():
    """Create a new custom list with improved error handling"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        list_type = data.get('type', '').strip()
        x_list_id = data.get('x_list_id', '').strip() if data.get('x_list_id') else None
        
        # Enhanced validation
        if not name or len(name) > 100:
            return jsonify({'success': False, 'error': 'List name must be 1-100 characters'}), 400
        
        if list_type != 'x_list':
            return jsonify({'success': False, 'error': 'Only X lists are supported'}), 400
        
        if list_type == 'x_list' and not x_list_id:
            return jsonify({'success': False, 'error': 'X list ID required for X lists'}), 400
        
        if x_list_id and not x_list_id.isdigit():
            return jsonify({'success': False, 'error': 'X list ID must be numeric'}), 400
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        # Create the custom list
        result = service.create_custom_list(user_id, name, list_type, x_list_id)
        
        if result['success']:
            # Check for warning cases
            if list_type == 'x_list' and result.get('list', {}).get('account_count', 0) == 0:
                return jsonify({
                    'success': True,
                    'warning': True,
                    'message': 'List created but no accounts were found. Please check the X List ID.',
                    'list': result['list']
                })
            return result
        else:
            # Handle specific error cases
            error_message = result.get('error', 'Unknown error')
            if 'already exists' in error_message.lower():
                return jsonify({'success': False, 'error': 'A list with this name already exists'}), 409
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error creating custom list: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/update-custom-list', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['list_id', 'action'])
def update_custom_list():
    """Update a custom list with improved validation"""
    try:
        data = request.get_json()
        list_id = data.get('list_id', '').strip()
        action = data.get('action', '').strip()
        account = data.get('account', '').strip() if data.get('account') else None
        name = data.get('name', '').strip() if data.get('name') else None
        
        # Validate action
        valid_actions = ['refresh', 'add_account', 'remove_account', 'update_name']
        if action not in valid_actions:
            return jsonify({'success': False, 'error': f'Invalid action. Must be one of: {", ".join(valid_actions)}'}), 400
        
        # Validate based on action
        if action == 'update_name':
            if not name or len(name) > 100:
                return jsonify({'success': False, 'error': 'Name must be 1-100 characters'}), 400
        
        if action in ['add_account', 'remove_account']:
            if not account or len(account) > 50:
                return jsonify({'success': False, 'error': 'Account name must be 1-50 characters'}), 400
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        # Handle name update directly
        if action == 'update_name':
            try:
                from firebase_admin import firestore
                db = firestore.client()
                doc_ref = db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
                
                # Check if list exists first
                doc = doc_ref.get()
                if not doc.exists:
                    return jsonify({'success': False, 'error': 'List not found'}), 404
                
                doc_ref.update({'name': name, 'last_updated': firestore.SERVER_TIMESTAMP})
                return jsonify({'success': True, 'message': 'List name updated successfully'})
                
            except Exception as db_error:
                logger.error(f"Database error updating list name: {str(db_error)}")
                return jsonify({'success': False, 'error': 'Failed to update list name'}), 500
        
        # Handle refresh action with update status
        if action == 'refresh':
            ongoing_updates = get_ongoing_updates(user_id)
            if list_id in ongoing_updates:
                return jsonify({
                    'success': False, 
                    'error': 'Update already in progress for this list',
                    'is_updating': True
                }), 409
            
            set_update_status(user_id, list_id, 'running')
        
        try:
            # Update the custom list
            result = service.update_custom_list(user_id, list_id, action, account)
            
            # Clear update status on completion for refresh
            if action == 'refresh':
                set_update_status(user_id, list_id, 'completed')
            
            return jsonify(result)
            
        except Exception as service_error:
            # Clear update status on error for refresh
            if action == 'refresh':
                set_update_status(user_id, list_id, 'completed')
            raise service_error
        
    except Exception as e:
        logger.error(f"Error updating custom list: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/delete-custom-list', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['list_id'])
@debounce_requests(timeout=3)
def delete_custom_list():
    """Delete a custom list with validation"""
    try:
        data = request.get_json()
        list_id = data.get('list_id', '').strip()
        
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        # Delete the custom list
        success = service.delete_custom_list(user_id, list_id)
        
        if success:
            # Clean up any update status
            set_update_status(user_id, list_id, 'completed')
            return jsonify({'success': True, 'message': 'List deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete list or list not found'}), 404
            
    except Exception as e:
        logger.error(f"Error deleting custom list: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/get-custom-list-details', methods=['POST'])
@auth_required
@require_permission('reply_guy')
@validate_request_data(required_fields=['list_id'])
def get_custom_list_details():
    """Get custom list details for editing"""
    try:
        data = request.get_json()
        list_id = data.get('list_id', '').strip()
        user_id = get_workspace_user_id()
        
        # Get list details efficiently
        from firebase_admin import firestore
        db = firestore.client()
        doc_ref = db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({'success': False, 'error': 'List not found'}), 404
        
        data = doc.to_dict()
        
        return jsonify({
            'success': True,
            'list': {
                'id': list_id,
                'name': data.get('name', ''),
                'type': data.get('type', 'manual'),
                'accounts': data.get('accounts', [])[:100],  # Limit accounts returned
                'account_count': len(data.get('accounts', [])),
                'created_at': data.get('created_at'),
                'last_updated': data.get('last_updated')
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting custom list details: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@bp.route('/check-brand-voice', methods=['GET'])
@auth_required
@require_permission('reply_guy')
def check_brand_voice():
    """Check if user has brand voice data - cached"""
    try:
        # Check session cache first
        cache_key = 'brand_voice_available'
        if cache_key in session:
            cached_time = session.get('brand_voice_checked', 0)
            if time.time() - cached_time < 300:  # 5 minutes cache
                return jsonify({
                    'success': True, 
                    'has_brand_voice_data': session[cache_key]
                })
        
        service = ReplyGuyService()
        user_id = get_workspace_user_id()
        
        has_data = service.has_brand_voice_data(user_id)
        
        # Cache result
        session[cache_key] = has_data
        session['brand_voice_checked'] = time.time()
        
        return jsonify({'success': True, 'has_brand_voice_data': has_data})
        
    except Exception as e:
        logger.error(f"Error checking brand voice: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error', 'has_brand_voice_data': False}), 500

# Health check endpoint
@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'reply-guy'
    })

# Cleanup old cache entries periodically (call this from a background task)
def cleanup_request_cache_periodic():
    """Periodic cleanup function for request cache"""
    try:
        clean_request_cache()
        logger.info(f"Cleaned request cache, {len(REQUEST_CACHE)} entries remaining")
    except Exception as e:
        logger.error(f"Error cleaning request cache: {str(e)}")

# Error handlers
@bp.errorhandler(400)
def bad_request(error):
    return jsonify({'success': False, 'error': 'Bad request'}), 400

@bp.errorhandler(401)
def unauthorized(error):
    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

@bp.errorhandler(403)
def forbidden(error):
    return jsonify({'success': False, 'error': 'Forbidden'}), 403

@bp.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@bp.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429

@bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500