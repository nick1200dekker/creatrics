"""
YouTube Client Utility - Get authenticated YouTube client using user's OAuth credentials
This ensures all API calls use the user's quota (10,000 units/day) instead of shared app quota
"""
import logging
from googleapiclient.discovery import build
from app.scripts.accounts.youtube_analytics import YouTubeAnalytics

logger = logging.getLogger(__name__)


def get_user_youtube_client(user_id):
    """
    Get authenticated YouTube Data API v3 client using user's OAuth credentials

    Args:
        user_id (str): The user's Firebase user ID

    Returns:
        googleapiclient.discovery.Resource: Authenticated YouTube API client
        None: If user hasn't connected YouTube or credentials are invalid

    Usage:
        youtube = get_user_youtube_client(user_id)
        if not youtube:
            return {'error': 'Please connect your YouTube account first'}

        # Use the client - all API calls use USER'S quota
        response = youtube.videos().list(
            part='snippet',
            id='video_id'
        ).execute()
    """
    try:
        # Use existing YouTubeAnalytics class to get user's credentials
        yt = YouTubeAnalytics(user_id)

        if not yt.credentials:
            logger.warning(f"No YouTube credentials found for user {user_id}")
            return None

        # Build YouTube Data API v3 client with user's OAuth credentials
        youtube = build('youtube', 'v3', credentials=yt.credentials)

        logger.info(f"Successfully created YouTube client for user {user_id}")
        return youtube

    except Exception as e:
        logger.error(f"Error creating YouTube client for user {user_id}: {str(e)}")
        return None


def check_youtube_connection(user_id):
    """
    Check if user has connected their YouTube account with required permissions

    Args:
        user_id (str): The user's Firebase user ID

    Returns:
        dict: {
            'connected': bool,
            'channel_id': str or None,
            'channel_name': str or None
        }
    """
    try:
        yt = YouTubeAnalytics(user_id)

        return {
            'connected': bool(yt.credentials and yt.channel_id),
            'channel_id': yt.channel_id,
            'channel_name': yt.channel_name
        }

    except Exception as e:
        logger.error(f"Error checking YouTube connection for user {user_id}: {str(e)}")
        return {
            'connected': False,
            'channel_id': None,
            'channel_name': None
        }
