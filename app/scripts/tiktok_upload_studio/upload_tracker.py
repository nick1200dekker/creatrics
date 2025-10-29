"""
TikTok Upload Tracker
Tracks upload progress and status in Firestore
"""

import logging
from datetime import datetime
from app.system.services.firebase_service import db

logger = logging.getLogger('upload_tracker')


class UploadTracker:
    """Track upload progress in Firestore"""

    COLLECTION = 'tiktok_uploads'

    @staticmethod
    def create_upload(user_id, filename, file_size, title, privacy_level, mode):
        """
        Create a new upload tracking record

        Args:
            user_id: User's ID
            filename: Original filename
            file_size: File size in bytes
            title: Video title
            privacy_level: Privacy level
            mode: Upload mode (direct/inbox)

        Returns:
            str: Upload ID
        """
        try:
            if not db:
                logger.error("Firestore not initialized")
                return None

            # Create new upload document
            upload_ref = db.collection(UploadTracker.COLLECTION).document()
            upload_id = upload_ref.id

            upload_data = {
                'upload_id': upload_id,
                'user_id': user_id,
                'filename': filename,
                'file_size': file_size,
                'title': title,
                'privacy_level': privacy_level,
                'mode': mode,
                'status': 'initializing',  # initializing, uploading, processing, completed, failed
                'progress': 0,
                'error': None,
                'publish_id': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }

            upload_ref.set(upload_data)
            logger.info(f"Created upload tracking record: {upload_id}")

            return upload_id

        except Exception as e:
            logger.error(f"Error creating upload record: {str(e)}")
            return None

    @staticmethod
    def update_status(upload_id, status, progress=None, error=None, publish_id=None, message=None):
        """
        Update upload status

        Args:
            upload_id: Upload ID
            status: New status
            progress: Progress percentage (0-100)
            error: Error message (if failed)
            publish_id: TikTok publish ID
            message: Additional message
        """
        try:
            if not db:
                logger.error("Firestore not initialized")
                return

            upload_ref = db.collection(UploadTracker.COLLECTION).document(upload_id)

            update_data = {
                'status': status,
                'updated_at': datetime.now()
            }

            if progress is not None:
                update_data['progress'] = progress

            if error is not None:
                update_data['error'] = error

            if publish_id is not None:
                update_data['publish_id'] = publish_id

            if message is not None:
                update_data['message'] = message

            upload_ref.update(update_data)
            logger.info(f"Updated upload {upload_id}: status={status}, progress={progress}")

        except Exception as e:
            logger.error(f"Error updating upload status: {str(e)}")

    @staticmethod
    def get_upload(upload_id):
        """
        Get upload status

        Args:
            upload_id: Upload ID

        Returns:
            dict: Upload data
        """
        try:
            if not db:
                logger.error("Firestore not initialized")
                return None

            upload_ref = db.collection(UploadTracker.COLLECTION).document(upload_id)
            upload_doc = upload_ref.get()

            if upload_doc.exists:
                return upload_doc.to_dict()
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting upload status: {str(e)}")
            return None

    @staticmethod
    def get_user_uploads(user_id, limit=10):
        """
        Get recent uploads for a user

        Args:
            user_id: User's ID
            limit: Number of uploads to retrieve

        Returns:
            list: List of upload records
        """
        try:
            if not db:
                logger.error("Firestore not initialized")
                return []

            uploads_ref = db.collection(UploadTracker.COLLECTION)
            query = uploads_ref.where('user_id', '==', user_id).order_by('created_at', direction='DESCENDING').limit(limit)

            uploads = []
            for doc in query.stream():
                uploads.append(doc.to_dict())

            return uploads

        except Exception as e:
            logger.error(f"Error getting user uploads: {str(e)}")
            return []

    @staticmethod
    def delete_old_uploads(days=7):
        """
        Delete upload records older than specified days

        Args:
            days: Number of days to keep

        Returns:
            int: Number of deleted records
        """
        try:
            if not db:
                logger.error("Firestore not initialized")
                return 0

            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)

            uploads_ref = db.collection(UploadTracker.COLLECTION)
            query = uploads_ref.where('created_at', '<', cutoff_date)

            deleted = 0
            for doc in query.stream():
                doc.reference.delete()
                deleted += 1

            logger.info(f"Deleted {deleted} old upload records")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting old uploads: {str(e)}")
            return 0
