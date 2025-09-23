"""
YouTube Analytics module for fetching and processing YouTube metrics
Data range: Last 90 days with enhanced engagement metrics
Updated with latest and historical storage
"""
import os
import json
import logging
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get encryption key
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key()
    os.environ['ENCRYPTION_KEY'] = ENCRYPTION_KEY.decode() if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def decrypt_token(encrypted_token):
    """Decrypt token data for use"""
    try:
        decrypted_token = cipher_suite.decrypt(encrypted_token.encode())
        return json.loads(decrypted_token.decode())
    except Exception as e:
        logger.error(f"Error decrypting token: {str(e)}")
        return None

class YouTubeAnalytics:
    """Handle YouTube analytics data fetching and processing"""
    
    def __init__(self, user_id):
        """Initialize the YouTube Analytics object"""
        self.user_id = user_id
        
        # Initialize Firestore
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        self.db = firestore.client()
        
        # Get user data and setup credentials
        user_data = self._get_user_data()
        if not user_data:
            self.credentials = None
            self.channel_id = None
            self.channel_name = None
            return
        
        # Setup credentials
        encrypted_creds = user_data.get('youtube_credentials')
        if not encrypted_creds:
            self.credentials = None
            self.channel_id = None
            self.channel_name = None
            return
        
        creds_dict = decrypt_token(encrypted_creds)
        if not creds_dict:
            self.credentials = None
            self.channel_id = None
            self.channel_name = None
            return
        
        # Parse expiry
        expiry = None
        if creds_dict.get('expiry'):
            try:
                expiry = datetime.fromisoformat(creds_dict['expiry'])
            except (ValueError, TypeError):
                expiry = None
        
        # Create credentials object
        self.credentials = Credentials(
            token=creds_dict.get('token'),
            refresh_token=creds_dict.get('refresh_token'),
            token_uri=creds_dict.get('token_uri'),
            client_id=creds_dict.get('client_id'),
            client_secret=creds_dict.get('client_secret'),
            scopes=creds_dict.get('scopes'),
            expiry=expiry
        )
        
        # Refresh if needed
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            self._refresh_credentials()
        
        # Get channel info
        self.channel_id = user_data.get('youtube_channel_id')
        self.channel_name = user_data.get('youtube_account')
    
    def _get_user_data(self):
        """Get user data from Firebase"""
        try:
            user_doc = self.db.collection('users').document(self.user_id).get()
            return user_doc.to_dict() if user_doc.exists else None
        except Exception as e:
            logger.error(f"Error getting user data: {str(e)}")
            return None
    
    def _refresh_credentials(self):
        """Refresh OAuth credentials and update in Firebase"""
        try:
            self.credentials.refresh(Request())
            
            # Update stored credentials
            creds_dict = {
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'token_uri': self.credentials.token_uri,
                'client_id': self.credentials.client_id,
                'client_secret': self.credentials.client_secret,
                'scopes': self.credentials.scopes,
                'expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
            
            encrypted_creds = cipher_suite.encrypt(json.dumps(creds_dict).encode()).decode()
            
            self.db.collection('users').document(self.user_id).update({
                'youtube_credentials': encrypted_creds
            })
            
        except Exception as e:
            logger.error(f"Error refreshing YouTube credentials: {str(e)}")
    
    def get_analytics_data(self):
        """Get comprehensive analytics data for YouTube channel"""
        if not self.credentials or not self.channel_id:
            logger.error("No valid credentials or channel ID")
            return None
        
        try:
            youtube_analytics = build('youtubeAnalytics', 'v2', credentials=self.credentials)
            
            # Date ranges
            end_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            start_date_90d = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            start_date_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Basic metrics
            metrics_90d = None
            try:
                metrics_90d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_90d,
                    endDate=end_date,
                    metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,likes,dislikes,comments,shares'
                ).execute()
            except Exception as e:
                logger.error(f"Error fetching basic metrics: {str(e)}")
            
            # Traffic sources
            traffic_sources = None
            try:
                traffic_sources = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_30d,
                    endDate=end_date,
                    dimensions='insightTrafficSourceType',
                    metrics='views',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch traffic sources: {str(e)}")
            
            # Top videos
            top_videos = None
            try:
                top_videos = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_30d,
                    endDate=end_date,
                    dimensions='video',
                    metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch top videos: {str(e)}")
            
            # Process the data
            processed_analytics = self._process_analytics(metrics_90d, traffic_sources, top_videos)
            
            # Store analytics data
            self._store_analytics(processed_analytics)
            
            return processed_analytics
            
        except HttpError as e:
            logger.error(f"HTTP error fetching analytics data: {e.content}")
            return None
        except Exception as e:
            logger.error(f"Error fetching analytics data: {str(e)}")
            return None
    
    def _process_analytics(self, metrics_90d, traffic_sources, top_videos):
        """Process raw analytics data into structured metrics"""
        now = datetime.now()
        
        processed = {
            "timestamp": now.isoformat(),
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "last_updated": now.strftime("%b %d, %Y %I:%M %p"),
            "date_range": "Last 90 days",
            
            # Core metrics
            "views": 0,
            "watch_time_minutes": 0,
            "watch_time_hours": 0,
            "avg_view_duration_seconds": 0,
            "subscribers_gained": 0,
            "subscribers_lost": 0,
            
            # Engagement metrics
            "likes": 0,
            "dislikes": 0,
            "comments": 0,
            "shares": 0,
            
            # Performance KPIs
            "average_view_percentage": 0,
            "engagement_rate": 0,
            "like_dislike_ratio": 0,
            "subscriber_conversion_rate": 0,
            
            # Calculated insights
            "avg_daily_views": 0,
            "avg_daily_watch_time": 0,
            "total_engagement": 0,
            
            # Data collections
            "traffic_sources": [],
            "top_videos": [],
            "status": "success"
        }
        
        # Process basic metrics
        if metrics_90d and 'rows' in metrics_90d and metrics_90d['rows']:
            row = metrics_90d['rows'][0]
            column_index = {col['name']: idx for idx, col in enumerate(metrics_90d['columnHeaders'])}
            
            processed["views"] = int(row[column_index.get('views', 0)])
            processed["watch_time_minutes"] = int(row[column_index.get('estimatedMinutesWatched', 0)])
            processed["watch_time_hours"] = round(processed["watch_time_minutes"] / 60, 1)
            processed["avg_view_duration_seconds"] = float(row[column_index.get('averageViewDuration', 0)])
            processed["subscribers_gained"] = int(row[column_index.get('subscribersGained', 0)])
            processed["subscribers_lost"] = int(row[column_index.get('subscribersLost', 0)])
            
            # Engagement metrics
            processed["likes"] = int(row[column_index.get('likes', 0)])
            processed["dislikes"] = int(row[column_index.get('dislikes', 0)])
            processed["comments"] = int(row[column_index.get('comments', 0)])
            processed["shares"] = int(row[column_index.get('shares', 0)])
            processed["average_view_percentage"] = float(row[column_index.get('averageViewPercentage', 0)])
            
            # Calculate KPIs
            processed["total_engagement"] = processed["likes"] + processed["comments"] + processed["shares"]
            
            if processed["views"] > 0:
                processed["engagement_rate"] = round((processed["total_engagement"] / processed["views"]) * 100, 2)
                processed["subscriber_conversion_rate"] = round((processed["subscribers_gained"] / processed["views"]) * 100, 4)
            
            total_reactions = processed["likes"] + processed["dislikes"]
            if total_reactions > 0:
                processed["like_dislike_ratio"] = round((processed["likes"] / total_reactions) * 100, 1)
            
            processed["avg_daily_views"] = round(processed["views"] / 90, 0)
            processed["avg_daily_watch_time"] = round(processed["watch_time_minutes"] / 90, 0)
        
        # Process traffic sources
        if traffic_sources and 'rows' in traffic_sources:
            column_index = {col['name']: idx for idx, col in enumerate(traffic_sources['columnHeaders'])}
            
            for row in traffic_sources['rows']:
                source_name = row[column_index['insightTrafficSourceType']]
                source_views = int(row[column_index['views']])
                
                processed["traffic_sources"].append({
                    "source": source_name,
                    "views": source_views,
                    "percentage": round((source_views / processed["views"] * 100), 2) if processed["views"] > 0 else 0
                })
        
        # Process top videos
        if top_videos and 'rows' in top_videos:
            column_index = {col['name']: idx for idx, col in enumerate(top_videos['columnHeaders'])}
            
            for row in top_videos['rows']:
                video_id = row[column_index['video']]
                if '==' in video_id:
                    video_id = video_id.split('==')[1]
                
                video_views = int(row[column_index['views']])
                video_likes = int(row[column_index.get('likes', 0)])
                video_comments = int(row[column_index.get('comments', 0)])
                video_shares = int(row[column_index.get('shares', 0)])
                video_total_engagement = video_likes + video_comments + video_shares
                
                processed["top_videos"].append({
                    "id": video_id,
                    "views": video_views,
                    "watch_time_minutes": int(row[column_index['estimatedMinutesWatched']]),
                    "avg_view_duration": float(row[column_index['averageViewDuration']]),
                    "avg_view_percentage": float(row[column_index.get('averageViewPercentage', 0)]),
                    "likes": video_likes,
                    "dislikes": int(row[column_index.get('dislikes', 0)]),
                    "comments": video_comments,
                    "shares": video_shares,
                    "subscribers_gained": int(row[column_index.get('subscribersGained', 0)]),
                    "engagement_rate": round((video_total_engagement / video_views) * 100, 2) if video_views > 0 else 0
                })
        
        return processed
    
    def _store_analytics(self, analytics_data):
        """Store analytics data in Firebase with both latest and historical data"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Store as latest (for dashboard)
            latest_ref = self.db.collection('users').document(self.user_id).collection('youtube_analytics').document('latest')
            latest_ref.set(analytics_data)
            
            # Store as historical data
            history_ref = self.db.collection('users').document(self.user_id).collection('youtube_analytics').document('history').collection('daily').document(today)
            history_ref.set(analytics_data)
            
            logger.info(f"YouTube Analytics stored successfully in Firebase for user {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing YouTube analytics: {str(e)}")
            return False

def fetch_youtube_analytics(user_id):
    """Fetch YouTube analytics data for a user"""
    try:
        analytics = YouTubeAnalytics(user_id)
        if not analytics.credentials:
            logger.error(f"Failed to initialize YouTubeAnalytics - no valid credentials")
            return None
        
        result = analytics.get_analytics_data()
        if result:
            logger.info(f"YouTube analytics fetch completed successfully for user {user_id}")
        else:
            logger.error(f"YouTube analytics fetch failed for user {user_id}")
            
        return result
    except Exception as e:
        logger.error(f"YouTube analytics fetch exception for user {user_id}: {str(e)}")
        return None

def clean_youtube_user_data(user_id):
    """Clean all YouTube analytics data for a user when they disconnect their account"""
    try:
        # Initialize Firestore
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass
        
        db = firestore.client()
        
        deleted_count = 0
        
        # Delete latest analytics document
        latest_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
        if latest_ref.get().exists:
            latest_ref.delete()
            deleted_count += 1
        
        # Delete historical data
        history_collection = db.collection('users').document(user_id).collection('youtube_analytics').document('history').collection('daily')
        history_docs = history_collection.stream()
        for doc in history_docs:
            doc.reference.delete()
            deleted_count += 1
        
        # Delete videos document if it exists
        videos_ref = db.collection('users').document(user_id).collection('youtube_videos').document('recent')
        if videos_ref.get().exists:
            videos_ref.delete()
            deleted_count += 1
        
        # Clean up legacy data in user document
        try:
            user_ref = db.collection('users').document(user_id)
            user_doc = user_ref.get()
            if user_doc.exists and user_doc.to_dict().get('youtube_analytics'):
                user_ref.update({
                    'youtube_analytics': firestore.DELETE_FIELD
                })
        except Exception as e:
            logger.warning(f"Error cleaning legacy youtube_analytics field: {str(e)}")
        
        logger.info(f"Successfully cleaned YouTube analytics data for user {user_id} - deleted {deleted_count} documents")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning YouTube user data: {str(e)}")
        return False

def get_users_with_youtube():
    """Get all user IDs who have YouTube connected"""
    try:
        # Initialize Firestore if needed
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        users_collection = db.collection('users')
        
        # Query users where youtube_credentials exists (more reliable than channel name)
        query = users_collection.where('youtube_credentials', '!=', '').where('youtube_credentials', '!=', None)
        
        # Execute query and get user IDs
        docs = query.stream()
        user_ids = [doc.id for doc in docs]
        
        logger.info(f"Found {len(user_ids)} users with YouTube connected")
        return user_ids
        
    except Exception as e:
        logger.error(f"Error querying users with YouTube: {str(e)}")
        return []