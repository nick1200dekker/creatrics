"""
Content Calendar Manager Module
Handles storing and retrieving content calendar events using Firestore.
Updated to include status, content_link, comments, and notes fields.
"""
import uuid
from datetime import datetime
import logging
from typing import List, Dict, Optional

from firebase_admin import firestore

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ContentCalendarManager:
    """Class to manage content calendar events for a user using Firestore"""
    
    def __init__(self, user_id: str):
        """Initialize ContentCalendarManager with user_id"""
        self.user_id = user_id
        self.db = firestore.client()
        self.user_collection = f'users/{user_id}/content_calendar'
        
        logger.info(f"Initialized ContentCalendarManager for user: {user_id}")
        logger.debug(f"Using collection path: {self.user_collection}")
    
    def _event_to_dict(self, event_doc) -> Dict:
        """Convert Firestore document to dictionary with proper serialization"""
        if not event_doc.exists:
            return None
        
        data = event_doc.to_dict()
        
        # Convert Firestore timestamps to ISO strings for JSON serialization
        if 'created_at' in data and hasattr(data['created_at'], 'isoformat'):
            data['created_at'] = data['created_at'].isoformat()
        elif 'created_at' in data and hasattr(data['created_at'], 'timestamp'):
            data['created_at'] = datetime.fromtimestamp(data['created_at'].timestamp()).isoformat()
            
        if 'updated_at' in data and hasattr(data['updated_at'], 'isoformat'):
            data['updated_at'] = data['updated_at'].isoformat()
        elif 'updated_at' in data and hasattr(data['updated_at'], 'timestamp'):
            data['updated_at'] = datetime.fromtimestamp(data['updated_at'].timestamp()).isoformat()
        
        return data
    
    def get_all_events(self) -> List[Dict]:
        """Get all calendar events for the user"""
        try:
            # Query user's own subcollection - much faster and more scalable!
            events_ref = self.db.collection(self.user_collection)
            query = events_ref.order_by('publish_date')
            
            events = []
            for doc in query.stream():
                event_data = self._event_to_dict(doc)
                if event_data:
                    events.append(event_data)
            
            logger.info(f"Retrieved {len(events)} events for user {self.user_id}")
            return events
            
        except Exception as e:
            logger.error(f"Error loading events for user {self.user_id}: {str(e)}")
            return []
    
    def create_event(self, title: str, publish_date: str, is_paid: bool = False,
                     is_free: bool = True, is_sponsored: bool = False,
                     category: str = "", audience_type: str = "Public",
                     content_type: str = "", platform: str = "",
                     description: str = "", color: str = "#20D7D7",
                     content_link: str = "", status: str = "planned",
                     comments: List[Dict] = None, notes: str = "",
                     youtube_video_id: str = "", instagram_post_id: str = "",
                     tiktok_post_id: str = "", x_post_id: str = "") -> str:
        """Create a new calendar event with new fields"""
        try:
            # Generate a unique ID for the event
            event_id = str(uuid.uuid4())

            # Create the event object (no user_id needed since it's in the path)
            event_data = {
                "id": event_id,
                "title": title,
                "publish_date": publish_date,
                "is_paid": is_paid,
                "is_free": is_free,  # This now represents "organic" content rather than free
                "is_sponsored": is_sponsored,
                "category": category,
                "audience_type": audience_type,
                "content_type": content_type or platform,  # Default to platform if content_type is empty
                "platform": platform,
                "description": description,
                "color": color,
                "content_link": content_link,  # New field
                "status": status,  # New field: planned, in-progress, review, ready, posted
                "comments": comments or [],  # New field: list of comment objects
                "notes": notes,  # New field: concepts, requirements, research notes
                "youtube_video_id": youtube_video_id,  # YouTube video ID for scheduled videos
                "instagram_post_id": instagram_post_id,  # Instagram post ID for scheduled posts
                "tiktok_post_id": tiktok_post_id,  # TikTok post ID for scheduled posts
                "x_post_id": x_post_id,  # X/Twitter post ID for scheduled posts
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            # Save to user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            doc_ref.set(event_data)
            
            logger.info(f"Created event: {event_id} - {title} for user {self.user_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Error creating event for user {self.user_id}: {str(e)}")
            raise e
    
    def update_event(self, event_id: str, **kwargs) -> bool:
        """Update an existing calendar event"""
        try:
            # Access document directly in user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            
            # Check if document exists
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Event not found: {event_id} for user {self.user_id}")
                return False
            
            # No need to verify user ownership since we're in their subcollection
            event_data = doc.to_dict()
            
            # Prepare update data
            update_data = {}
            
            # Only update fields that are provided and not None
            allowed_fields = [
                'title', 'publish_date', 'is_paid', 'is_free', 'is_sponsored',
                'category', 'audience_type', 'content_type', 'platform', 
                'description', 'color', 'content_link', 'status', 'comments', 'notes'
            ]
            
            for key, value in kwargs.items():
                if key in allowed_fields and value is not None:
                    update_data[key] = value
                    logger.info(f"Updating field {key}: {event_data.get(key)} -> {value}")
            
            # Always update the timestamp
            update_data["updated_at"] = datetime.now()
            
            # Perform the update
            doc_ref.update(update_data)
            
            logger.info(f"Updated event: {event_id} for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating event {event_id} for user {self.user_id}: {str(e)}")
            raise e
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event"""
        try:
            # Access document directly in user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            
            # Check if document exists
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Event not found: {event_id} for user {self.user_id}")
                return False
            
            # No need to verify user ownership since we're in their subcollection
            # Delete the document
            doc_ref.delete()
            
            logger.info(f"Deleted event: {event_id} for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting event {event_id} for user {self.user_id}: {str(e)}")
            raise e
    
    def get_event(self, event_id: str) -> Optional[Dict]:
        """Get a specific event by ID"""
        try:
            # Access document directly in user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            # No need to verify user ownership since we're in their subcollection
            return self._event_to_dict(doc)
            
        except Exception as e:
            logger.error(f"Error getting event {event_id} for user {self.user_id}: {str(e)}")
            return None
    
    def get_events_by_date_range(self, start_date: str, end_date: str, limit: int = 1000) -> List[Dict]:
        """Get events within a specific date range for better performance with large datasets"""
        try:
            events_ref = self.db.collection(self.user_collection)
            query = (events_ref
                    .where('publish_date', '>=', start_date)
                    .where('publish_date', '<=', end_date)
                    .order_by('publish_date')
                    .limit(limit))
            
            events = []
            for doc in query.stream():
                event_data = self._event_to_dict(doc)
                if event_data:
                    events.append(event_data)
            
            logger.info(f"Retrieved {len(events)} events for user {self.user_id} in date range {start_date} to {end_date}")
            return events
            
        except Exception as e:
            logger.error(f"Error loading events by date range for user {self.user_id}: {str(e)}")
            return []
    
    def add_comment_to_event(self, event_id: str, comment_text: str) -> bool:
        """Add a comment to an existing event"""
        try:
            # Access document directly in user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            
            # Check if document exists
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Event not found: {event_id} for user {self.user_id}")
                return False
            
            event_data = doc.to_dict()
            comments = event_data.get('comments', [])
            
            # Create new comment
            new_comment = {
                'text': comment_text,
                'date': datetime.now().isoformat()
            }
            
            comments.append(new_comment)
            
            # Update the event with new comments
            doc_ref.update({
                'comments': comments,
                'updated_at': datetime.now()
            })
            
            logger.info(f"Added comment to event: {event_id} for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding comment to event {event_id} for user {self.user_id}: {str(e)}")
            raise e
    
    def update_event_status(self, event_id: str, status: str) -> bool:
        """Update the status of an event"""
        try:
            valid_statuses = ['planned', 'in-progress', 'review', 'ready', 'posted']
            if status not in valid_statuses:
                logger.warning(f"Invalid status: {status}. Must be one of {valid_statuses}")
                return False
            
            # Access document directly in user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            
            # Check if document exists
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Event not found: {event_id} for user {self.user_id}")
                return False
            
            # Update the status
            doc_ref.update({
                'status': status,
                'updated_at': datetime.now()
            })
            
            logger.info(f"Updated status for event: {event_id} to {status} for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating status for event {event_id} for user {self.user_id}: {str(e)}")
            raise e
    
    def update_event_notes(self, event_id: str, notes: str) -> bool:
        """Update the notes of an event"""
        try:
            # Access document directly in user's subcollection
            doc_ref = self.db.collection(self.user_collection).document(event_id)
            
            # Check if document exists
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Event not found: {event_id} for user {self.user_id}")
                return False
            
            # Update the notes
            doc_ref.update({
                'notes': notes,
                'updated_at': datetime.now()
            })
            
            logger.info(f"Updated notes for event: {event_id} for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating notes for event {event_id} for user {self.user_id}: {str(e)}")
            raise e
    
    def get_events_by_status(self, status: str) -> List[Dict]:
        """Get all events with a specific status"""
        try:
            events_ref = self.db.collection(self.user_collection)
            query = events_ref.where('status', '==', status).order_by('publish_date')
            
            events = []
            for doc in query.stream():
                event_data = self._event_to_dict(doc)
                if event_data:
                    events.append(event_data)
            
            logger.info(f"Retrieved {len(events)} events with status '{status}' for user {self.user_id}")
            return events
            
        except Exception as e:
            logger.error(f"Error loading events by status for user {self.user_id}: {str(e)}")
            return []