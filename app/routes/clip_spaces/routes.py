from flask import render_template, request, jsonify, g, redirect, Response, session
import os
import json
import tempfile
import logging
import traceback
import zipfile
import threading
import time
from datetime import datetime

from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import require_permission, get_workspace_user_id
from app.system.credits.credits_manager import CreditsManager
from app.scripts.clip_spaces.processor import SpaceProcessor
from app.system.services.firebase_service import StorageService

logger = logging.getLogger(__name__)

# Global dictionary to track processing status
processing_status = {}

@bp.route('/')
@auth_required
@require_permission('clip_spaces')
def index():
    """Main Spaces index page"""
    user_id = get_workspace_user_id()
    logger.info(f"[SPACES] User {user_id} accessing Spaces index page")

    try:
        user_id = str(user_id)
        
        # Get list of previously processed spaces from Firebase Storage
        processed_spaces = []
        
        try:
            # List files from 'data' directory
            files = StorageService.list_files(user_id, 'data')
            logger.info(f"[SPACES] Found {len(files)} total files")
            
            # Group files by space_id and look for metadata files
            space_ids = set()
            for file in files:
                file_name = file.get('name', '')
                
                # Look for spaces metadata files: spaces/space_id/metadata.json
                if file_name.startswith('spaces/') and file_name.endswith('/metadata.json'):
                    # Extract space_id from path like spaces/1DXxyqODqyRxM/metadata.json
                    path_parts = file_name.split('/')
                    if len(path_parts) == 3:  # spaces/space_id/metadata.json
                        space_id = path_parts[1]
                        space_ids.add(space_id)
                        logger.info(f"[SPACES] Found space: {space_id}")
            
            logger.info(f"[SPACES] Found {len(space_ids)} space IDs: {list(space_ids)}")
            
            # Load metadata for each space
            for space_id in space_ids:
                try:
                    metadata_path = f"spaces/{space_id}/metadata.json"
                    metadata_content = StorageService.get_file_content(user_id, 'data', metadata_path)
                    
                    if metadata_content:
                        if isinstance(metadata_content, str):
                            metadata = json.loads(metadata_content)
                        else:
                            metadata = metadata_content
                            
                        # Extract title from creator info or use default
                        title = "Twitter Space"
                        if metadata.get('creator'):
                            title = metadata['creator'].get('display_name', 'Twitter Space')
                        elif metadata.get('title'):
                            title = metadata['title']
                        
                        # Format the date properly
                        created_at = metadata.get('started', 0)
                        formatted_date = "Unknown"
                        
                        if created_at:
                            try:
                                # Convert timestamp to datetime and format
                                from datetime import datetime
                                if isinstance(created_at, str):
                                    # If it's a string timestamp, convert to int
                                    created_at = int(created_at)
                                
                                # Handle both seconds and milliseconds timestamps
                                if created_at > 10**10:  # Milliseconds timestamp
                                    dt = datetime.fromtimestamp(created_at / 1000)
                                else:  # Seconds timestamp
                                    dt = datetime.fromtimestamp(created_at)
                                
                                formatted_date = dt.strftime("%b %d, %Y at %I:%M %p")
                                
                            except (ValueError, TypeError) as e:
                                logger.warning(f"[SPACES] Error formatting date for space {space_id}: {e}")
                                formatted_date = "Unknown"
                        
                        processed_spaces.append({
                            'space_id': space_id,
                            'title': title,
                            'created_at': created_at,
                            'formatted_date': formatted_date,
                        })
                        
                        logger.info(f"[SPACES] Loaded space: {space_id} - {title}")
                        
                except Exception as e:
                    logger.warning(f"[SPACES] Error loading metadata for space {space_id}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"[SPACES] Error listing spaces for user {user_id}: {e}")
        
        # Sort by creation time (newest first)
        processed_spaces.sort(key=lambda x: x['created_at'], reverse=True)
        
        logger.info(f"[SPACES] Returning {len(processed_spaces)} processed spaces")
        
        return render_template('clip_spaces/index.html', processed_spaces=processed_spaces)
        
    except Exception as e:
        logger.error(f"[SPACES] Error loading spaces index: {e}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        return render_template('clip_spaces/index.html', processed_spaces=[])

@bp.route('/status/<space_id>')
@auth_required
@require_permission('clip_spaces')
def get_processing_status(space_id):
    """Get processing status for a space"""
    user_id = str(get_workspace_user_id())
    status_key = f"{user_id}_{space_id}"
    
    status = processing_status.get(status_key, {
        'status': 'not_started',
        'message': 'Ready to process',
        'progress': 0,
        'error': None
    })
    
    return jsonify(status)

@bp.route('/check_processing')
@auth_required
@require_permission('clip_spaces')
def check_any_processing():
    """Check if user has any spaces currently processing"""
    user_id = str(get_workspace_user_id())
    
    # Check all status keys for this user
    for status_key, status_data in processing_status.items():
        if status_key.startswith(f"{user_id}_") and status_data.get('status') == 'processing':
            space_id = status_key.replace(f"{user_id}_", "")
            return jsonify({
                'has_active_process': True,
                'space_id': space_id,
                'status': status_data
            })
    
    return jsonify({'has_active_process': False})

def update_processing_status(user_id, space_id, message, progress, error=None, status='processing'):
    """Update processing status"""
    status_key = f"{user_id}_{space_id}"
    processing_status[status_key] = {
        'status': status,
        'message': message,
        'progress': progress,
        'error': error,
        'timestamp': time.time()
    }

def process_space_async(space_id, user_id):
    """Process space asynchronously"""
    try:
        def status_callback(message, progress):
            update_processing_status(user_id, space_id, message, progress)
        
        # Initialize services
        credits_manager = CreditsManager()
        processor = SpaceProcessor(space_id, user_id, status_callback)
        
        # Fetch space data
        space_data = processor.fetch_space_data()
        
        # Estimate transcription cost
        update_processing_status(user_id, space_id, "💰 Calculating costs...", 45)
        
        # Download audio first to get duration for cost estimation
        audio_duration = processor.download_and_get_duration(space_data['playlist'])
        
        # Calculate cost based on duration (in minutes)
        duration_minutes = audio_duration / 60.0
        
        # Estimate transcription cost (0.5 credits per minute)
        transcription_cost = duration_minutes * 0.5

        # Check if user has sufficient credits
        current_credits = credits_manager.get_user_credits(user_id)
        if current_credits < transcription_cost:
            update_processing_status(user_id, space_id, f"❌ Insufficient credits", 0,
                                   f"Need {transcription_cost:.2f} credits, have {current_credits:.2f}", 'error')
            return
        
        # Estimate summary cost based on audio duration
        estimated_transcript_length = int(duration_minutes * 150)  # ~150 words per minute
        summary_cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content='x' * estimated_transcript_length,
            model_name='gpt-4.1'
        )
        
        total_estimated_cost = transcription_cost + summary_cost_estimate['final_cost']
        
        # Check if user has sufficient credits for total operation
        credit_check = credits_manager.check_sufficient_credits(user_id, total_estimated_cost)
        
        if not credit_check['sufficient']:
            update_processing_status(user_id, space_id, 
                                   f"❌ Insufficient credits: {total_estimated_cost} required, {credit_check['current_credits']} available", 
                                   0, "insufficient_credits", 'error')
            return
        
        # Process the space
        transcript_data, actual_tokens = processor.transcribe_audio()
        
        # Extract display transcript for storage
        if isinstance(transcript_data, tuple):
            structured_segments, display_transcript = transcript_data
        else:
            # Fallback for legacy format
            display_transcript = transcript_data
        
        # Deduct actual transcription cost
        transcription_deduction = credits_manager.deduct_credits(
            user_id=user_id,
            amount=transcription_cost,
            description=f"Twitter Space transcription - {space_id}",
            feature_id='clip_spaces'
        )
        
        if not transcription_deduction['success']:
            logger.error(f"Failed to deduct transcription credits: {transcription_deduction['message']}")
        
        # Generate enhanced summary with quotes and highlights
        summary, summary_tokens = processor.generate_summary(transcript_data)
        
        # Deduct actual summary cost (simplified)
        summary_deduction = credits_manager.deduct_credits(
            user_id=user_id,
            amount=summary_cost_estimate['final_cost'],
            description=f"Twitter Space summary - {space_id}",
            feature_id='clip_spaces'
        )
        
        if not summary_deduction['success']:
            logger.error(f"Failed to deduct summary credits: {summary_deduction['message']}")
        
        # Save processed data to Firebase Storage
        update_processing_status(user_id, space_id, "💾 Saving results...", 98)
        
        space_storage_path = f"spaces/{space_id}"
        
        # Save metadata
        metadata_path = f"{space_storage_path}/metadata.json"
        StorageService.save_file_content(user_id, 'data', metadata_path, space_data)
        
        # Save transcript
        transcript_path = f"{space_storage_path}/transcript.txt"
        StorageService.save_file_content(user_id, 'data', transcript_path, display_transcript)
        
        # Save summary
        summary_path = f"{space_storage_path}/summary.md"
        StorageService.save_file_content(user_id, 'data', summary_path, summary)
        
        # Save audio file to Firebase Storage
        audio_storage_path = f"{space_storage_path}/audio.mp3"
        with open(processor.audio_path, 'rb') as audio_file:
            StorageService.save_file_content(user_id, 'data', audio_storage_path, audio_file.read())
        
        # Create the result object
        result = {
            'success': True,
            'space_id': space_id,
            'space_info': space_data,
            'audio_url': f"/clip-spaces/audio/{space_id}",
            'transcript': display_transcript,
            'summary': summary,
            'processing_cost': {
                'transcription': transcription_cost,
                'summary': summary_cost_estimate['final_cost'],
                'total': transcription_cost + summary_cost_estimate['final_cost']
            }
        }
        
        # Save complete result
        result_path = f"{space_storage_path}/data.json"
        StorageService.save_file_content(user_id, 'data', result_path, result)
        
        # Mark as completed
        update_processing_status(user_id, space_id, "✅ Processing completed successfully!", 100, None, 'completed')
        
        logger.info(f"[SPACES] Processing completed successfully for space_id: {space_id}")
        
    except Exception as e:
        error_msg = f"Error processing Space: {str(e)}"
        logger.error(f"[SPACES] {error_msg}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        
        update_processing_status(user_id, space_id, f"❌ {error_msg}", 0, str(e), 'error')
    
    finally:
        # Always clean up temporary files
        if 'processor' in locals():
            processor.clean_up()

@bp.route('/process', methods=['POST'])
@auth_required
@require_permission('clip_spaces')
def process_space():
    """Process a Twitter Space"""
    space_id = request.form.get('space_id')
    user_id = str(get_workspace_user_id())
    
    logger.info(f"[SPACES] User {user_id} processing Space ID: {space_id}")
    
    if not space_id:
        logger.error(f"[SPACES] No Space ID provided by user {user_id}")
        return jsonify({'success': False, 'error': 'No Space ID provided'}), 400
    
    # Check if already processing
    status_key = f"{user_id}_{space_id}"
    current_status = processing_status.get(status_key, {}).get('status')
    
    if current_status == 'processing':
        return jsonify({'success': False, 'error': 'Space is already being processed'}), 400
    
    # Initialize processing status
    update_processing_status(user_id, space_id, "🚀 Starting processing...", 5, None, 'processing')
    
    # Start processing in background thread
    thread = threading.Thread(target=process_space_async, args=(space_id, user_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Processing started',
        'space_id': space_id
    }), 202

@bp.route('/audio/<space_id>')
@auth_required
@require_permission('clip_spaces')
def get_audio(space_id):
    """Stream audio file for a space with proper CORS headers"""
    user_id = str(get_workspace_user_id())
    logger.info(f"[SPACES] User {user_id} requesting audio for space_id: {space_id}")
    
    try:
        # Check if the audio file exists
        audio_path = f"spaces/{space_id}/audio.mp3"
        full_path = f'users/{user_id}/data/{audio_path}'
        
        # Get the Firebase Storage bucket from the module
        from app.system.services.firebase_service import bucket
        if not bucket:
            logger.error("[SPACES] Firebase Storage not initialized")
            return Response("Storage service unavailable", status=503, mimetype='text/plain')
        
        # Check if the file exists
        blob = bucket.blob(full_path)
        if not blob.exists():
            logger.error(f"[SPACES] Audio file not found: {full_path}")
            return Response("Audio file not found", status=404, mimetype='text/plain')
        
        # Get file size for Content-Length header
        blob.reload()
        file_size = blob.size
        
        # Check if this is a range request
        range_header = request.headers.get('range')
        
        if range_header:
            # Handle range requests properly
            try:
                byte_start = int(range_header.split('=')[1].split('-')[0])
                byte_end = file_size - 1
                if '-' in range_header.split('=')[1] and range_header.split('=')[1].split('-')[1]:
                    byte_end = int(range_header.split('=')[1].split('-')[1])
                
                # Limit chunk size to 5MB to avoid memory issues
                chunk_size = min(byte_end - byte_start + 1, 5 * 1024 * 1024)
                byte_end = byte_start + chunk_size - 1
                
                logger.info(f"[SPACES] Serving range {byte_start}-{byte_end} of {file_size}")
                
                # Download only the requested range
                audio_content = blob.download_as_bytes(start=byte_start, end=byte_end + 1)
                
                # Return partial content response
                response = Response(
                    audio_content,
                    status=206,
                    mimetype='audio/mpeg',
                    headers={
                        'Content-Range': f'bytes {byte_start}-{byte_end}/{file_size}',
                        'Accept-Ranges': 'bytes',
                        'Content-Length': str(len(audio_content)),
                        'Content-Type': 'audio/mpeg',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, OPTIONS',
                        'Access-Control-Allow-Headers': 'Range',
                        'Cache-Control': 'public, max-age=3600'
                    }
                )
                return response
                
            except Exception as e:
                logger.error(f"[SPACES] Error handling range request: {e}")
                # Fall through to standard handling
        
        # For large files without range request, use streaming generator
        if file_size > 30 * 1024 * 1024:  # 30MB threshold
            logger.info(f"[SPACES] Using streaming for large file ({file_size} bytes)")
            
            from flask import stream_with_context
            
            @stream_with_context
            def generate():
                # Stream in 1MB chunks
                chunk_size = 1024 * 1024
                offset = 0
                
                while offset < file_size:
                    end = min(offset + chunk_size, file_size)
                    try:
                        chunk = blob.download_as_bytes(start=offset, end=end)
                        yield chunk
                        offset = end
                    except Exception as e:
                        logger.error(f"[SPACES] Error streaming chunk at offset {offset}: {e}")
                        break
            
            # Stream response without setting Content-Length
            response = Response(
                generate(),
                mimetype='audio/mpeg',
                headers={
                    'Content-Type': 'audio/mpeg',
                    'Accept-Ranges': 'bytes',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Range',
                    'Cache-Control': 'no-cache, no-store'
                }
            )
            
            return response
        
        # For files that made it here (small files < 10MB), serve them directly
        logger.info(f"[SPACES] Serving small file directly: {space_id} ({file_size} bytes)")
        
        audio_content = blob.download_as_bytes()
        
        response = Response(
            audio_content,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': f'inline; filename="space_{space_id}.mp3"',
                'Accept-Ranges': 'bytes',
                'Content-Type': 'audio/mpeg',
                'Content-Length': str(file_size),
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Range',
                'Cache-Control': 'public, max-age=3600'
            }
        )
        
        return response
            
    except Exception as e:
        logger.error(f"[SPACES] Error serving audio: {e}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        # Return proper HTTP error response for audio endpoint
        return Response(
            "Error accessing audio file",
            status=500,
            mimetype='text/plain'
        )

@bp.route('/info/<space_id>')
@auth_required
@require_permission('clip_spaces')
def get_space_info(space_id):
    """Get space information"""
    user_id = str(get_workspace_user_id())
    logger.info(f"[SPACES] User {user_id} requesting info for space_id: {space_id}")
    
    try:
        space_path = f"spaces/{space_id}"
        
        # Load the main data file
        data_path = f"{space_path}/data.json"
        data_content = StorageService.get_file_content(user_id, 'data', data_path)
        
        if not data_content:
            logger.error(f"[SPACES] Space data not found: {data_path}")
            return jsonify({'success': False, 'error': 'Space data not found'}), 404
        
        if isinstance(data_content, str):
            data = json.loads(data_content)
        else:
            data = data_content
        
        # Load transcript separately (might be updated)
        transcript_path = f"{space_path}/transcript.txt"
        transcript_content = StorageService.get_file_content(user_id, 'data', transcript_path)
        if transcript_content:
            data['transcript'] = transcript_content
        
        # Load summary separately (might be updated)
        summary_path = f"{space_path}/summary.md"
        summary_content = StorageService.get_file_content(user_id, 'data', summary_path)
        if summary_content:
            data['summary'] = summary_content
        
        logger.info(f"[SPACES] Loaded transcript length: {len(data.get('transcript', ''))}")
        logger.info(f"[SPACES] Loaded summary length: {len(data.get('summary', ''))}")
        
        return jsonify(data)
        
    except Exception as e:
        error_msg = f"Error loading space data: {str(e)}"
        logger.error(f"[SPACES] {error_msg}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': error_msg}), 500

@bp.route('/trim', methods=['POST'])
@auth_required
@require_permission('clip_spaces')
def trim_space():
    """Trim a Twitter Space audio file"""
    try:
        data = request.get_json()
        
        space_id = data.get('space_id')
        start_time = float(data.get('start', 0))
        end_time = float(data.get('end', 0))
        filename = data.get('filename')
        
        if not space_id:
            return jsonify({'success': False, 'error': 'No Space ID provided'}), 400
            
        if start_time >= end_time:
            return jsonify({'success': False, 'error': 'Invalid time range'}), 400
        
        user_id = str(get_workspace_user_id())
        
        # Get the original audio file content
        audio_path = f"spaces/{space_id}/audio.mp3"
        audio_content = StorageService.get_file_content(user_id, 'data', audio_path)
        
        if not audio_content:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            if isinstance(audio_content, str):
                temp_audio.write(audio_content.encode())
            else:
                temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        # Create output path
        if not filename:
            filename = f"trim_{space_id}_{int(start_time)}_{int(end_time)}.mp3"
        
        temp_output_path = tempfile.mktemp(suffix='.mp3')
        
        try:
            # Initialize processor for trimming
            processor = SpaceProcessor(space_id, user_id)
            processor.audio_path = temp_audio_path
            
            # Trim the audio
            processor.trim_audio(start_time, end_time, temp_output_path)
            
            # Save trimmed file to Firebase Storage
            exports_path = f"spaces/{space_id}/exports/{filename}"
            
            with open(temp_output_path, 'rb') as trimmed_file:
                StorageService.save_file_content(user_id, 'data', exports_path, trimmed_file.read())
            
            # Generate download URL
            download_url = f"/clip-spaces/download/{space_id}/{filename}"
            
            return jsonify({
                'success': True,
                'download_url': download_url,
                'filename': filename
            })
        
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_audio_path)
                if os.path.exists(temp_output_path):
                    os.unlink(temp_output_path)
            except:
                pass
    
    except Exception as e:
        error_msg = f"Error trimming Space audio: {str(e)}"
        logger.error(f"[SPACES] {error_msg}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/trim_multiple', methods=['POST'])
@auth_required
@require_permission('clip_spaces')
def trim_multiple():
    """Trim multiple regions of a Twitter Space audio file and create a zip archive"""
    try:
        data = request.get_json()
        
        space_id = data.get('space_id')
        regions = data.get('regions', [])
        filename = data.get('filename', f"twitter_space_{space_id}_all_trims.zip")
        
        if not space_id:
            return jsonify({'success': False, 'error': 'No Space ID provided'}), 400
            
        if not regions:
            return jsonify({'success': False, 'error': 'No regions provided'}), 400
        
        user_id = str(get_workspace_user_id())
        
        # Get the original audio file content
        audio_path = f"spaces/{space_id}/audio.mp3"
        audio_content = StorageService.get_file_content(user_id, 'data', audio_path)
        
        if not audio_content:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            if isinstance(audio_content, str):
                temp_audio.write(audio_content.encode())
            else:
                temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        # Create a temporary directory for the trimmed files
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Initialize processor
            processor = SpaceProcessor(space_id, user_id)
            processor.audio_path = temp_audio_path
            
            # Trim each region
            trimmed_files = []
            for i, region in enumerate(regions):
                start_time = float(region.get('start', 0))
                end_time = float(region.get('end', 0))
                
                if start_time >= end_time:
                    continue  # Skip invalid regions
                    
                region_filename = f"region_{i+1}_{int(start_time)}_{int(end_time)}.mp3"
                output_path = os.path.join(temp_dir, region_filename)
                
                # Trim the audio
                processor.trim_audio(start_time, end_time, output_path)
                trimmed_files.append(output_path)
            
            # Create zip file
            zip_path = os.path.join(temp_dir, filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in trimmed_files:
                    zipf.write(file, os.path.basename(file))
            
            # Save zip file to Firebase Storage
            exports_path = f"spaces/{space_id}/exports/{filename}"
            
            with open(zip_path, 'rb') as zip_file:
                StorageService.save_file_content(user_id, 'data', exports_path, zip_file.read())
            
            # Create download URL
            download_url = f"/spaces/download/{space_id}/{filename}"
            
            return jsonify({
                'success': True,
                'download_url': download_url,
                'filename': filename
            })
        
        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_audio_path)
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
    
    except Exception as e:
        error_msg = f"Error trimming multiple regions: {str(e)}"
        logger.error(f"[SPACES] {error_msg}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/download/<space_id>/<filename>')
@auth_required
@require_permission('clip_spaces')
def download_export(space_id, filename):
    """Download a trimmed audio file"""
    logger.info(f"[SPACES] Download request for space_id={space_id}, filename={filename}")
    
    try:
        user_id = str(get_workspace_user_id())
        logger.info(f"[SPACES] User {user_id} downloading {filename} from space {space_id}")
        
        # Get the exported file using the same pattern as other files
        exports_path = f"spaces/{space_id}/exports/{filename}"
        export_content = StorageService.get_file_content(user_id, 'data', exports_path)
        
        if not export_content:
            logger.error(f"[SPACES] Export file not found at path: {exports_path}")
            # Return proper HTTP error response for binary endpoint
            return Response(
                "File not found",
                status=404,
                mimetype='text/plain',
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': 'true'
                }
            )
        
        # Determine content type based on file extension
        content_type = 'application/octet-stream'
        if filename.endswith('.mp3'):
            content_type = 'audio/mpeg'
        elif filename.endswith('.zip'):
            content_type = 'application/zip'
        
        # Ensure export_content is bytes
        if isinstance(export_content, str):
            export_content = export_content.encode('utf-8')
        
        logger.info(f"[SPACES] Serving download: {filename} ({len(export_content)} bytes)")
        
        response = Response(
            export_content,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': content_type,
                'Content-Length': str(len(export_content)),
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            }
        )
        
        return response
    
    except Exception as e:
        error_msg = f"Error downloading file: {str(e)}"
        logger.error(f"[SPACES] {error_msg}")
        logger.error(f"[SPACES] Traceback: {traceback.format_exc()}")
        
        # Return proper HTTP error response for binary endpoint
        return Response(
            f"Error: {str(e)}",
            status=500,
            mimetype='text/plain',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': 'true'
            }
        )