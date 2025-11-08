import firebase_admin
from firebase_admin import credentials, storage, firestore
import json
import os
from datetime import datetime
import logging

logger = logging.getLogger('firebase_service')

# Initialize Firebase Admin with credentials
try:
    # Get credentials path
    cred_path = os.environ.get('FIREBASE_CREDENTIALS', '/secrets/firebase-credentials.json')
    
    if not os.path.exists(cred_path):
        fallback_locations = [
            './firebase-credentials.json',
            '/secrets/firebase-credentials.json',
            '/app/secrets/firebase-credentials.json'
        ]
        
        for fallback_path in fallback_locations:
            if os.path.exists(fallback_path):
                cred_path = fallback_path
                break
    
    logger.info(f"Using Firebase credentials from: {cred_path}")
    
    # Add this debug log
    if os.path.exists(cred_path):
        with open(cred_path, 'r') as f:
            cred_content = f.read()
            logger.info(f"Firebase credentials file exists. First 20 chars: {cred_content[:20]}")
    else:
        logger.error(f"Firebase credentials file not found at {cred_path}")
        
    cred = credentials.Certificate(cred_path)
    
    # Initialize with storage bucket
    bucket_name = os.environ.get('FIREBASE_STORAGE_BUCKET')
    logger.info(f"Firebase bucket name from env: {bucket_name}")
    
    if not bucket_name:
        with open(cred_path, 'r') as f:
            cred_data = json.load(f)
        project_id = cred_data.get('project_id')
        bucket_name = f"{project_id}.appspot.com"
        logger.info(f"Using derived bucket name: {bucket_name}")
    
    # Strip the 'gs://' prefix if present
    if bucket_name.startswith('gs://'):
        bucket_name = bucket_name[5:]
    
    # Initialize app
    firebase_app = firebase_admin.initialize_app(cred, {
        'storageBucket': bucket_name
    })
    
    # Initialize Firestore and Storage clients
    db = firestore.client()
    bucket = storage.bucket()
    storage_bucket = bucket  # Alias for consistency
    logger.info("Firebase successfully initialized")
    
except Exception as e:
    logger.error(f"Error initializing Firebase: {str(e)}")
    # Create dummy clients for development without failing
    db = None
    bucket = None
    storage_bucket = None
    firebase_app = None

class UserService:
    """Service for user operations in Firestore"""
    
    @staticmethod
    def get_user(user_id):
        """Get user by ID"""
        if not db:
            logger.error("Firestore not initialized")
            return None
            
        try:
            logger.info(f"Fetching user {user_id} from Firestore")
            doc_ref = db.collection('users').document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                logger.info(f"User {user_id} found in Firestore")
                return doc.to_dict()
            else:
                logger.info(f"User {user_id} not found in Firestore")
                return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def create_user(user_id, user_data):
        """Create a new user in Firestore"""
        if not db:
            logger.error("Firestore not initialized")
            return None

        try:
            logger.info(f"Creating user {user_id} in Firestore with data: {user_data}")
            doc_ref = db.collection('users').document(user_id)

            # Add timestamps
            user_data['created_at'] = datetime.now()
            user_data['last_login'] = datetime.now()
            user_data['is_active'] = True
            user_data['subscription_plan'] = user_data.get('subscription_plan', 'Free Plan')

            # Add 5 credits to new users
            user_data['credits'] = 5

            # Initialize referral data
            from app.system.services.referral_service import ReferralService
            username = user_data.get('username')
            referral_data = ReferralService.create_referral_entry(user_id, username)
            if referral_data:
                user_data.update(referral_data)

            # Save to Firestore
            doc_ref.set(user_data)
            logger.info(f"User {user_id} created successfully in Firestore")

            # Initialize user directories
            StorageService.initialize_user_directories(user_id)

            # Create default settings file
            default_settings = {
                'theme': 'dark',
                'notifications': True,
                'created_at': datetime.now().isoformat()
            }

            StorageService.save_config_file(user_id, 'settings.json', default_settings)

            return doc_ref.get().to_dict()
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def update_user(user_id, update_data):
        """Update user data"""
        if not db:
            logger.error("Firestore not initialized")
            return None
            
        try:
            logger.info(f"Updating user {user_id} with data: {update_data}")
            doc_ref = db.collection('users').document(user_id)
            doc_ref.update(update_data)
            logger.info(f"User {user_id} updated successfully")
            return doc_ref.get().to_dict()
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            return None

