"""
Clean Routes for Post Editor
Thin controllers that delegate to appropriate services
NO business logic here - just HTTP handling
ADDED: Pagination support with offset/limit for loading more drafts
"""
from flask import render_template, request, jsonify, current_app, g
import uuid
import json
from datetime import datetime

from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.services.firebase_service import UserService
from app.scripts.accounts.x_analytics import XAnalytics

def get_user_posts_collection():
    """Get the user's posts collection reference"""
    user_id = get_workspace_user_id()
    try:
        from firebase_admin import firestore
        db = firestore.client()
        return db.collection('users').document(str(user_id)).collection('post_drafts')
    except Exception as e:
        current_app.logger.error(f"Error getting Firestore client: {e}")
        raise

def get_user_drafts_safe(user_id, limit=20, offset=0):
    """Safely get user drafts with pagination support"""
    try:
        collection = get_user_posts_collection()
        
        # Build query with offset support
        query = collection.order_by('timestamp', direction='DESCENDING')
        
        # Apply offset if provided
        if offset > 0:
            # Get the document at the offset position to use as startAfter
            offset_query = collection.order_by('timestamp', direction='DESCENDING').limit(offset)
            offset_docs = list(offset_query.stream())
            if offset_docs:
                last_doc = offset_docs[-1]
                query = query.start_after(last_doc)
        
        # Apply limit
        query = query.limit(limit)
        
        drafts = []
        for doc in query.stream():
            draft_data = doc.to_dict()
            draft_data['id'] = doc.id
            
            # PERFORMANCE OPTIMIZATION: Don't update media URLs on list view
            # Media URLs will be updated only when individual draft is opened
            # This prevents expensive Firebase Storage API calls for ALL drafts on page load
            
            drafts.append(draft_data)
        
        return drafts
        
    except Exception as e:
        current_app.logger.error(f"Error getting user drafts: {str(e)}")
        return []

def get_total_drafts_count(user_id):
    """Get total count of user's drafts"""
    try:
        collection = get_user_posts_collection()
        
        # Count all drafts for the user
        docs = list(collection.stream())
        return len(docs)
        
    except Exception as e:
        current_app.logger.error(f"Error counting drafts: {str(e)}")
        return 0

def update_media_urls_in_posts(user_id: str, posts: list):
    """Update media URLs in posts to ensure they don't expire"""
    from app.scripts.post_editor.post_editor import PostEditor
    editor = PostEditor()
    
    for post in posts:
        if 'media' in post and isinstance(post['media'], list):
            for item in post['media']:
                if isinstance(item, dict) and 'filename' in item:
                    item['url'] = editor.generate_public_media_url(user_id, item['filename'])

@bp.route('/')
@bp.route('/x_post_editor')  # Add alias route for base template compatibility
@auth_required
@require_permission('x_post_editor')
def index():
    """Main Post Editor view with pagination support"""
    try:
        user_id = get_workspace_user_id()
        # Get first 10 drafts and total count for initial load
        recent_drafts = get_user_drafts_safe(user_id, limit=10, offset=0)
        total_count = get_total_drafts_count(user_id)

        # Determine if there are more drafts to load
        has_more = len(recent_drafts) < total_count

        # Get user data for template, including x_account if available
        user_data = g.user.copy() if hasattr(g, 'user') else {}

        # Try to get x_account from Firebase if not in g.user
        if 'x_account' not in user_data:
            try:
                from firebase_admin import firestore
                db = firestore.client()
                user_doc = db.collection('users').document(str(user_id)).get()
                if user_doc.exists:
                    firebase_user = user_doc.to_dict()
                    user_data['x_account'] = firebase_user.get('x_account', '')
            except Exception as e:
                current_app.logger.warning(f"Could not fetch x_account: {e}")
                user_data['x_account'] = ''

        return render_template('x_post_editor/index.html',
                             recent_drafts=recent_drafts,
                             total_count=total_count,
                             has_more=has_more,
                             loaded_count=len(recent_drafts),
                             user=user_data)
    except Exception as e:
        current_app.logger.error(f"Error loading post editor page: {str(e)}")
        # Get user data for template
        user_data = g.user if hasattr(g, 'user') else {}

        return render_template('x_post_editor/index.html',
                             recent_drafts=[],
                             total_count=0,
                             has_more=False,
                             loaded_count=0,
                             user=user_data)

