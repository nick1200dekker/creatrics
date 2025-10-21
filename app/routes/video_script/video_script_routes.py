from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_script.video_script import VideoScriptGenerator
from app.system.services.firebase_service import db
from firebase_admin import firestore
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-script')
@auth_required
@require_permission('video_script')
def video_script():
    """Video script generator page"""
    return render_template('video_script/index.html')

@bp.route('/api/generate-video-script', methods=['POST'])
@auth_required
@require_permission('video_script')
def generate_video_script():
    """Generate video script using AI with proper credit management"""
    try:
        data = request.json
        concept = data.get('concept', '').strip()
        video_type = data.get('videoType', 'long')  # 'long' or 'short'
        script_format = data.get('scriptFormat', 'full')  # 'full' or 'bullet'
        duration = data.get('duration', 10 if video_type == 'long' else 30)  # Default durations

        if not concept:
            return jsonify({'success': False, 'error': 'Please provide a video concept or topic'}), 400

        # Initialize managers
        credits_manager = CreditsManager()
        script_generator = VideoScriptGenerator()

        user_id = get_workspace_user_id()

        # Step 1: Check credits before generation
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=concept,
            model_name=None  # Uses current AI provider model  # Default model
        )

        # Scripts cost more than titles (more output)
        required_credits = cost_estimate['final_cost'] * 3  # Multiply by 3 for longer output
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        # Check for sufficient credits - strict enforcement
        if not credit_check.get('sufficient', False):
            return jsonify({
                "success": False,
                "error": f"Insufficient credits. Required: {required_credits:.2f}, Available: {current_credits:.2f}",
                "error_type": "insufficient_credits",
                "current_credits": current_credits,
                "required_credits": required_credits
            }), 402

        # Step 2: Generate script
        generation_result = script_generator.generate_script(
            concept=concept,
            video_type=video_type,
            script_format=script_format,
            duration=duration,
            user_id=user_id
        )

        if not generation_result.get('success'):
            return jsonify({
                "success": False,
                "error": generation_result.get('error', 'Script generation failed')
            }), 500

        # Step 3: Deduct credits if AI was used
        if generation_result.get('used_ai', False):
            token_usage = generation_result.get('token_usage', {})

            # Only deduct if we have real token usage
            if token_usage.get('input_tokens', 0) > 0:
                deduction_result = credits_manager.deduct_llm_credits(
                    user_id=user_id,
                    model_name=token_usage.get('model', None),  # Uses current AI provider model
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    description=f"Video Script Generation ({video_type}/{script_format})",
                    provider_enum=token_usage.get('provider_enum')
                )

                if not deduction_result['success']:
                    logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        return jsonify({
            'success': True,
            'script': generation_result.get('script'),
            'message': 'Script generated successfully',
            'used_ai': generation_result.get('used_ai', False)
        })

    except Exception as e:
        logger.error(f"Error generating video script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Legacy endpoint compatibility
@bp.route('/api/video-script/generate', methods=['POST'])
@auth_required
@require_permission('video_script')
def generate_video_script_legacy():
    """Legacy endpoint - redirects to new endpoint"""
    return generate_video_script()

@bp.route('/api/video-script/save', methods=['POST'])
@auth_required
@require_permission('video_script')
def save_video_script():
    """Save video script to Firebase"""
    try:
        data = request.json
        user_id = get_workspace_user_id()

        # Get required fields
        title = data.get('title', '').strip()
        script_content = data.get('script', '')
        video_type = data.get('videoType', 'long')
        script_format = data.get('scriptFormat', 'full')
        duration = data.get('duration')
        concept = data.get('concept', '')

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        if not script_content:
            return jsonify({'success': False, 'error': 'Script content is required'}), 400

        # Create script document
        now = datetime.now(timezone.utc)

        script_data = {
            'title': title,
            'script': script_content,
            'video_type': video_type,
            'script_format': script_format,
            'duration': duration,
            'concept': concept,
            'created_at': now,
            'updated_at': now
        }

        # Save to Firebase
        scripts_ref = db.collection('users').document(user_id).collection('yt_scripts')
        doc_ref = scripts_ref.add(script_data)

        # Get the document ID
        if isinstance(doc_ref, tuple):
            doc_id = doc_ref[1].id
        else:
            doc_id = doc_ref.id

        return jsonify({
            'success': True,
            'script_id': doc_id,
            'message': 'Script saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving video script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-script/list', methods=['GET'])
@auth_required
@require_permission('video_script')
def list_video_scripts():
    """Get all saved video scripts for the user"""
    try:
        user_id = get_workspace_user_id()

        # Get all scripts from Firebase
        scripts_ref = db.collection('users').document(user_id).collection('yt_scripts')
        scripts = scripts_ref.order_by('created_at', direction=firestore.Query.DESCENDING).stream()

        scripts_list = []
        for script in scripts:
            script_data = script.to_dict()
            script_data['id'] = script.id

            # Convert timestamps to ISO format
            if script_data.get('created_at'):
                script_data['created_at'] = script_data['created_at'].isoformat()
            if script_data.get('updated_at'):
                script_data['updated_at'] = script_data['updated_at'].isoformat()

            scripts_list.append(script_data)

        return jsonify({
            'success': True,
            'scripts': scripts_list
        })

    except Exception as e:
        logger.error(f"Error listing video scripts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-script/<script_id>', methods=['GET'])
@auth_required
@require_permission('video_script')
def get_video_script(script_id):
    """Get a specific video script"""
    try:
        user_id = get_workspace_user_id()

        # Get script from Firebase
        script_ref = db.collection('users').document(user_id).collection('yt_scripts').document(script_id)
        script = script_ref.get()

        if not script.exists:
            return jsonify({'success': False, 'error': 'Script not found'}), 404

        script_data = script.to_dict()
        script_data['id'] = script.id

        # Convert timestamps to ISO format
        if script_data.get('created_at'):
            script_data['created_at'] = script_data['created_at'].isoformat()
        if script_data.get('updated_at'):
            script_data['updated_at'] = script_data['updated_at'].isoformat()

        return jsonify({
            'success': True,
            'script': script_data
        })

    except Exception as e:
        logger.error(f"Error getting video script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-script/<script_id>', methods=['DELETE'])
@auth_required
@require_permission('video_script')
def delete_video_script(script_id):
    """Delete a video script"""
    try:
        user_id = get_workspace_user_id()

        # Delete script from Firebase
        script_ref = db.collection('users').document(user_id).collection('yt_scripts').document(script_id)
        script_ref.delete()

        return jsonify({
            'success': True,
            'message': 'Script deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting video script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-script/<script_id>', methods=['PUT'])
@auth_required
@require_permission('video_script')
def update_video_script(script_id):
    """Update a video script"""
    try:
        data = request.json
        user_id = get_workspace_user_id()

        # Get script reference
        script_ref = db.collection('users').document(user_id).collection('yt_scripts').document(script_id)

        # Check if script exists
        if not script_ref.get().exists:
            return jsonify({'success': False, 'error': 'Script not found'}), 404

        # Update data
        now = datetime.now(timezone.utc)
        update_data = {
            'updated_at': now
        }

        # Add optional fields if provided
        if 'title' in data:
            update_data['title'] = data['title']
        if 'script' in data:
            update_data['script'] = data['script']
        if 'concept' in data:
            update_data['concept'] = data['concept']

        # Update in Firebase
        script_ref.update(update_data)

        return jsonify({
            'success': True,
            'message': 'Script updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating video script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500