class StorageService:
    """Service for managing user files in Firebase Storage"""
    
    @staticmethod
    def initialize_user_directories(user_id):
        """Create initial directories for a new user - ONLY config and data"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return False
            
        try:
            logger.info(f"Initializing directories for user {user_id}")
            directories = ['config', 'data']
            
            for directory in directories:
                # In Firebase Storage, we create an empty file to represent a directory
                blob = bucket.blob(f'users/{user_id}/{directory}/.keep')
                blob.upload_from_string('')
                
            logger.info(f"Directories for user {user_id} initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing directories for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def save_config_file(user_id, filename, data):
        """Save a configuration file for the user"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None
            
        try:
            logger.info(f"Saving config file {filename} for user {user_id}")
            blob = bucket.blob(f'users/{user_id}/config/{filename}')
            
            if isinstance(data, dict):
                # If data is a dict, save as JSON
                blob.upload_from_string(
                    json.dumps(data, indent=2),
                    content_type='application/json'
                )
            else:
                # Otherwise save as is
                blob.upload_from_string(data)
            
            # Generate a signed URL that expires in 1 hour
            url = blob.generate_signed_url(
                version='v4',
                expiration=3600,
                method='GET'
            )
            
            logger.info(f"Config file {filename} saved successfully for user {user_id}")
            return url
        except Exception as e:
            logger.error(f"Error saving config file {filename} for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_config_file(user_id, filename):
        """Get a configuration file"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None
            
        try:
            logger.info(f"Getting config file {filename} for user {user_id}")
            blob = bucket.blob(f'users/{user_id}/config/{filename}')
            
            if not blob.exists():
                logger.info(f"Config file {filename} not found for user {user_id}")
                return None
                
            content = blob.download_as_bytes()
            
            # Try to parse as JSON if the file is json
            if filename.endswith('.json'):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON content from {filename}")
                    
            return content.decode('utf-8')
        except Exception as e:
            logger.error(f"Error getting config file {filename} for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def save_file_content(user_id, directory, filepath, content):
        """Save content to a file in the user's directory"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return False
            
        try:
            logger.info(f"Saving file {filepath} for user {user_id} to directory {directory}")
            blob = bucket.blob(f'users/{user_id}/{directory}/{filepath}')
            
            if isinstance(content, dict):
                # If content is a dict, save as JSON
                blob.upload_from_string(
                    json.dumps(content, indent=2, default=str),
                    content_type='application/json'
                )
            elif isinstance(content, str):
                # If content is a string, save as text
                blob.upload_from_string(content, content_type='text/plain; charset=utf-8')
            elif isinstance(content, bytes):
                # If content is bytes, save as binary
                blob.upload_from_string(content)
            else:
                # Try to convert to string
                blob.upload_from_string(str(content))
            
            logger.info(f"File {filepath} saved successfully for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving file {filepath} for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_file_content(user_id, directory, filepath):
        """Get content from a file in the user's directory"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None
            
        try:
            logger.info(f"Getting file {filepath} for user {user_id} from directory {directory}")
            blob = bucket.blob(f'users/{user_id}/{directory}/{filepath}')
            
            if not blob.exists():
                logger.info(f"File {filepath} not found for user {user_id}")
                return None
                
            content = blob.download_as_bytes()
            
            # Try to decode as text if it's a text file
            if filepath.endswith(('.txt', '.md', '.json')):
                try:
                    text_content = content.decode('utf-8')
                    # Try to parse as JSON if the file is json
                    if filepath.endswith('.json'):
                        try:
                            return json.loads(text_content)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON content from {filepath}")
                            return text_content
                    return text_content
                except UnicodeDecodeError:
                    logger.warning(f"Failed to decode {filepath} as text, returning bytes")
                    return content
            
            # Return bytes for binary files
            return content
        except Exception as e:
            logger.error(f"Error getting file {filepath} for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def list_files(user_id, directory='data'):
        """List files in a user directory"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return []
            
        try:
            logger.info(f"Listing files for user {user_id} in directory {directory}")
            prefix = f'users/{user_id}/{directory}/'
            blobs = bucket.list_blobs(prefix=prefix)
            
            # Filter out directory markers and remove prefix from names
            files = []
            for blob in blobs:
                name = blob.name.replace(prefix, '')
                if name and not name.endswith('/.keep'):
                    # Create signed URL for access
                    url = blob.generate_signed_url(
                        version='v4',
                        expiration=3600,
                        method='GET'
                    )
                    
                    files.append({
                        'name': name,
                        'size': blob.size,
                        'updated': blob.time_created,
                        'url': url
                    })
            
            logger.info(f"Found {len(files)} files for user {user_id} in directory {directory}")
            return files
        except Exception as e:
            logger.error(f"Error listing files for user {user_id}: {str(e)}")
            return []
    
    @staticmethod
    def upload_file(user_id, directory, filename, file_object, expiration_seconds=604800, make_public=False):
        """Upload a file to the user's directory with configurable URL expiration

        Args:
            user_id: User ID
            directory: Storage directory
            filename: Filename
            file_object: File object to upload
            expiration_seconds: URL expiration time in seconds (default: 7 days)
            make_public: If True, make file publicly accessible without signed URL
        """
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None

        try:
            logger.info(f"Uploading file {filename} for user {user_id} to directory {directory}")
            blob = bucket.blob(f'users/{user_id}/{directory}/{filename}')
            blob.upload_from_file(file_object)

            if make_public:
                # Make the blob publicly accessible
                blob.make_public()
                url = blob.public_url
                logger.info(f"File {filename} uploaded successfully for user {user_id} as public URL")
            else:
                # Generate a signed URL for access with configurable expiration
                url = blob.generate_signed_url(
                    version='v4',
                    expiration=expiration_seconds,
                    method='GET'
                )
                logger.info(f"File {filename} uploaded successfully for user {user_id} with {expiration_seconds}s URL expiration")

            return {
                'path': blob.name,
                'url': url
            }
        except Exception as e:
            logger.error(f"Error uploading file {filename} for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def delete_file(user_id, directory, filename):
        """Delete a file from the user's directory"""
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return False

        try:
            logger.info(f"Deleting file {filename} for user {user_id} from directory {directory}")
            blob = bucket.blob(f'users/{user_id}/{directory}/{filename}')

            if not blob.exists():
                logger.info(f"File {filename} not found for user {user_id}")
                return False

            blob.delete()
            logger.info(f"File {filename} deleted successfully for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {filename} for user {user_id}: {str(e)}")
            return False

    @staticmethod
    def generate_upload_signed_url(user_id, directory, filename, content_type='video/mp4', expiration_seconds=3600):
        """Generate a signed URL for direct upload to Firebase Storage from client

        Note: This returns metadata for server-side upload. Direct browser uploads require CORS configuration.
        For large files, use this to get the path, then upload server-side using upload_file_from_client.

        Args:
            user_id: User ID
            directory: Storage directory
            filename: Filename
            content_type: MIME type of the file
            expiration_seconds: URL expiration time in seconds (default: 1 hour)

        Returns:
            dict with 'file_path', 'blob_name' for server-side upload
        """
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None

        try:
            blob_path = f'users/{user_id}/{directory}/{filename}'
            blob = bucket.blob(blob_path)

            logger.info(f"Generated upload path for {blob_path}")

            # Return metadata for upload - server will handle the actual upload
            return {
                'file_path': blob_path,
                'blob_name': blob.name,
                'bucket_name': bucket.name
            }

        except Exception as e:
            logger.error(f"Error generating upload path: {str(e)}")
            return None

    @staticmethod
    def upload_large_file_chunked(user_id, directory, filename, file_stream, content_type='video/mp4'):
        """Upload a large file to Firebase Storage in chunks

        Args:
            user_id: User ID
            directory: Storage directory
            filename: Filename
            file_stream: File stream or file-like object
            content_type: MIME type of the file

        Returns:
            dict with 'path', 'url', and 'thumbnail_url' on success, None on failure
        """
        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None

        try:
            blob_path = f'users/{user_id}/{directory}/{filename}'
            blob = bucket.blob(blob_path)
            blob.content_type = content_type

            # Upload from file stream (handles large files efficiently)
            logger.info(f"Starting chunked upload for {blob_path}")
            blob.upload_from_file(file_stream, content_type=content_type, timeout=3600)

            # Make publicly accessible
            blob.make_public()
            url = blob.public_url

            logger.info(f"Chunked upload completed for {blob_path}")

            # Generate thumbnail from first frame
            thumbnail_url = None
            try:
                thumbnail_url = StorageService.generate_video_thumbnail(user_id, directory, filename, blob_path)
            except Exception as e:
                logger.warning(f"Could not generate thumbnail for {filename}: {e}")

            return {
                'path': blob.name,
                'url': url,
                'thumbnail_url': thumbnail_url
            }

        except Exception as e:
            logger.error(f"Error uploading large file {filename}: {str(e)}")
            return None

    @staticmethod
    def generate_video_thumbnail(user_id, directory, filename, video_blob_path):
        """Generate thumbnail from first frame of video using ffmpeg

        Args:
            user_id: User ID
            directory: Storage directory
            filename: Original video filename
            video_blob_path: Path to video blob in Firebase Storage

        Returns:
            str: Public URL of generated thumbnail, or None on failure
        """
        import tempfile
        import subprocess
        import os

        if not bucket:
            logger.error("Firebase Storage not initialized")
            return None

        try:
            # Download video to temp file
            video_blob = bucket.blob(video_blob_path)
            temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            temp_video.close()

            logger.info(f"Downloading video for thumbnail generation: {video_blob_path}")
            video_blob.download_to_filename(temp_video.name)

            # Generate thumbnail using ffmpeg (extract first frame)
            thumbnail_filename = filename.rsplit('.', 1)[0] + '_thumb.jpg'
            temp_thumbnail = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_thumbnail.close()

            logger.info(f"Generating thumbnail from first frame")
            subprocess.run([
                'ffmpeg',
                '-i', temp_video.name,
                '-vframes', '1',  # Extract only 1 frame
                '-vf', 'scale=320:-1',  # Scale to 320px width, maintain aspect ratio
                '-y',  # Overwrite output file
                temp_thumbnail.name
            ], check=True, capture_output=True, timeout=30)

            # Upload thumbnail to Firebase
            thumbnail_blob_path = f'users/{user_id}/{directory}/thumbnails/{thumbnail_filename}'
            thumbnail_blob = bucket.blob(thumbnail_blob_path)

            with open(temp_thumbnail.name, 'rb') as f:
                thumbnail_blob.upload_from_file(f, content_type='image/jpeg')

            thumbnail_blob.make_public()
            thumbnail_url = thumbnail_blob.public_url

            logger.info(f"Thumbnail generated and uploaded: {thumbnail_url}")

            # Cleanup temp files
            try:
                os.unlink(temp_video.name)
                os.unlink(temp_thumbnail.name)
            except Exception as e:
                logger.warning(f"Could not delete temp files: {e}")

            return thumbnail_url

        except subprocess.TimeoutExpired:
            logger.error("Thumbnail generation timed out")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg error generating thumbnail: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return None


class TikTokTrendFinderService:
    """
    Service for global TikTok Trend Finder data
    Stores analysis results that are shared across all users
    """

    COLLECTION_NAME = 'tiktok_trend_finder'
    DOCUMENT_ID = 'latest_analysis'

    @staticmethod
    def save_analysis(analysis_data):
        """
        Save the latest trend analysis (replaces previous one)

        Args:
            analysis_data: Dict containing:
                - total_keywords_fetched: int
                - gaming_keywords_found: int
                - keywords_analyzed: int
                - results: list of keyword analysis results
                - analyzed_at: ISO timestamp

        Returns:
            bool: True if successful
        """
        if not db:
            logger.error("Firestore not initialized")
            return False

        try:
            # Add server timestamp
            analysis_data['updated_at'] = firestore.SERVER_TIMESTAMP

            # Save to Firestore (overwrites previous document)
            doc_ref = db.collection(TikTokTrendFinderService.COLLECTION_NAME).document(
                TikTokTrendFinderService.DOCUMENT_ID
            )
            doc_ref.set(analysis_data)

            logger.info(f"Saved TikTok Trend Finder analysis with {len(analysis_data.get('results', []))} keywords")
            return True

        except Exception as e:
            logger.error(f"Error saving TikTok Trend Finder analysis: {str(e)}")
            return False

    @staticmethod
    def get_latest_analysis():
        """
        Get the latest trend analysis

        Returns:
            dict: Analysis data or None if not found
        """
        if not db:
            logger.error("Firestore not initialized")
            return None

        try:
            doc_ref = db.collection(TikTokTrendFinderService.COLLECTION_NAME).document(
                TikTokTrendFinderService.DOCUMENT_ID
            )
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                logger.info(f"Retrieved TikTok Trend Finder analysis with {len(data.get('results', []))} keywords")
                return data
            else:
                logger.info("No TikTok Trend Finder analysis found in database")
                return None

        except Exception as e:
            logger.error(f"Error getting TikTok Trend Finder analysis: {str(e)}")
            return None

    @staticmethod
    def delete_analysis():
        """
        Delete the stored analysis

        Returns:
            bool: True if successful
        """
        if not db:
            logger.error("Firestore not initialized")
            return False

        try:
            doc_ref = db.collection(TikTokTrendFinderService.COLLECTION_NAME).document(
                TikTokTrendFinderService.DOCUMENT_ID
            )
            doc_ref.delete()

            logger.info("Deleted TikTok Trend Finder analysis")
            return True

        except Exception as e:
            logger.error(f"Error deleting TikTok Trend Finder analysis: {str(e)}")
            return False