# Add alias function for base template compatibility
@bp.route('/editor')
@auth_required
@require_permission('x_post_editor')
def x_post_editor():
    """Alias for the main post editor - for base template compatibility"""
    return index()

@bp.route('/drafts', methods=['GET'])
@auth_required
@require_permission('x_post_editor')
def get_drafts():
    """Get drafts for the current user with pagination support"""
    try:
        user_id = get_workspace_user_id()
        
        # Get pagination parameters
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 20))
        
        # Validate parameters
        if offset < 0:
            offset = 0
        if limit < 1 or limit > 50:  # Max 50 per request
            limit = 20
        
        drafts = get_user_drafts_safe(user_id, limit=limit, offset=offset)
        total_count = get_total_drafts_count(user_id)
        
        # Calculate if there are more drafts to load
        has_more = (offset + len(drafts)) < total_count
        
        return jsonify({
            "success": True,
            "drafts": drafts,
            "offset": offset,
            "limit": limit,
            "total_count": total_count,
            "has_more": has_more,
            "loaded_count": offset + len(drafts)
        })
    except Exception as e:
        current_app.logger.error(f"Error getting drafts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/drafts/<draft_id>', methods=['GET'])
@auth_required
@require_permission('x_post_editor')
def get_draft(draft_id):
    """Get a specific draft by ID"""
    try:
        user_id = get_workspace_user_id()
        current_app.logger.info(f"Loading draft {draft_id} for user {user_id}")
        
        collection = get_user_posts_collection()
        current_app.logger.info(f"Got collection reference for user {user_id}")
        
        doc = collection.document(draft_id).get()
        current_app.logger.info(f"Retrieved document {draft_id}, exists: {doc.exists}")
        
        if not doc.exists:
            current_app.logger.warning(f"Draft {draft_id} not found for user {user_id}")
            return jsonify({
                "success": False,
                "error": "Draft not found"
            }), 404
        
        draft_data = doc.to_dict()
        draft_data['id'] = doc.id
        current_app.logger.info(f"Draft data keys: {list(draft_data.keys())}")
        
        # Update media URLs to ensure they don't expire
        if 'posts' in draft_data and isinstance(draft_data['posts'], list):
            current_app.logger.info(f"Updating media URLs for {len(draft_data['posts'])} posts")
            update_media_urls_in_posts(user_id, draft_data['posts'])
        
        current_app.logger.info(f"Successfully loaded draft {draft_id}")
        return jsonify({
            "success": True,
            "draft": draft_data
        })
    except Exception as e:
        current_app.logger.error(f"Error reading draft {draft_id}: {str(e)}")
        import traceback
        current_app.logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/drafts/<draft_id>/pre-ai-version', methods=['GET'])
@auth_required
@require_permission('x_post_editor')
def get_pre_ai_version(draft_id):
    """Get the pre-AI version of a draft for revert functionality"""
    try:
        from app.scripts.post_editor.post_editor import PostEditor
        
        editor = PostEditor()
        user_id = get_workspace_user_id()
        
        pre_ai_posts = editor.get_pre_ai_version(user_id, draft_id)
        
        # Update media URLs in pre-AI version too
        if pre_ai_posts:
            update_media_urls_in_posts(user_id, pre_ai_posts)
        
        return jsonify({
            "success": True,
            "pre_ai_posts": pre_ai_posts
        })
    except Exception as e:
        current_app.logger.error(f"Error getting pre-AI version for draft {draft_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "pre_ai_posts": []
        }), 500

