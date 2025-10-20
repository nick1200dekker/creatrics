"""
Image Editor Module using FAL API for Flux Kontext models
Handles image editing operations and storing results in Firebase
"""
import os
import json
import uuid
import base64
import requests
import logging
from pathlib import Path
from datetime import datetime
from firebase_admin import storage as firebase_storage
from firebase_admin import firestore
import time
import threading
import traceback
from dotenv import load_dotenv
import fal_client


# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

def load_prompt(filename: str) -> str:
    """Load a prompt from text file"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        raise
# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageEditor:
    """Class to handle image editing using FAL API for Flux Kontext models"""
    
    def __init__(self, user_id):
        """Initialize ImageEditor with user_id"""
        self.user_id = user_id
        
        # Initialize Firestore DB client
        self.db = firestore.client()
        
        # Get Firebase Storage bucket
        self.bucket = firebase_storage.bucket()
        
        # Get FAL API token
        self.fal_api_token = os.environ.get('FAL_API_TOKEN', '')
        
        if not self.fal_api_token:
            logger.error("FAL API token not found in environment")
        else:
            logger.info(f"FAL API token loaded (starts with: {self.fal_api_token[:8]}...)")
            # Set FAL_KEY environment variable for fal_client
            os.environ['FAL_KEY'] = self.fal_api_token
            # Log available fal_client attributes for debugging
            logger.debug(f"fal_client methods: {[attr for attr in dir(fal_client) if not attr.startswith('_')]}")
    
    def check_api_token(self):
        """Check if API token is available"""
        if not self.fal_api_token:
            raise ValueError("FAL API token not found. Please add FAL_API_TOKEN to your environment variables.")
        return True
    
    def edit_image(self, image_data, prompt, model_name='flux-kontext-max', aspect_ratio='match_input_image'):
        """
        Edit an image using the FAL API for Flux Kontext models
        
        Args:
            image_data (str): Base64 encoded image
            prompt (str): Text prompt to guide the editing
            model_name (str): The model to use ('flux-kontext-max' or 'flux-kontext-pro')
            aspect_ratio (str): Aspect ratio for output
            
        Returns:
            dict: Result containing edit_id and other metadata
        """
        try:
            # Check if API token is available
            self.check_api_token()
            
            # Import credits manager
            from app.system.credits.credits_manager import CreditsManager
            from app.system.credits.config import get_image_editor_cost
            
            # Map model names to credit keys and FAL endpoints
            model_mapping = {
                'flux-kontext-max': {
                    'api_endpoint': 'fal-ai/flux-pro/kontext/max',
                    'credit_key': 'FLUX_KONTEXT_MAX'
                },
                'flux-kontext-pro': {
                    'api_endpoint': 'fal-ai/flux-pro/kontext',
                    'credit_key': 'FLUX_KONTEXT_PRO'
                }
            }
            
            # Get model info
            model_info = model_mapping.get(model_name, model_mapping['flux-kontext-pro'])
            api_endpoint = model_info['api_endpoint']
            credit_key = model_info['credit_key']
            
            logger.info(f"Using model: {model_name}, API endpoint: {api_endpoint}, Credit key: {credit_key}")
            
            # Get credit cost
            credit_cost = get_image_editor_cost(credit_key)
            
            # Check if user has sufficient credits
            credits_manager = CreditsManager()
            if not credits_manager.has_sufficient_credits(self.user_id, credit_cost):
                logger.error(f"Insufficient credits for user {self.user_id}")
                return {
                    "error": "Insufficient credits",
                    "details": f"This operation requires {credit_cost} credits. Please purchase more credits."
                }
            
            # Unique ID for this edit
            edit_id = str(uuid.uuid4())
            
            # Clean base64 data
            if image_data.startswith("data:image/"):
                image_data = image_data.split("base64,")[1]
            
            # Save the input image
            input_image_url = self.save_input_image(edit_id, image_data)
            
            # Create edit record immediately for UI feedback
            edit_data = {
                "id": edit_id,
                "prompt": prompt,
                "created_at": datetime.now().isoformat(),
                "status": "processing",
                "input_image": True,
                "user_id": self.user_id,
                "model": api_endpoint,
                "model_display": model_name,
                "aspect_ratio": aspect_ratio,
                "credits_cost": credit_cost,
                "provider": "fal"
            }
            
            # Save to user-specific collection
            edit_ref = self.db.collection('users').document(self.user_id).collection('data').document('image_editor').collection('edits').document(edit_id)
            edit_ref.set(edit_data)
            logger.info(f"Created processing record for edit: {edit_id}")
            
            # Return immediately for UI feedback
            result = edit_data.copy()
            
            # Process in background
            thread = threading.Thread(
                target=self._process_edit_async,
                args=(edit_id, image_data, prompt, model_name, api_endpoint, credit_key, credit_cost, aspect_ratio)
            )
            thread.daemon = True
            thread.start()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in image editing: {str(e)}\n{traceback.format_exc()}")
            return {
                "error": "Image editing failed",
                "details": str(e)
            }
    
    def _process_edit_async(self, edit_id, image_data, prompt, model_name, api_endpoint, credit_key, credit_cost, aspect_ratio):
        """Process image edit asynchronously"""
        try:
            # Import credits manager
            from app.system.credits.credits_manager import CreditsManager
            
            try:
                # Get public URL for input image
                temp_image_url = self._get_public_url_for_image(edit_id, 'input')
                
                if not temp_image_url:
                    logger.error("Failed to get public URL for input image")
                    self._update_edit_status(edit_id, "error", "Failed to prepare image")
                    return
                
                logger.info(f"Using public image URL: {temp_image_url}")
                
                # Configure input parameters
                input_params = {
                    "prompt": prompt,
                    "image_url": temp_image_url,
                    "safety_tolerance": 6,  # Set safety tolerance to 0 as requested
                }
                
                # Only add aspect_ratio if it's not 'match_input_image' (FAL doesn't have this option)
                if aspect_ratio != 'match_input_image':
                    input_params["aspect_ratio"] = aspect_ratio
                
                logger.info(f"Starting FAL API call with endpoint {api_endpoint}")
                logger.info(f"Input parameters: {json.dumps({k: v for k, v in input_params.items() if k != 'image_url'})}")
                
                # Submit request to FAL
                response = fal_client.submit(
                    api_endpoint,
                    arguments=input_params
                )
                
                logger.info(f"Submit response type: {type(response)}")
                
                # Get request ID
                if hasattr(response, 'request_id'):
                    request_id = response.request_id
                elif isinstance(response, dict) and 'request_id' in response:
                    request_id = response['request_id']
                else:
                    logger.error(f"Could not extract request_id from response: {response}")
                    self._update_edit_status(edit_id, "error", "Failed to get request ID")
                    return
                    
                logger.info(f"FAL request submitted with ID: {request_id}")
                
                # Poll for status
                max_polls = 60  # Max 2 minutes with 2 second intervals
                poll_count = 0
                result = None
                
                while poll_count < max_polls:
                    poll_count += 1
                    status = fal_client.status(
                        api_endpoint,
                        request_id
                    )
                    
                    # Log the raw status for debugging
                    logger.info(f"Status response - Type: {type(status).__name__}")
                    logger.debug(f"Status attributes: {[attr for attr in dir(status) if not attr.startswith('_')]}")
                    
                    # Try to handle different status types
                    status_type_name = type(status).__name__
                    
                    if status_type_name == 'InProgress' or (hasattr(status, 'status') and status.status == 'IN_PROGRESS'):
                        logger.info(f"Status for {request_id}: IN_PROGRESS")
                        # Optional: log progress if available
                        if hasattr(status, 'logs') and status.logs:
                            for log in status.logs:
                                logger.info(f"Progress log: {log}")
                    elif status_type_name == 'Queued' or (hasattr(status, 'status') and status.status == 'QUEUED'):
                        logger.info(f"Status for {request_id}: QUEUED")
                    elif status_type_name == 'Completed' or (hasattr(status, 'status') and status.status == 'COMPLETED'):
                        logger.info(f"Status for {request_id}: COMPLETED")
                        # The result might be in the status object itself
                        if hasattr(status, 'data'):
                            result = status.data
                        else:
                            # Get the result separately
                            result = fal_client.result(
                                api_endpoint,
                                request_id
                            )
                        break
                    else:
                        # Handle unexpected status types
                        logger.warning(f"Unexpected status type: {type(status)} - {status}")
                        # Check if it's a failed status
                        if hasattr(status, 'status') and status.status == 'FAILED':
                            error_msg = getattr(status, 'error', 'Unknown error')
                            logger.error(f"FAL request failed: {error_msg}")
                            self._update_edit_status(edit_id, "error", error_msg)
                            return
                        # If we can't determine the status, continue polling
                        logger.info(f"Unknown status, continuing to poll...")
                    
                    # Wait before next poll
                    time.sleep(2)
                
                # Check if we timed out
                if poll_count >= max_polls:
                    logger.error(f"Polling timed out after {max_polls * 2} seconds")
                    self._update_edit_status(edit_id, "error", "Request timed out")
                    return
                
                if result is None:
                    logger.error("No result received from FAL API")
                    self._update_edit_status(edit_id, "error", "No result received")
                    return
                
                logger.info(f"FAL API call completed. Result type: {type(result).__name__}")
                logger.debug(f"Result attributes: {[attr for attr in dir(result) if not attr.startswith('_')]}")
                
                # Extract the result URL - handle both object and dict responses
                images = None
                
                # Try to get images from different possible locations
                if hasattr(result, 'images'):
                    images = result.images
                elif isinstance(result, dict) and 'images' in result:
                    images = result['images']
                elif hasattr(result, 'data'):
                    if hasattr(result.data, 'images'):
                        images = result.data.images
                    elif isinstance(result.data, dict) and 'images' in result.data:
                        images = result.data['images']
                
                if images and len(images) > 0:
                    # Extract URL from image object or dict
                    output_url = None
                    if isinstance(images[0], dict):
                        output_url = images[0].get('url')
                    elif hasattr(images[0], 'url'):
                        output_url = images[0].url
                    
                    if output_url:
                        logger.info(f"Found output URL: {output_url}")
                    else:
                        logger.error(f"No URL found in image object: {images[0]}")
                        self._update_edit_status(edit_id, "error", "No URL in result")
                        return
                else:
                    logger.error(f"No images found in response. Full result: {result}")
                    self._update_edit_status(edit_id, "error", "No images in response")
                    return
                
                # Download and save the result
                result_path = self._download_and_save_result(edit_id, output_url)
                firebase_url = self._get_firebase_image_url(edit_id, 'result')
                
                # Deduct credits
                credits_manager = CreditsManager()
                credit_result = credits_manager.deduct_credits(
                    self.user_id,
                    credit_cost,
                    f"Image Edit ({model_name}): {prompt[:30]}{'...' if len(prompt) > 30 else ''}",
                    edit_id
                )
                
                if not credit_result['success']:
                    logger.error(f"Failed to deduct credits: {credit_result['message']}")
                
                # Update status
                self._update_edit_status(
                    edit_id,
                    "completed",
                    result_path=result_path,
                    result_url=firebase_url,
                    completed_at=datetime.now().isoformat()
                )
                
                logger.info(f"Image edit completed successfully: {edit_id}")
                
            except Exception as e:
                logger.error(f"Error in FAL API call: {str(e)}\n{traceback.format_exc()}")
                self._update_edit_status(edit_id, "error", str(e))
                
        except Exception as e:
            logger.error(f"Error in async edit processing: {str(e)}\n{traceback.format_exc()}")
            self._update_edit_status(edit_id, "error", f"Unexpected error: {str(e)}")

    
    def _update_edit_status(self, edit_id, status, error_message=None, **kwargs):
        """Update the status of an edit in Firestore"""
        try:
            edit_ref = self.db.collection('users').document(self.user_id).collection('data').document('image_editor').collection('edits').document(edit_id)
            update_data = {"status": status}
            
            if error_message and status == "error":
                update_data["error"] = error_message
            
            update_data.update(kwargs)
            
            edit_ref.update(update_data)
            logger.info(f"Updated edit status to {status}: {edit_id}")
        except Exception as e:
            logger.error(f"Error updating edit status: {str(e)}")
    
    def _get_public_url_for_image(self, edit_id, image_type='input'):
        """Get a public URL for an uploaded image"""
        try:
            blob = self.bucket.blob(f"users/{self.user_id}/data/image_editor/{image_type}/{edit_id}.jpg")
            
            if not blob.exists():
                logger.error(f"Image blob not found: {edit_id}")
                return None
            
            blob.make_public()
            url = blob.public_url
            
            logger.info(f"Created public URL for {image_type} image: {url}")
            return url
        except Exception as e:
            logger.error(f"Error creating public URL: {str(e)}")
            return None
    
    def _download_and_save_result(self, edit_id, result_url):
        """Download and save the edited result"""
        logger.info(f"Downloading result from: {result_url}")
        
        response = requests.get(result_url, stream=True)
        if response.status_code != 200:
            raise Exception(f"Failed to download result. Status code: {response.status_code}")
        
        # Save to Firebase Storage
        result_path = f"users/{self.user_id}/data/image_editor/results/{edit_id}.jpg"
        blob = self.bucket.blob(result_path)
        
        blob.upload_from_string(
            response.content,
            content_type="image/jpeg"
        )
        
        blob.make_public()
        
        logger.info(f"Result saved to Firebase Storage: {result_path}")
        return result_path
    
    def _get_firebase_image_url(self, edit_id, image_type='result'):
        """Get the public URL for an image in Firebase Storage"""
        if image_type == 'result':
            blob = self.bucket.blob(f"users/{self.user_id}/data/image_editor/results/{edit_id}.jpg")
        else:
            blob = self.bucket.blob(f"users/{self.user_id}/data/image_editor/{image_type}/{edit_id}.jpg")
        
        if blob.exists():
            blob.make_public()
            return blob.public_url
        else:
            logger.error(f"Image file not found: {edit_id}")
            return None
    
    def save_input_image(self, edit_id, image_data):
        """Save the input image to Firebase Storage"""
        try:
            blob_path = f"users/{self.user_id}/data/image_editor/input/{edit_id}.jpg"
            blob = self.bucket.blob(blob_path)
            
            # Decode and upload
            blob.upload_from_string(
                base64.b64decode(image_data),
                content_type="image/jpeg"
            )
            
            blob.make_public()
            image_url = blob.public_url
            
            logger.info(f"Saved input image: {blob_path}")
            return image_url
        except Exception as e:
            logger.error(f"Error saving input image: {str(e)}")
            return None
    
    def get_edit(self, edit_id):
        """Get edit data for a specific ID"""
        try:
            edit_ref = self.db.collection('users').document(self.user_id).collection('data').document('image_editor').collection('edits').document(edit_id)
            edit_doc = edit_ref.get()
            
            if not edit_doc.exists:
                return None
            
            edit_data = edit_doc.to_dict()
            return edit_data
        except Exception as e:
            logger.error(f"Error getting edit: {str(e)}")
            return None
    
    def get_recent_edits(self, limit=10):
        """Get recent edits"""
        try:
            query = self.db.collection('users').document(self.user_id).collection('data').document('image_editor').collection('edits')
            edit_docs = query.stream()
            
            all_edits = []
            for doc in edit_docs:
                edit_data = doc.to_dict()
                edit_data['id'] = doc.id
                all_edits.append(edit_data)
            
            # Sort by created_at
            all_edits.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return all_edits[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent edits: {str(e)}")
            return []
    
    def delete_edit(self, edit_id):
        """Delete an edit"""
        try:
            edit_ref = self.db.collection('users').document(self.user_id).collection('data').document('image_editor').collection('edits').document(edit_id)
            edit_doc = edit_ref.get()
            
            if not edit_doc.exists:
                return False
            
            # Delete images from Storage
            input_blob = self.bucket.blob(f"users/{self.user_id}/data/image_editor/input/{edit_id}.jpg")
            if input_blob.exists():
                input_blob.delete()
            
            result_blob = self.bucket.blob(f"users/{self.user_id}/data/image_editor/results/{edit_id}.jpg")
            if result_blob.exists():
                result_blob.delete()
            
            # Delete document
            edit_ref.delete()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting edit: {str(e)}")
            return False
    
    def get_input_image_url(self, edit_id):
        """Get URL for input image"""
        return self._get_firebase_image_url(edit_id, 'input')
    
    def get_result_image_url(self, edit_id):
        """Get URL for result image"""
        return self._get_firebase_image_url(edit_id, 'result')