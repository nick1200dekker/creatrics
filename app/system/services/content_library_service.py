"""
Content Library Service
Manages cross-platform content reposting using Firestore
Structure: users/{user_id}/repost/{content_id}
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.system.services.firebase_service import db, storage_bucket

logger = logging.getLogger('content_library_service')


class ContentLibraryManager:
    """Manage content library for cross-platform reposting"""

    COLLECTION_PATH = 'repost'  # users/{user_id}/repost/{content_id}

    @staticmethod
    def save_content(
        user_id: str,
        media_url: str,
        media_type: str,
        keywords: str = None,
        content_description: str = None,
        thumbnail_url: str = None,
        duration: int = None,
        file_size: int = None,
        platform: str = None,
        platform_data: Dict = None
    ) -> Optional[str]:
        """
        Save content to library for reposting

        Args:
            user_id: User ID
            media_url: Firebase Storage URL
            media_type: 'video' or 'image'
            keywords: Keywords entered by user
            content_description: Description entered by user
            thumbnail_url: Optional thumbnail URL
            duration: Video duration in seconds
            file_size: File size in bytes
            platform: Platform where first posted (youtube, tiktok, instagram, x)
            platform_data: Platform-specific data (post_id, scheduled_for, title, etc.)

        Returns:
            content_id if successful, None otherwise
        """
        if not db:
            logger.error("Firestore not initialized")
            return None

        try:
            # Create content document
            content_ref = db.collection('users').document(user_id).collection(ContentLibraryManager.COLLECTION_PATH).document()
            content_id = content_ref.id

            content_data = {
                'media_url': media_url,
                'media_type': media_type,
                'keywords': keywords or '',
                'content_description': content_description or '',
                'thumbnail_url': thumbnail_url,
                'duration': duration,
                'file_size': file_size,
                'platforms_posted': {},
                'created_at': datetime.utcnow(),
                'last_action_at': datetime.utcnow(),  # Track last schedule/post time for expiration
            }

            # Add initial platform data if provided
            if platform and platform_data:
                platform_entry = {
                    'post_id': platform_data.get('post_id'),
                    'scheduled_for': platform_data.get('scheduled_for'),
                    'title': platform_data.get('title'),
                    'status': platform_data.get('status', 'posted')
                }

                # Only set posted_at if actually posted (not scheduled)
                if platform_data.get('status') != 'scheduled':
                    platform_entry['posted_at'] = datetime.utcnow()

                content_data['platforms_posted'][platform] = platform_entry
                # Update last_action_at when platform is added
                content_data['last_action_at'] = datetime.utcnow()

            content_ref.set(content_data)
            logger.info(f"Saved content {content_id} to library for user {user_id}")
            return content_id

        except Exception as e:
            logger.error(f"Error saving content to library: {str(e)}")
            return None

    @staticmethod
    def update_platform_status(
        user_id: str,
        content_id: str,
        platform: str,
        platform_data: Dict
    ) -> bool:
        """
        Update content with new platform posting info

        Args:
            user_id: User ID
            content_id: Content ID
            platform: Platform name (youtube, tiktok, instagram, x)
            platform_data: Platform-specific data

        Returns:
            True if successful, False otherwise
        """
        if not db:
            logger.error("Firestore not initialized")
            return False

        try:
            content_ref = db.collection('users').document(user_id).collection(ContentLibraryManager.COLLECTION_PATH).document(content_id)

            # Build platform entry
            platform_entry = {
                'post_id': platform_data.get('post_id'),
                'scheduled_for': platform_data.get('scheduled_for'),
                'title': platform_data.get('title'),
                'status': platform_data.get('status', 'posted')
            }

            # Only set posted_at if actually posted (not scheduled)
            if platform_data.get('status') != 'scheduled':
                platform_entry['posted_at'] = datetime.utcnow()

            # Update platforms_posted AND last_action_at
            content_ref.update({
                f'platforms_posted.{platform}': platform_entry,
                'last_action_at': datetime.utcnow()  # Update expiration timer on every new post/schedule
            })

            logger.info(f"Updated content {content_id} with {platform} data")
            return True

        except Exception as e:
            logger.error(f"Error updating platform status: {str(e)}")
            return False

    @staticmethod
    def get_recent_content(
        user_id: str,
        media_type_filter: str = None,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get recent content for reposting

        Args:
            user_id: User ID
            media_type_filter: Optional filter ('video' or 'image')
            hours: How many hours back to look (default 24)

        Returns:
            List of content documents
        """
        if not db:
            logger.error("Firestore not initialized")
            return []

        try:
            # Query content from last X hours
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Get all content for this user from last X hours (ordered by created_at)
            query = db.collection('users').document(user_id).collection(ContentLibraryManager.COLLECTION_PATH) \
                .where('created_at', '>=', cutoff_time) \
                .order_by('created_at', direction='DESCENDING')

            docs = query.stream()

            content_list = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id

                # Filter by media type in Python (avoids needing composite index)
                if media_type_filter and data.get('media_type') != media_type_filter:
                    continue

                content_list.append(data)

            logger.info(f"Retrieved {len(content_list)} content items for user {user_id}")
            return content_list

        except Exception as e:
            logger.error(f"Error getting recent content: {str(e)}")
            return []

    @staticmethod
    def get_content_by_id(user_id: str, content_id: str) -> Optional[Dict]:
        """
        Get specific content by ID

        Args:
            user_id: User ID
            content_id: Content ID

        Returns:
            Content data or None
        """
        if not db:
            logger.error("Firestore not initialized")
            return None

        try:
            doc_ref = db.collection('users').document(user_id).collection(ContentLibraryManager.COLLECTION_PATH).document(content_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            else:
                logger.warning(f"Content {content_id} not found for user {user_id}")
                return None

        except Exception as e:
            logger.error(f"Error getting content by ID: {str(e)}")
            return None

    @staticmethod
    def delete_content(user_id: str, content_id: str) -> bool:
        """
        Delete content from library

        Args:
            user_id: User ID
            content_id: Content ID

        Returns:
            True if successful, False otherwise
        """
        if not db:
            logger.error("Firestore not initialized")
            return False

        try:
            doc_ref = db.collection('users').document(user_id).collection(ContentLibraryManager.COLLECTION_PATH).document(content_id)
            doc_ref.delete()
            logger.info(f"Deleted content {content_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting content: {str(e)}")
            return False

    @staticmethod
    def cleanup_expired_content(user_id: str = None, hours: int = 24) -> int:
        """
        Clean up content older than specified hours
        Also deletes associated Firebase Storage files

        Args:
            user_id: Optional specific user ID, otherwise cleans for all users
            hours: Age threshold in hours (default 24)

        Returns:
            Number of items deleted
        """
        if not db:
            logger.error("Firestore not initialized")
            return 0

        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            deleted_count = 0

            # If specific user, clean only their content
            if user_id:
                users_to_clean = [user_id]
            else:
                # Get all users (this could be optimized with a dedicated collection)
                users_ref = db.collection('users').stream()
                users_to_clean = [user.id for user in users_ref]

            for uid in users_to_clean:
                # Get all content for this user
                all_content = db.collection('users').document(uid).collection(ContentLibraryManager.COLLECTION_PATH).stream()

                for doc in all_content:
                    try:
                        data = doc.to_dict()

                        # Check if content should be deleted
                        # Only delete 24 hours after the LATEST scheduled post has gone live
                        platforms_posted = data.get('platforms_posted', {})

                        # Find the latest scheduled_for time across all platforms
                        latest_scheduled = None
                        for platform, platform_data in platforms_posted.items():
                            scheduled_for = platform_data.get('scheduled_for')
                            if scheduled_for:
                                # Convert to datetime if it's a string
                                if isinstance(scheduled_for, str):
                                    scheduled_for = datetime.fromisoformat(scheduled_for.replace('Z', '+00:00'))

                                if latest_scheduled is None or scheduled_for > latest_scheduled:
                                    latest_scheduled = scheduled_for

                        # Determine deletion time
                        # If there are scheduled posts, wait 24 hours after the latest one
                        # Otherwise, use last_action_at
                        deletion_threshold = latest_scheduled if latest_scheduled else data.get('last_action_at')

                        if not deletion_threshold:
                            continue  # Skip if no timestamp available

                        # Only delete if 24 hours have passed since deletion_threshold
                        if deletion_threshold >= cutoff_time:
                            continue  # Not old enough to delete

                        media_url = data.get('media_url')

                        # Delete from Firebase Storage
                        if media_url and storage_bucket:
                            try:
                                # Extract blob path from URL
                                # URL format: https://storage.googleapis.com/bucket/path/to/file
                                if 'storage.googleapis.com' in media_url:
                                    path = media_url.split(storage_bucket.name + '/')[-1]
                                    blob = storage_bucket.blob(path)
                                    blob.delete()
                                    logger.info(f"Deleted storage file: {path}")
                            except Exception as storage_error:
                                logger.error(f"Error deleting storage file: {storage_error}")

                        # Delete Firestore document
                        doc.reference.delete()
                        deleted_count += 1

                    except Exception as item_error:
                        logger.error(f"Error deleting content item: {item_error}")
                        continue

            logger.info(f"Cleanup completed: deleted {deleted_count} expired content items")
            return deleted_count

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return 0