@bp.route('/drafts/new', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def create_new_draft():
    """Create a new empty draft"""
    try:
        collection = get_user_posts_collection()
        
        data = request.json or {}
        title = data.get('title', 'New Draft')
        
        draft_data = {
            "title": title,
            "posts": [{"text": "", "media": []}],  # Unified to media field only
            "input_text": "",
            "output_text": "",
            "preset": "keyword",
            "additional_context": "",
            "timestamp": datetime.now(),
            "permanent": True
        }
        
        doc_ref = collection.add(draft_data)[1]
        
        return jsonify({
            "success": True,
            "draft_id": doc_ref.id
        })
    except Exception as e:
        current_app.logger.error(f"Error creating new draft: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/drafts/<draft_id>', methods=['DELETE'])
@auth_required
@require_permission('x_post_editor')
def delete_draft(draft_id):
    """Delete a specific draft and all its versions"""
    try:
        from firebase_admin import firestore
        from app.scripts.post_editor.post_editor import PostEditor
        
        user_id = get_workspace_user_id()
        db = firestore.client()
        editor = PostEditor()
        
        collection = get_user_posts_collection()
        doc_ref = collection.document(draft_id)
        
        if not doc_ref.get().exists:
            return jsonify({
                "success": False,
                "error": "Draft not found"
            }), 404
        
        # Get draft data to find media that needs to be deleted
        draft_doc = doc_ref.get()
        if draft_doc.exists:
            draft_data = draft_doc.to_dict()
            
            # Delete associated media from storage
            if 'posts' in draft_data and isinstance(draft_data['posts'], list):
                for post in draft_data['posts']:
                    if 'media' in post and isinstance(post['media'], list):
                        for item in post['media']:
                            if isinstance(item, dict) and 'filename' in item:
                                try:
                                    editor.delete_media_from_storage(user_id, item['filename'])
                                except Exception as media_error:
                                    current_app.logger.warning(f"Failed to delete media {item['filename']}: {media_error}")
        
        # Delete all versions subcollection documents first
        try:
            versions_ref = doc_ref.collection('versions')
            versions_docs = versions_ref.stream()
            
            for version_doc in versions_docs:
                version_doc.reference.delete()
                current_app.logger.info(f"Deleted version {version_doc.id} for draft {draft_id}")
        except Exception as version_error:
            current_app.logger.warning(f"Error deleting versions for draft {draft_id}: {version_error}")
        
        doc_ref.delete()
        
        return jsonify({
            "success": True
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting draft {draft_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/upload-media', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def upload_media():
    """Upload media files (images, videos, GIFs) using Firebase Storage"""
    try:
        data = request.json
        media_data = data.get('media_data')
        filename = data.get('filename')
        media_type = data.get('media_type')
        file_size = data.get('file_size', 0)
        mime_type = data.get('mime_type', '')
        
        if not media_data:
            return jsonify({
                "success": False,
                "error": "No media data provided"
            }), 400
        
        # Validate file size limits
        size_limits = {
            'image': 10 * 1024 * 1024,  # 10MB
            'video': 100 * 1024 * 1024,  # 100MB
            'gif': 25 * 1024 * 1024     # 25MB
        }
        
        max_size = size_limits.get(media_type, 10 * 1024 * 1024)
        if file_size > max_size:
            return jsonify({
                "success": False,
                "error": f"File too large. Maximum size for {media_type}: {max_size // (1024*1024)}MB"
            }), 400
        
        from app.scripts.post_editor.post_editor import PostEditor
        
        editor = PostEditor()
        
        media_url = editor.save_media_to_storage(
            user_id=get_workspace_user_id(),
            media_data=media_data,
            filename=filename,
            media_type=media_type,
            mime_type=mime_type
        )
        
        if media_url:
            current_app.logger.info(f"Media uploaded successfully: {filename} -> {media_url}")
            return jsonify({
                "success": True,
                "media_url": media_url,
                "filename": filename,
                "media_type": media_type
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save media"
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error uploading media: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/delete-media', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def delete_media():
    """Delete media files from Firebase Storage"""
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({
                "success": False,
                "error": "No filename provided"
            }), 400
        
        from app.scripts.post_editor.post_editor import PostEditor
        editor = PostEditor()
        
        success = editor.delete_media_from_storage(get_workspace_user_id(), filename)
        
        if success:
            return jsonify({
                "success": True
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to delete media"
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error deleting media: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Legacy endpoints for backward compatibility (redirect to new media endpoints)
@bp.route('/upload-image', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def upload_image():
    """Legacy image upload endpoint - redirects to media upload"""
    try:
        data = request.json
        image_data = data.get('image_data')
        filename = data.get('filename')
        
        if not image_data:
            return jsonify({
                "success": False,
                "error": "No image data provided"
            }), 400
        
        # Convert legacy request to new format
        new_request_data = {
            'media_data': image_data,
            'filename': filename,
            'media_type': 'image',
            'mime_type': 'image/jpeg',
            'file_size': 0
        }
        
        # Use the main media upload logic
        from flask import Request
        with current_app.test_request_context(json=new_request_data):
            result = upload_media()
            
            # Convert response format for backward compatibility
            if isinstance(result, tuple):
                response_data, status_code = result
                response_json = response_data.get_json()
            else:
                response_json = result.get_json()
                status_code = 200
            
            if response_json.get('success'):
                return jsonify({
                    "success": True,
                    "image_url": response_json.get('media_url'),
                    "filename": response_json.get('filename')
                })
            else:
                return jsonify(response_json), status_code
            
    except Exception as e:
        current_app.logger.error(f"Error in legacy image upload: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/delete-image', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def delete_image():
    """Legacy image delete endpoint - redirects to media delete"""
    return delete_media()  # Same logic, just different endpoint name

@bp.route('/save', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def save_draft():
    """Save a draft with complete post data including media and update timestamp for reordering"""
    try:
        collection = get_user_posts_collection()
        
        data = request.json
        draft_id = data.get('draft_id')
        posts = data.get('posts', [])
        preset = data.get('preset', 'braindump')
        additional_context = data.get('additional_context', '')
        
        # Store pre-AI version before any potential AI enhancement
        if draft_id and draft_id != 'new':
            try:
                from app.scripts.post_editor.post_editor import PostEditor
                editor = PostEditor()
                editor.store_pre_ai_version(get_workspace_user_id(), draft_id, posts)
            except Exception as pre_ai_error:
                current_app.logger.warning(f"Failed to store pre-AI version: {pre_ai_error}")
        
        # Process and clean up media data (unified to single media field)
        for i, post in enumerate(posts):
            # Consolidate all media into single 'media' field
            all_media = []
            
            # Get media from both possible fields and consolidate
            for media_field in ['media', 'images']:
                if media_field in post and post[media_field]:
                    for item in post[media_field]:
                        if isinstance(item, dict):
                            all_media.append({
                                'url': item.get('url', item.get('src', '')),
                                'filename': item.get('filename', f"media_{i}"),
                                'media_type': item.get('media_type', 'image'),
                                'file_size': item.get('file_size', 0),
                                'mime_type': item.get('mime_type', '')
                            })
                        else:
                            # Handle legacy string format
                            all_media.append({
                                'url': str(item),
                                'filename': f"legacy_media_{i}",
                                'media_type': 'image',
                                'file_size': 0,
                                'mime_type': ''
                            })
            
            # Store only in unified 'media' field
            post['media'] = all_media
            # Remove legacy field if it exists
            if 'images' in post:
                del post['images']
        
        # For backward compatibility, create input_text and output_text fields
        input_text = ""
        for i, post in enumerate(posts):
            input_text += post.get('text', '')
            
            # Add media references
            for item in post.get('media', []):
                if isinstance(item, dict) and 'filename' in item:
                    media_type = item.get('media_type', 'image')
                    input_text += f"\n[{media_type.title()}: {item['filename']}]"
            
            if i < len(posts) - 1:
                input_text += "\n\n---\n\n"
        
        # Get the title from the first post's text
        title = "Untitled Draft"
        if posts and posts[0].get('text'):
            first_line = posts[0]['text'].strip().split('\n')[0]
            title = first_line[:30]
            if len(first_line) > 30:
                title += '...'
        
        draft_data = {
            "title": title,
            "posts": posts,
            "input_text": input_text,
            "output_text": input_text,
            "preset": preset,
            "additional_context": additional_context,
            "timestamp": datetime.now(),
            "permanent": True
        }
        
        # Save the draft
        if draft_id and draft_id != 'new':
            doc_ref = collection.document(draft_id)
            doc_ref.set(draft_data)
            return_draft_id = draft_id
        else:
            doc_ref = collection.add(draft_data)[1]
            return_draft_id = doc_ref.id
        
        return jsonify({
            "success": True,
            "draft_id": return_draft_id
        })
    except Exception as e:
        current_app.logger.error(f"Error saving draft: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/save-fast', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def save_draft_fast():
    """Fast save for simple content updates with timestamp update for reordering"""
    try:
        collection = get_user_posts_collection()
        
        data = request.json
        draft_id = data.get('draft_id')
        posts = data.get('posts', [])

        preset = data.get('preset', 'braindump')
        additional_context = data.get('additional_context', '')
        
        # Simple media processing for fast save - ensure media field exists
        for post in posts:
            if 'media' not in post:
                post['media'] = post.get('images', [])  # Use images if available, else empty
            # Remove legacy field
            if 'images' in post:
                del post['images']
        
        # Quick title generation
        title = "Untitled Draft"
        if posts and posts[0].get('text'):
            first_line = posts[0]['text'].strip().split('\n')[0]
            title = first_line[:30]
            if len(first_line) > 30:
                title += '...'
        
        # Minimal backward compatibility
        input_text = ""
        for i, post in enumerate(posts):
            input_text += post.get('text', '')
            if i < len(posts) - 1:
                input_text += "\n\n---\n\n"
        
        draft_data = {
            "title": title,
            "posts": posts,
            "input_text": input_text,
            "output_text": input_text,
            "preset": preset,
            "additional_context": additional_context,
            "timestamp": datetime.now(),
            "permanent": True
        }
        
        # Save the draft
        if draft_id and draft_id != 'new':
            doc_ref = collection.document(draft_id)
            doc_ref.set(draft_data)
            return_draft_id = draft_id
        else:
            doc_ref = collection.add(draft_data)[1]
            return_draft_id = doc_ref.id
        
        return jsonify({
            "success": True,
            "draft_id": return_draft_id
        })
    except Exception as e:
        current_app.logger.error(f"Error in fast save: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/estimate-cost', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def estimate_cost():
    """
    CLEAN: Estimate the cost of content generation
    Delegates ALL credit logic to CreditsManager
    """
    try:
        data = request.json
        posts = data.get('posts', [])
        preset = data.get('preset', 'braindump')
        additional_context = data.get('additional_context', '')
        voice_tone = data.get('voice_tone', 'standard')
        custom_voice_posts = data.get('custom_voice_posts', None)
        
        # Handle new custom voice format
        if voice_tone.startswith('custom:'):
            custom_voice_username = voice_tone.replace('custom:', '')
            voice_tone = 'custom'
            custom_voice_posts = custom_voice_username
        
        # Validate we have posts with content
        has_content = any(post.get('text', '').strip() for post in posts)
        if not has_content:
            return jsonify({
                "success": False,
                "error": "No content provided for cost estimation"
            }), 400
        
        # Delegate to CreditsManager for cost estimation
        from app.system.credits.credits_manager import CreditsManager
        credits_manager = CreditsManager()

        # Combine all post text for estimation
        combined_text = ""
        for post in posts:
            combined_text += post.get('text', '') + " "
        if additional_context:
            combined_text += additional_context

        # Estimate cost (uses current AI provider's model)
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=combined_text,
            model_name=None  # Will use the current AI provider's model
        )

        required_credits = cost_estimate['final_cost']
        current_credits = credits_manager.get_user_credits(get_workspace_user_id())
        has_sufficient = credits_manager.check_sufficient_credits(
            user_id=get_workspace_user_id(),
            required_credits=required_credits
        )

        return jsonify({
            "success": True,
            "estimated_cost": cost_estimate['base_cost'],
            "required_credits": required_credits,
            "current_credits": current_credits,
            "has_sufficient_credits": has_sufficient.get('sufficient', False) if isinstance(has_sufficient, dict) else has_sufficient
        })
        
    except Exception as e:
        current_app.logger.error(f"Error estimating cost: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/generate', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def generate_content():
    """
    CLEAN: Generate enhanced content using AI
    Proper separation: CreditsManager handles credits, PostEditor handles content
    """
    try:
        data = request.json
        posts = data.get('posts', [])
        preset = data.get('preset', 'braindump')
        additional_context = data.get('additional_context', '')
        voice_tone = data.get('voice_tone', 'standard')
        custom_voice_posts = data.get('custom_voice_posts', None)
        
        # Handle new custom voice format
        if voice_tone.startswith('custom:'):
            custom_voice_username = voice_tone.replace('custom:', '')
            voice_tone = 'custom'
            custom_voice_posts = custom_voice_username
        
        # Validate we have posts with content
        has_content = any(post.get('text', '').strip() for post in posts)
        if not has_content:
            return jsonify({
                "success": False,
                "error": "No content provided"
            }), 400
        
        # CLEAN: Separate credit checking and content generation
        from app.system.credits.credits_manager import CreditsManager
        from app.scripts.post_editor.post_editor import PostEditor
        
        credits_manager = CreditsManager()
        post_editor = PostEditor()
        
        user_id = get_workspace_user_id()

        # Get user subscription for AI provider selection
        user_subscription = None
        if hasattr(g, 'user') and g.user:
            # Try direct access first (set by middleware)
            user_subscription = g.user.get('subscription_plan')
            # Fallback to nested data
            if not user_subscription and 'data' in g.user:
                user_subscription = g.user['data'].get('subscription_plan')

        # Step 1: Check credits BEFORE generation
        # Combine all post text for estimation
        combined_text = ""
        for post in posts:
            combined_text += post.get('text', '') + " "
        if additional_context:
            combined_text += additional_context

        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=combined_text,
            model_name=None  # Will use the current AI provider's model
        )

        required_credits = cost_estimate['final_cost']
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": f"Insufficient credits. Required: {required_credits:.2f}, Available: {current_credits:.2f}",
                "error_type": "insufficient_credits"
            }), 402

        # Step 2: Generate content (no credit logic here)
        generation_result = post_editor.generate(
            posts=posts,
            preset=preset,
            additional_context=additional_context,
            user_id=user_id,
            voice_tone=voice_tone,
            custom_voice_posts=custom_voice_posts,
            user_subscription=user_subscription
        )
        
        if not generation_result['success']:
            return jsonify({
                "success": False,
                "error": "Content generation failed"
            }), 500
        
        # Step 3: Deduct credits based on actual usage
        token_usage = generation_result['token_usage']
        
        deduction_result = credits_manager.deduct_llm_credits(
            user_id=user_id,
            model_name=token_usage['model'],
            input_tokens=token_usage['input_tokens'],
            output_tokens=token_usage['output_tokens'],
            description=f"Post Editor enhancement ({preset}) - {len(generation_result['enhanced_posts'])} posts",
            provider_enum=token_usage.get('provider_enum')
        )
        
        if not deduction_result['success']:
            current_app.logger.error(f"Failed to deduct credits: {deduction_result['message']}")
            # Could implement rollback logic here if needed
        
        return jsonify({
            "success": True,
            "enhanced_posts": generation_result['enhanced_posts']
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating content: {str(e)}")
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while generating content. Please try again."
        }), 500

@bp.route('/fetch-x-posts', methods=['POST'])
@auth_required
@require_permission('x_post_editor')
def fetch_x_posts():
    """Fetch X posts for a given username for voice mimicking"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip().replace('@', '')
        
        if not username:
            return jsonify({
                "success": False,
                "error": "Username is required"
            }), 400

        # Initialize X Analytics
        user_id = get_workspace_user_id()
        analytics = XAnalytics(user_id=user_id)

        # Override the handle temporarily
        original_handle = analytics.x_handle
        analytics.x_handle = username

        # Fetch timeline data (limited to 15 posts for voice analysis)
        timeline_data = analytics.get_timeline_data(max_posts=15)

        # Restore original handle
        analytics.x_handle = original_handle

        if not timeline_data or len(timeline_data) == 0:
            return jsonify({
                "success": False,
                "error": "Could not fetch posts for this user. Make sure the username is correct and the account is public."
            }), 404

        posts = timeline_data

        # Extract just the text content for voice analysis
        post_texts = []
        for post in posts[:15]:
            try:
                if isinstance(post, dict):
                    # Handle dict format
                    if 'text' in post:
                        post_texts.append(post['text'])
                    elif 'content' in post:
                        post_texts.append(post['content'])
                elif isinstance(post, str):
                    # Handle string format
                    post_texts.append(post)
                elif hasattr(post, 'text'):
                    # Handle object with text attribute
                    post_texts.append(post.text)
                else:
                    # Try to convert to string as fallback
                    post_str = str(post)
                    if post_str and post_str != 'None':
                        post_texts.append(post_str)
            except Exception as e:
                current_app.logger.warning(f"Error processing post: {e}")
                continue

        if not post_texts:
            return jsonify({
                "success": False,
                "error": "No text content found in user's posts"
            }), 404

        # Store in Firebase
        try:
            from firebase_admin import firestore
            db = firestore.client()
            
            # Store in users/{user_id}/x_post_editor_voices/{username}
            voice_ref = db.collection('users').document(str(user_id)).collection('x_post_editor_voices').document(username)
            voice_ref.set({
                'username': username,
                'posts': post_texts,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            current_app.logger.info(f"Stored custom voice {username} for user {user_id}")
            
        except Exception as e:
            current_app.logger.error(f"Error storing custom voice in Firebase: {e}")
            # Continue anyway, return the posts even if storage fails

        return jsonify({
            "success": True,
            "posts": post_texts,
            "username": username
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching X posts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/custom-voices', methods=['GET'])
@auth_required
@require_permission('x_post_editor')
def get_custom_voices():
    """Get all custom voices for the current user"""
    try:
        user_id = get_workspace_user_id()
        from firebase_admin import firestore
        db = firestore.client()
        
        voices_ref = db.collection('users').document(str(user_id)).collection('x_post_editor_voices')
        voices = []
        
        for doc in voices_ref.stream():
            voice_data = doc.to_dict()
            voices.append({
                'username': voice_data.get('username'),
                'created_at': voice_data.get('created_at'),
                'post_count': len(voice_data.get('posts', []))
            })
        
        return jsonify({
            "success": True,
            "voices": voices
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting custom voices: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@bp.route('/custom-voices/<username>', methods=['DELETE'])
@auth_required
@require_permission('x_post_editor')
def delete_custom_voice(username):
    """Delete a custom voice"""
    try:
        user_id = get_workspace_user_id()
        from firebase_admin import firestore
        db = firestore.client()
        
        # Delete from Firebase
        voice_ref = db.collection('users').document(str(user_id)).collection('x_post_editor_voices').document(username)
        voice_ref.delete()
        
        current_app.logger.info(f"Deleted custom voice {username} for user {user_id}")
        
        return jsonify({
            "success": True,
            "message": f"Custom voice {username} deleted successfully"
        })
        
    except Exception as e:
        current_app.logger.error(f"Error deleting custom voice: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500