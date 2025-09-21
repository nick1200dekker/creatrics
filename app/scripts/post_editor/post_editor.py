"""
Post Editor Module for enhanced content generation
Clean architecture: ONLY handles content generation
ALL credit operations delegated to CreditsManager
Enhanced with multi-media support and AI Provider integration
"""
import os
import logging
import traceback
import base64
import uuid
import mimetypes
from pathlib import Path
from typing import Optional, Dict, List
from dotenv import load_dotenv
from app.system.ai_provider.ai_provider import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class PostEditor:
    """Enhanced PostEditor with multi-media support: Focus on content generation ONLY"""
    
    def __init__(self):
        self.presets = ['grammar', 'storytelling', 'hook_story_punch']
        
        # Define supported media types and their configurations
        self.supported_media_types = {
            'image': {
                'mime_types': ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
                'max_size': 10 * 1024 * 1024,  # 10MB
                'prefix': 'img'
            },
            'video': {
                'mime_types': ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo', 'video/avi'],
                'max_size': 100 * 1024 * 1024,  # 100MB
                'prefix': 'vid'
            },
            'gif': {
                'mime_types': ['image/gif'],
                'max_size': 25 * 1024 * 1024,  # 25MB
                'prefix': 'gif'
            }
        }

    def get_default_prompt(self, preset: str) -> str:
        """Get the default prompt for a preset from the defaults directory."""
        try:
            current_dir = Path(__file__).parent
            prompt_file = current_dir / f'{preset}.txt'
            
            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return None
                
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading default prompt: {e}")
            return None

    def get_media_type_from_mime(self, mime_type: str) -> str:
        """Determine media type from MIME type"""
        for media_type, config in self.supported_media_types.items():
            if mime_type in config['mime_types']:
                return media_type
        return 'unknown'

    def validate_media_file(self, mime_type: str, file_size: int) -> Dict[str, any]:
        """Validate media file type and size"""
        media_type = self.get_media_type_from_mime(mime_type)
        
        if media_type == 'unknown':
            return {
                'valid': False,
                'error': f'Unsupported file type: {mime_type}'
            }
        
        config = self.supported_media_types[media_type]
        if file_size > config['max_size']:
            max_size_mb = config['max_size'] // (1024 * 1024)
            return {
                'valid': False,
                'error': f'File too large. Maximum size for {media_type}: {max_size_mb}MB'
            }
        
        return {
            'valid': True,
            'media_type': media_type,
            'config': config
        }

    def save_media_to_storage(self, user_id: str, media_data: str, filename: str = None, 
                             media_type: str = None, mime_type: str = None) -> str:
        """Save media using Firebase Storage"""
        try:
            if not filename:
                # Add media type prefix to filename for identification
                ext = mimetypes.guess_extension(mime_type) or '.bin'
                media_prefix = self.supported_media_types.get(media_type, {}).get('prefix', 'med')
                filename = f"{media_prefix}_{uuid.uuid4()}{ext}"
            
            # Validate the media file
            if mime_type:
                validation = self.validate_media_file(mime_type, len(media_data))
                if not validation['valid']:
                    logger.error(f"Media validation failed: {validation['error']}")
                    return None
                
                media_type = validation['media_type']
            
            # Extract base64 data if needed
            if media_data.startswith("data:"):
                media_data = media_data.split("base64,")[1]
                logger.info("Extracted base64 data from data URI")
            
            media_bytes = base64.b64decode(media_data)
            
            from io import BytesIO
            media_file = BytesIO(media_bytes)
            
            try:
                from firebase_admin import storage
                bucket = storage.bucket()
                
                blob_path = f"users/{user_id}/post_editor/{filename}"
                blob = bucket.blob(blob_path)
                
                # Set appropriate content type
                content_type = mime_type or 'application/octet-stream'
                blob.upload_from_file(media_file, content_type=content_type)
                blob.make_public()
                
                public_url = blob.public_url
                logger.info(f"Media uploaded successfully: {filename} ({media_type}) -> {public_url}")
                return public_url
                
            except Exception as firebase_error:
                logger.error(f"Firebase direct upload failed: {str(firebase_error)}")
                
                # Fallback to existing StorageService
                from app.system.services.firebase_service import StorageService
                result = StorageService.upload_file(user_id, 'post_editor', filename, media_file)
                
                if result and result.get('url'):
                    logger.info(f"Media saved using StorageService fallback: {filename}")
                    return result['url']
                else:
                    logger.error("Failed to upload media to storage (fallback also failed)")
                    return None
            
        except Exception as e:
            logger.error(f"Error saving media to storage: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def generate_public_media_url(self, user_id: str, filename: str) -> str:
        """Generate a permanent public URL for media in Firebase Storage"""
        try:
            from firebase_admin import storage
            
            bucket = storage.bucket()
            blob_path = f"users/{user_id}/post_editor/{filename}"
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"Media not found in storage: {blob_path}")
                return ""
            
            try:
                blob.make_public()
            except Exception:
                pass  # Might already be public
            
            public_url = blob.public_url
            logger.info(f"Generated public URL for {filename}: {public_url}")
            return public_url
            
        except Exception as e:
            logger.error(f"Error generating public URL for {filename}: {str(e)}")
            return ""

    def delete_media_from_storage(self, user_id: str, filename: str) -> bool:
        """Delete media from Firebase Storage"""
        try:
            from firebase_admin import storage
            
            bucket = storage.bucket()
            blob_path = f"users/{user_id}/post_editor/{filename}"
            blob = bucket.blob(blob_path)
            
            if blob.exists():
                blob.delete()
                logger.info(f"Deleted media from storage: {blob_path}")
                return True
            else:
                logger.warning(f"Media not found for deletion: {blob_path}")
                return False
            
        except Exception as e:
            logger.error(f"Error deleting media {filename}: {str(e)}")
            return False

    def store_pre_ai_version(self, user_id: str, draft_id: str, posts: list) -> bool:
        """Store the pre-AI version of content including media for revert functionality"""
        try:
            from firebase_admin import firestore
            from datetime import datetime
            
            db = firestore.client()
            
            version_ref = (db.collection('users')
                          .document(str(user_id))
                          .collection('post_drafts')
                          .document(str(draft_id))
                          .collection('versions')
                          .document('pre_ai'))
            
            # Ensure media data is preserved with unified format
            processed_posts = []
            for post in posts:
                processed_post = {
                    'text': post.get('text', ''),
                    'media': post.get('media', post.get('images', []))  # Unified to media field
                }
                processed_posts.append(processed_post)
            
            version_data = {
                'posts': processed_posts,
                'timestamp': datetime.now(),
                'version_type': 'pre_ai',
                'description': 'Content before AI enhancement (with media)'
            }
            
            version_ref.set(version_data)
            logger.info(f"Pre-AI version with media stored for draft {draft_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing pre-AI version: {e}")
            logger.error(traceback.format_exc())
            return False

    def get_pre_ai_version(self, user_id: str, draft_id: str) -> list:
        """Get the pre-AI version of content including media for revert functionality"""
        try:
            from firebase_admin import firestore
            
            db = firestore.client()
            
            version_ref = (db.collection('users')
                          .document(str(user_id))
                          .collection('post_drafts')
                          .document(str(draft_id))
                          .collection('versions')
                          .document('pre_ai'))
            
            version_doc = version_ref.get()
            
            if version_doc.exists:
                version_data = version_doc.to_dict()
                posts = version_data.get('posts', [])
                
                # Update media URLs to ensure they're current
                for post in posts:
                    if 'media' in post and isinstance(post['media'], list):
                        for item in post['media']:
                            if isinstance(item, dict) and 'filename' in item:
                                item['url'] = self.generate_public_media_url(user_id, item['filename'])
                
                logger.info(f"Pre-AI version with media retrieved for draft {draft_id}")
                return posts
            else:
                logger.info(f"No pre-AI version found for draft {draft_id}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting pre-AI version: {e}")
            logger.error(traceback.format_exc())
            return []

    def cleanup_orphaned_media(self, user_id: str, active_media_filenames: List[str]) -> int:
        """Clean up orphaned media files that are no longer referenced in any drafts"""
        try:
            from firebase_admin import storage
            
            bucket = storage.bucket()
            base_path = f"users/{user_id}/post_editor/"
            
            # Get all media files in user's storage
            blobs = bucket.list_blobs(prefix=base_path)
            deleted_count = 0
            
            for blob in blobs:
                filename = blob.name.split('/')[-1]
                if filename not in active_media_filenames:
                    try:
                        blob.delete()
                        logger.info(f"Deleted orphaned media: {blob.name}")
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete orphaned media {blob.name}: {e}")
            
            logger.info(f"Cleanup completed: {deleted_count} orphaned media files deleted")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during media cleanup: {e}")
            return 0

    def generate(self, posts: list, preset: str, additional_context: Optional[str] = None, 
                 user_id: Optional[str] = None, use_brand_voice: bool = False) -> dict:
        """
        Generate improved content for all posts in a thread based on the selected preset.
        
        CLEAN: This method ONLY handles content generation.
        Credit operations are handled by the caller using CreditsManager.
        
        Returns:
            dict: Result with enhanced posts and token usage for billing
        """
        if preset not in self.presets:
            raise ValueError(f"Unknown preset: {preset}")

        # Get the prompt template
        prompt_template = self.get_default_prompt(preset)
        if not prompt_template:
            raise ValueError(f"Could not load prompt for preset: {preset}")
        
        enhanced_posts = []
        total_input_tokens = 0
        total_output_tokens = 0
        
        # Get AI provider
        ai_provider = get_ai_provider()
        
        # Process each post individually for better thread handling
        for i, post in enumerate(posts):
            post_text = post.get('text', '').strip()
            
            # Skip empty posts
            if not post_text:
                enhanced_posts.append(post_text)
                continue
            
            # Create context-aware prompt for thread posts
            if len(posts) > 1:
                if i == 0:
                    context_note = f"\n\nThis is the first post in a {len(posts)}-post thread. Set up the topic engagingly."
                elif i == len(posts) - 1:
                    context_note = f"\n\nThis is the final post (#{i+1}) in a {len(posts)}-post thread. Provide a strong conclusion or call-to-action."
                else:
                    context_note = f"\n\nThis is post #{i+1} in a {len(posts)}-post thread. Continue the narrative flow from previous posts."
            else:
                context_note = ""
            
            # Add media context if present
            media_context = ""
            media_items = post.get('media', [])
            if media_items:
                media_descriptions = []
                for item in media_items:
                    if isinstance(item, dict):
                        media_type = item.get('media_type', 'image')
                        filename = item.get('filename', 'media')
                        media_descriptions.append(f"{media_type} ({filename})")
                    else:
                        media_descriptions.append("image")
                
                if media_descriptions:
                    media_context = f"\n\nThis post includes the following media: {', '.join(media_descriptions)}. Consider referencing or complementing this media in your enhanced content."
            
            # Format the prompt with the input text
            prompt = prompt_template.format(text=post_text) + context_note + media_context
            
            # Add any additional context if provided
            if additional_context:
                prompt = f"{prompt}\n\nAdditional context: {additional_context}"
            
            # Add brand voice context if requested
            if use_brand_voice and user_id:
                brand_voice_context = self.get_brand_voice_context(user_id)
                if brand_voice_context:
                    logger.info(f"Adding Brand Voice context for user {user_id}. Length: {len(brand_voice_context)} chars")
                    prompt = f"{prompt}\n\n{brand_voice_context}"
                else:
                    logger.info(f"Brand Voice requested but no context found for user {user_id}")
            
            try:
                # Call the AI API for this specific post
                response = ai_provider.create_completion(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that enhances social media posts for better engagement and clarity. Focus on improving this specific post while maintaining its core message."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=5000
                )
                
                # Track token usage from unified response
                if response.get('usage'):
                    total_input_tokens += response['usage']['input_tokens']
                    total_output_tokens += response['usage']['output_tokens']
                    logger.info(f"Post {i+1} tokens - Input: {response['usage']['input_tokens']}, Output: {response['usage']['output_tokens']}")
                
                # Extract the result
                result = response['content'].strip()
                logger.info(f"Generated content for post {i+1} using {response['provider']}: {result[:50]}...")
                enhanced_posts.append(result)
                
            except Exception as e:
                logger.error(f"Error calling AI API for post {i+1}: {str(e)}")
                # Fall back to original text if enhancement fails
                enhanced_posts.append(post_text)
        
        # Return result with token usage for billing
        return {
            'success': True,
            'enhanced_posts': enhanced_posts,
            'token_usage': {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'model': ai_provider.default_model
            }
        }

    def get_brand_voice_context(self, user_id: str) -> str:
        """Get the user's brand voice context from their X timeline data"""
        try:
            from firebase_admin import firestore
            db = firestore.client()
            
            posts_ref = db.collection('users').document(str(user_id)).collection('x_posts').document('timeline')
            posts_doc = posts_ref.get()
            
            if not posts_doc.exists:
                logger.info(f"No X posts document found for user {user_id}")
                return ""
            
            posts_data = posts_doc.to_dict()
            posts = posts_data.get('posts', [])
            
            if not posts:
                logger.info(f"No posts found in X timeline for user {user_id}")
                return ""
            
            # Get user's X account name for context
            user_doc = db.collection('users').document(str(user_id)).get()
            screen_name = ""
            if user_doc.exists:
                user_data = user_doc.to_dict()
                x_account = user_data.get('x_account', '')
                screen_name = x_account.lstrip('@') if x_account else ''
            
            # Sort posts by views to get best performing posts first
            sorted_posts = sorted(posts, key=lambda x: x.get('views', 0), reverse=True)
            top_posts = sorted_posts[:20]
            
            # Extract meaningful post text
            post_examples = []
            for post in top_posts:
                post_text = post.get('text', '').strip()
                if post_text and len(post_text) > 10:
                    import re
                    clean_text = re.sub(r'https?://\S+', '', post_text).strip()
                    if clean_text:
                        post_examples.append(clean_text)
            
            if not post_examples:
                logger.info(f"No meaningful post examples found for user {user_id}")
                return ""
                
            # Format the brand voice context
            brand_voice_context = f"Brand Voice Context for @{screen_name}:\n\n"
            brand_voice_context += "Below are examples of this user's best performing posts. Match their style exactly.\n\n"
            brand_voice_context += "MATCH: LENGTH, EMOJIS, TONE, BULLET POINTS, FORMATTING\n\n"
            
            # Add the top post examples
            for i, post in enumerate(post_examples[:15], 1):
                brand_voice_context += f"Top Post {i}: {post}\n\n"
                
            brand_voice_context += "OUTPUT FINAL CONTENT ONLY WITH NO EXPLANATIONS.\n"
            
            logger.info(f"Generated brand voice context for user {user_id} with {len(post_examples)} posts")
            return brand_voice_context
            
        except Exception as e:
            logger.error(f"Error getting brand voice context: {e}")
            logger.error(traceback.format_exc())
            return ""
    
    def has_brand_voice_data(self, user_id: str) -> bool:
        """Check if the user has brand voice data available"""
        try:
            from firebase_admin import firestore
            db = firestore.client()
            
            posts_ref = db.collection('users').document(str(user_id)).collection('x_posts').document('timeline')
            posts_doc = posts_ref.get()
            
            if not posts_doc.exists:
                logger.info(f"No X posts document found for user {user_id}")
                return False
            
            posts_data = posts_doc.to_dict()
            posts = posts_data.get('posts', [])
            
            # Check if we have posts with meaningful content
            meaningful_posts = 0
            for post in posts:
                post_text = post.get('text', '').strip()
                if post_text and len(post_text) > 10:
                    meaningful_posts += 1
            
            # Also check if user has X account connected
            user_doc = db.collection('users').document(str(user_id)).get()
            has_x_account = False
            if user_doc.exists:
                user_data = user_doc.to_dict()
                x_account = user_data.get('x_account', '')
                has_x_account = bool(x_account.strip())
            
            result = meaningful_posts >= 5 and has_x_account
            logger.info(f"Brand voice data check for user {user_id}: {result} (posts: {meaningful_posts}, x_account: {has_x_account})")
            return result
            
        except Exception as e:
            logger.error(f"Error checking brand voice data: {e}")
            return False

    def get_media_statistics(self, user_id: str) -> Dict[str, int]:
        """Get statistics about user's media usage"""
        try:
            from firebase_admin import storage
            
            bucket = storage.bucket()
            base_path = f"users/{user_id}/post_editor/"
            
            stats = {
                'total_files': 0,
                'total_size': 0,
                'images': 0,
                'videos': 0,
                'gifs': 0,
                'other': 0
            }
            
            blobs = bucket.list_blobs(prefix=base_path)
            
            for blob in blobs:
                filename = blob.name.split('/')[-1]
                
                stats['total_files'] += 1
                stats['total_size'] += blob.size if hasattr(blob, 'size') else 0
                
                # Determine media type from filename prefix
                if filename.startswith('img_'):
                    stats['images'] += 1
                elif filename.startswith('vid_'):
                    stats['videos'] += 1
                elif filename.startswith('gif_'):
                    stats['gifs'] += 1
                else:
                    stats['other'] += 1
            
            logger.info(f"Media statistics for user {user_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting media statistics: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'images': 0,
                'videos': 0,
                'gifs': 0,
                'other': 0
            }