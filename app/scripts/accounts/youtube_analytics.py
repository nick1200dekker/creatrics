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
            error_str = str(e).lower()
            logger.error(f"Error refreshing YouTube credentials: {str(e)}")

            # If token is revoked, clean up immediately (YouTube API compliance)
            if 'invalid_grant' in error_str or 'token has been expired or revoked' in error_str:
                logger.warning(f"Token revoked during refresh for user {self.user_id}, cleaning up")
                clean_youtube_user_data(self.user_id)
                # Set credentials to None so caller knows auth failed
                self.credentials = None

            # Re-raise to notify caller that refresh failed
            raise
    
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
            start_date_180d = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')  # 6 months
            start_date_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Basic metrics (aggregate)
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
            
            # Daily metrics for time series (6 months for better timeframe support)
            daily_metrics = None
            try:
                daily_metrics = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_180d,
                    endDate=end_date,
                    dimensions='day',
                    metrics='views,estimatedMinutesWatched,subscribersGained'
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch daily metrics: {str(e)}")
            
            # Traffic sources for different timeframes
            traffic_sources_7d = None
            traffic_sources_30d = None
            traffic_sources_90d = None
            traffic_sources_180d = None
            
            # 7 days
            try:
                traffic_sources_7d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_7d,
                    endDate=end_date,
                    dimensions='insightTrafficSourceType',
                    metrics='views',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 7-day traffic sources: {str(e)}")
            
            # 30 days
            try:
                traffic_sources_30d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_30d,
                    endDate=end_date,
                    dimensions='insightTrafficSourceType',
                    metrics='views',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 30-day traffic sources: {str(e)}")
            
            # 90 days
            try:
                traffic_sources_90d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_90d,
                    endDate=end_date,
                    dimensions='insightTrafficSourceType',
                    metrics='views',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 90-day traffic sources: {str(e)}")
            
            # 6 months (180 days)
            try:
                traffic_sources_180d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_180d,
                    endDate=end_date,
                    dimensions='insightTrafficSourceType',
                    metrics='views',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 180-day traffic sources: {str(e)}")
            
            # Top videos for different timeframes
            top_videos_7d = None
            top_videos_30d = None
            top_videos_90d = None
            top_videos_180d = None
            
            # 7 days
            start_date_7d = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            try:
                top_videos_7d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_7d,
                    endDate=end_date,
                    dimensions='video',
                    metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 7-day top videos: {str(e)}")
            
            # 30 days
            try:
                top_videos_30d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_30d,
                    endDate=end_date,
                    dimensions='video',
                    metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 30-day top videos: {str(e)}")
            
            # 90 days
            try:
                top_videos_90d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_90d,
                    endDate=end_date,
                    dimensions='video',
                    metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 90-day top videos: {str(e)}")
            
            # 6 months (180 days)
            try:
                top_videos_180d = youtube_analytics.reports().query(
                    ids=f'channel=={self.channel_id}',
                    startDate=start_date_180d,
                    endDate=end_date,
                    dimensions='video',
                    metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained',
                    sort='-views',
                    maxResults=10
                ).execute()
            except Exception as e:
                logger.warning(f"Could not fetch 180-day top videos: {str(e)}")
            
            # Process the data
            top_videos_data = {
                '7days': top_videos_7d,
                '30days': top_videos_30d,
                '90days': top_videos_90d,
                '6months': top_videos_180d
            }
            traffic_sources_data = {
                '7days': traffic_sources_7d,
                '30days': traffic_sources_30d,
                '90days': traffic_sources_90d,
                '6months': traffic_sources_180d
            }
            processed_analytics = self._process_analytics(metrics_90d, daily_metrics, traffic_sources_data, top_videos_data)
            
            # Store analytics data
            self._store_analytics(processed_analytics)
            
            return processed_analytics
            
        except HttpError as e:
            logger.error(f"HTTP error fetching analytics data: {e.content}")
            return None
        except Exception as e:
            logger.error(f"Error fetching analytics data: {str(e)}")
            return None
    
    def _process_analytics(self, metrics_90d, daily_metrics, traffic_sources_data, top_videos_data):
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
            "traffic_sources": [],  # Keep for backward compatibility (90 days)
            "traffic_sources_by_timeframe": {
                "7days": [],
                "30days": [],
                "90days": [],
                "6months": []
            },
            "top_videos": [],  # Keep for backward compatibility (30 days)
            "top_videos_by_timeframe": {
                "7days": [],
                "30days": [],
                "90days": [],
                "6months": []
            },
            "daily_data": [],
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
        
        # Process daily metrics
        if daily_metrics and 'rows' in daily_metrics:
            column_index = {col['name']: idx for idx, col in enumerate(daily_metrics['columnHeaders'])}
            
            for row in daily_metrics['rows']:
                day = row[column_index['day']]
                views = int(row[column_index.get('views', 0)])
                watch_time_minutes = int(row[column_index.get('estimatedMinutesWatched', 0)])
                subscribers_gained = int(row[column_index.get('subscribersGained', 0)])
                
                processed["daily_data"].append({
                    "date": day,
                    "views": views,
                    "watch_time_minutes": watch_time_minutes,
                    "watch_time_hours": round(watch_time_minutes / 60, 2),
                    "subscribers_gained": subscribers_gained
                })
        
        # Process traffic sources for all timeframes
        for timeframe, traffic_sources in traffic_sources_data.items():
            if traffic_sources and 'rows' in traffic_sources:
                column_index = {col['name']: idx for idx, col in enumerate(traffic_sources['columnHeaders'])}
                
                for row in traffic_sources['rows']:
                    source_name = row[column_index['insightTrafficSourceType']]
                    source_views = int(row[column_index['views']])
                    
                    source_data = {
                        "source": source_name,
                        "views": source_views,
                        "percentage": round((source_views / processed["views"] * 100), 2) if processed["views"] > 0 else 0
                    }
                    
                    processed["traffic_sources_by_timeframe"][timeframe].append(source_data)
                    
                    # Keep backward compatibility - use 90 days for the old traffic_sources field
                    if timeframe == '90days':
                        processed["traffic_sources"].append(source_data)

        # Collect all unique video IDs for metadata fetching
        all_video_ids = set()
        for timeframe, top_videos in top_videos_data.items():
            if top_videos and 'rows' in top_videos:
                column_index = {col['name']: idx for idx, col in enumerate(top_videos['columnHeaders'])}
                for row in top_videos['rows']:
                    video_id = row[column_index['video']]
                    if '==' in video_id:
                        video_id = video_id.split('==')[1]
                    all_video_ids.add(video_id)

        # Fetch video metadata (titles and thumbnails) for all videos
        video_metadata = {}
        if all_video_ids:
            try:
                youtube_data = build('youtube', 'v3', credentials=self.credentials)
                # YouTube API allows up to 50 video IDs per request
                video_ids_list = list(all_video_ids)
                for i in range(0, len(video_ids_list), 50):
                    batch_ids = video_ids_list[i:i+50]
                    video_details = youtube_data.videos().list(
                        part='snippet',
                        id=','.join(batch_ids)
                    ).execute()

                    for item in video_details.get('items', []):
                        video_id = item['id']
                        snippet = item['snippet']
                        video_metadata[video_id] = {
                            'title': snippet.get('title', f'Video {video_id}'),
                            'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
                        }
            except Exception as e:
                logger.warning(f"Could not fetch video metadata: {str(e)}")

        # Process top videos for all timeframes
        for timeframe, top_videos in top_videos_data.items():
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

                    # Get metadata if available
                    metadata = video_metadata.get(video_id, {})

                    video_data = {
                        "id": video_id,
                        "title": metadata.get('title', f'Video {video_id}'),
                        "thumbnail": metadata.get('thumbnail', ''),
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
                    }

                    processed["top_videos_by_timeframe"][timeframe].append(video_data)

                    # Keep backward compatibility - use 30 days for the old top_videos field
                    if timeframe == '30days':
                        processed["top_videos"].append(video_data)
        
        return processed
    
    def _store_analytics(self, analytics_data):
        """Store analytics data in Firebase with both latest and historical data"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            now = datetime.now()

            # Add compliance timestamps
            analytics_data['data_fetched_at'] = now.isoformat()
            analytics_data['data_fetched_timestamp'] = now.timestamp()
            analytics_data['next_verification_due'] = (now + timedelta(days=30)).isoformat()

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

def fetch_youtube_analytics(user_id, force_refresh=False):
    """
    Fetch YouTube analytics data for a user

    Args:
        user_id: User ID
        force_refresh: Force fetch even if cached data is recent

    Returns:
        Analytics data dict or None if failed
    """
    try:
        analytics = YouTubeAnalytics(user_id)
        if not analytics.credentials:
            logger.error(f"Failed to initialize YouTubeAnalytics - no valid credentials")
            return None

        # Check if we need to refresh (30-day compliance check)
        if not force_refresh:
            needs_refresh = check_if_refresh_needed(user_id)
            if not needs_refresh:
                logger.info(f"YouTube analytics for user {user_id} is recent, skipping fetch")
                # Return cached data
                return get_cached_analytics(user_id)

        result = analytics.get_analytics_data()
        if result:
            logger.info(f"YouTube analytics fetch completed successfully for user {user_id}")
        else:
            logger.error(f"YouTube analytics fetch failed for user {user_id}")

        return result
    except Exception as e:
        error_str = str(e).lower()

        # Check for revoked access (compliance requirement)
        if 'invalid_grant' in error_str or 'token has been expired or revoked' in error_str:
            logger.warning(f"YouTube access revoked for user {user_id}, cleaning up data")
            # Auto-delete data as per policy III.E.4.g
            clean_youtube_user_data(user_id)
            return None

        logger.error(f"YouTube analytics fetch exception for user {user_id}: {str(e)}")
        return None

def check_if_refresh_needed(user_id):
    """
    Check if analytics data needs refresh (30-day compliance check)
    Policy: III.E.4.b - verify every 30 days

    Returns:
        True if refresh needed, False if cached data is acceptable
    """
    try:
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass

        db = firestore.client()
        latest_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
        latest_doc = latest_ref.get()

        if not latest_doc.exists:
            logger.info(f"No cached analytics for user {user_id}, refresh needed")
            return True

        data = latest_doc.to_dict()
        fetched_at = data.get('data_fetched_at')

        if not fetched_at:
            logger.info(f"No fetch timestamp for user {user_id}, refresh needed")
            return True

        # Parse timestamp
        try:
            fetched_time = datetime.fromisoformat(fetched_at)
            age_days = (datetime.now() - fetched_time).days

            # Compliance: Refresh if >30 days old
            if age_days >= 30:
                logger.info(f"Analytics data for user {user_id} is {age_days} days old, refresh required")
                return True

            logger.info(f"Analytics data for user {user_id} is {age_days} days old, acceptable")
            return False

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid timestamp format for user {user_id}: {e}")
            return True

    except Exception as e:
        logger.error(f"Error checking refresh status for user {user_id}: {str(e)}")
        return True

def get_cached_analytics(user_id):
    """Get cached analytics data from Firestore"""
    try:
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass

        db = firestore.client()
        latest_ref = db.collection('users').document(user_id).collection('youtube_analytics').document('latest')
        latest_doc = latest_ref.get()

        if latest_doc.exists:
            return latest_doc.to_dict()

        return None

    except Exception as e:
        logger.error(f"Error getting cached analytics for user {user_id}: {str(e)}")
        return None

def clean_youtube_user_data(user_id):
    """
    Clean all YouTube analytics data AND tokens for a user when they disconnect
    or when token is revoked/expired (YouTube API compliance requirement)
    """
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

        # CRITICAL: Delete OAuth tokens from user document (YouTube API compliance)
        # Must use DELETE_FIELD to physically remove from storage, not set to None
        try:
            user_ref = db.collection('users').document(user_id)
            user_doc = user_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                fields_to_delete = {}

                # Only delete fields that exist
                if user_data.get('youtube_credentials'):
                    fields_to_delete['youtube_credentials'] = firestore.DELETE_FIELD
                if user_data.get('youtube_account'):
                    fields_to_delete['youtube_account'] = firestore.DELETE_FIELD
                if user_data.get('youtube_channel_id'):
                    fields_to_delete['youtube_channel_id'] = firestore.DELETE_FIELD
                if user_data.get('youtube_connected_at'):
                    fields_to_delete['youtube_connected_at'] = firestore.DELETE_FIELD
                if user_data.get('youtube_setup_complete'):
                    fields_to_delete['youtube_setup_complete'] = firestore.DELETE_FIELD
                if user_data.get('youtube_channel_keywords'):
                    fields_to_delete['youtube_channel_keywords'] = firestore.DELETE_FIELD

                if fields_to_delete:
                    user_ref.update(fields_to_delete)
                    logger.info(f"Deleted {len(fields_to_delete)} YouTube token fields from user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting YouTube token fields: {str(e)}")

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

def update_video_metadata(user_id, video_id, title=None, description=None, tags=None):
    """
    Update YouTube video metadata (title, description, tags)

    Args:
        user_id: User ID who owns the video
        video_id: YouTube video ID
        title: New title (optional)
        description: New description (optional)
        tags: List of new tags (optional)

    Returns:
        dict: {'success': bool, 'message': str, 'error': str (if failed)}
    """
    try:
        # Initialize YouTubeAnalytics to get credentials
        analytics = YouTubeAnalytics(user_id)

        if not analytics.credentials:
            logger.error(f"No YouTube credentials found for user {user_id}")
            return {
                'success': False,
                'error': 'YouTube account not connected'
            }

        # Build YouTube API client
        youtube = build('youtube', 'v3', credentials=analytics.credentials)

        # Get current video data
        try:
            video_response = youtube.videos().list(
                part='snippet,status',
                id=video_id
            ).execute()

            if not video_response.get('items'):
                return {
                    'success': False,
                    'error': 'Video not found or access denied'
                }

            video_data = video_response['items'][0]
            snippet = video_data['snippet']

        except HttpError as e:
            logger.error(f"HTTP error fetching video {video_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to fetch video: {str(e)}'
            }

        # Import string for character validation
        import string

        # ALWAYS clean existing tags to prevent YouTube API errors
        # This is critical because existing video tags may have invalid characters
        if 'tags' in snippet:
            existing_tags = snippet.get('tags', [])
            cleaned_existing_tags = []
            total_length = 0

            logger.info(f"Cleaning {len(existing_tags)} existing tags for video {video_id}")

            for tag in existing_tags:
                if isinstance(tag, str):
                    original_tag = tag
                    cleaned_tag = tag.strip()

                    # Remove ALL special characters - extremely strict
                    # Only keep ASCII letters, digits, spaces, hyphens (no apostrophes)
                    allowed_chars = string.ascii_letters + string.digits + ' -'
                    cleaned_tag = ''.join(c for c in cleaned_tag if c in allowed_chars)

                    # Normalize whitespace
                    cleaned_tag = ' '.join(cleaned_tag.split())

                    # Remove leading/trailing hyphens or spaces
                    cleaned_tag = cleaned_tag.strip(' -')

                    if cleaned_tag != original_tag:
                        logger.info(f"Cleaned tag: '{original_tag}' -> '{cleaned_tag}'")

                    # Skip empty or single-char tags
                    if cleaned_tag and len(cleaned_tag) > 1:
                        # Check 500 character limit (including separators)
                        # YouTube uses ", " as separator = 2 chars per tag
                        tag_length_with_separator = len(cleaned_tag) + (2 if cleaned_existing_tags else 0)
                        if total_length + tag_length_with_separator <= 480:
                            cleaned_existing_tags.append(cleaned_tag)
                            total_length += tag_length_with_separator

            snippet['tags'] = cleaned_existing_tags
            logger.info(f"Cleaned existing tags: {len(cleaned_existing_tags)} tags, {total_length} chars")

        # Update only provided fields
        if title is not None:
            snippet['title'] = title
            logger.info(f"Updating title for video {video_id}")

        if description is not None:
            snippet['description'] = description
            logger.info(f"Updating description for video {video_id}")

        if tags is not None:
            # Clean and validate new tags with EXTREME strictness
            cleaned_tags = []
            total_length = 0

            logger.info(f"Processing {len(tags)} new tags for video {video_id}")

            for tag in tags:
                if isinstance(tag, str):
                    original_tag = tag
                    cleaned_tag = tag.strip()

                    # Remove ALL special characters - be extremely strict
                    # Only keep ASCII letters, digits, spaces, hyphens
                    # Remove apostrophes as they might be causing issues
                    allowed_chars = string.ascii_letters + string.digits + ' -'
                    cleaned_tag = ''.join(c for c in cleaned_tag if c in allowed_chars)

                    # Normalize whitespace
                    cleaned_tag = ' '.join(cleaned_tag.split())

                    # Remove any leading/trailing hyphens or spaces
                    cleaned_tag = cleaned_tag.strip(' -')

                    if cleaned_tag != original_tag:
                        logger.info(f"Cleaned new tag: '{original_tag}' -> '{cleaned_tag}'")

                    # Skip empty tags or tags with only spaces/hyphens
                    if cleaned_tag and len(cleaned_tag) > 1:
                        # YouTube limits: each tag max 30 chars, total 500 chars
                        if len(cleaned_tag) > 30:
                            logger.warning(f"Skipping tag '{cleaned_tag}' - exceeds 30 char limit ({len(cleaned_tag)} chars)")
                            continue

                        # Check character limit - max 500 chars total including commas
                        tag_length_with_separator = len(cleaned_tag) + (2 if cleaned_tags else 0)
                        if total_length + tag_length_with_separator <= 480:  # Stay under 500
                            cleaned_tags.append(cleaned_tag)
                            total_length += tag_length_with_separator
                        else:
                            logger.warning(f"Skipping tag '{cleaned_tag}' - would exceed 480 char limit")

            snippet['tags'] = cleaned_tags
            logger.info(f"Updating {len(cleaned_tags)} tags for video {video_id} (total: {total_length} chars)")
            logger.info(f"Final tags to send: {cleaned_tags}")

        # Execute update
        try:
            # Log the full snippet we're about to send
            logger.info(f"Sending snippet update for video {video_id}")
            logger.info(f"Snippet keys: {list(snippet.keys())}")

            # The issue might be that we're sending fields YouTube doesn't like
            # Let's only send the required fields + what we're updating
            safe_snippet = {
                'title': snippet['title'],
                'categoryId': snippet['categoryId'],
                'description': snippet.get('description', ''),
            }

            # Only include tags if they exist and are valid
            if 'tags' in snippet and snippet['tags']:
                safe_snippet['tags'] = snippet['tags']

            # Log what we're sending
            logger.info(f"Safe snippet fields: {list(safe_snippet.keys())}")
            if 'tags' in safe_snippet:
                logger.info(f"Sending {len(safe_snippet['tags'])} tags")

            update_body = {
                'id': video_id,
                'snippet': safe_snippet
            }

            youtube.videos().update(
                part='snippet',
                body=update_body
            ).execute()

            logger.info(f"Successfully updated video {video_id} for user {user_id}")
            return {
                'success': True,
                'message': 'Video metadata updated successfully'
            }

        except HttpError as e:
            error_content = e.content.decode('utf-8') if hasattr(e, 'content') else str(e)
            logger.error(f"HTTP error updating video {video_id}: {error_content}")

            # Try to parse error message
            try:
                error_json = json.loads(error_content)
                error_message = error_json.get('error', {}).get('message', str(e))
            except:
                error_message = str(e)

            return {
                'success': False,
                'error': f'YouTube API error: {error_message}'
            }

    except Exception as e:
        logger.error(f"Error updating video metadata for video {video_id}: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to update video: {str(e)}'
        }