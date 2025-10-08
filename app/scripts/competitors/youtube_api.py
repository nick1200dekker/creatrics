"""
YouTube API Integration
Handles all YouTube data fetching via RapidAPI
"""
import os
import logging
import requests
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class YouTubeAPI:
    """YouTube API handler using RapidAPI"""
    
    def __init__(self):
        self.api_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.base_url = "https://yt-api.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "yt-api.p.rapidapi.com"
        }
    
    def extract_channel_handle(self, url: str) -> Optional[str]:
        """Extract channel handle (@username) from various YouTube URL formats"""
        # Handle @username format
        if '@' in url:
            # Extract just the @username part
            username = url.split('@')[1].split('/')[0].split('?')[0]
            return f"@{username}"
        
        # Handle /channel/ format - return as is for now
        if '/channel/' in url:
            return url.split('/channel/')[1].split('/')[0].split('?')[0]
        
        # Handle /c/ or /user/ format
        if '/c/' in url or '/user/' in url:
            return url.split('/')[-1].split('?')[0]
        
        # Already a channel ID
        if len(url) == 24 and url.startswith('UC'):
            return url
        
        # If it starts with @, return as is
        if url.startswith('@'):
            return url
        
        return None
    
    def get_channel_info(self, channel_identifier: str) -> Optional[Dict]:
        """
        Get channel information using either @username or channel ID
        
        Args:
            channel_identifier: Either @username or channel ID (UC...)
        
        Returns:
            Dict with channel info or None
        """
        try:
            url = f"{self.base_url}/channel/home"
            
            # Use forUsername if it's a handle, otherwise use id
            if channel_identifier.startswith('@'):
                querystring = {"forUsername": channel_identifier}
            else:
                querystring = {"id": channel_identifier}
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract relevant info
            meta = data.get('meta', {})
            channel_id = meta.get('channelId')
            
            if not channel_id:
                logger.error(f"No channel ID found for {channel_identifier}")
                return None
            
            return {
                'channel_id': channel_id,
                'title': meta.get('title'),
                'description': meta.get('description', ''),
                'avatar': meta.get('avatar', [{}])[0].get('url') if meta.get('avatar') else None,
                'subscriber_count': meta.get('subscriberCount', 0),
                'subscriber_count_text': meta.get('subscriberCountText', '0'),
                'video_count': meta.get('videosCount', 0),
                'keywords': meta.get('keywords', []),
                'channel_handle': meta.get('channelHandle', channel_identifier if channel_identifier.startswith('@') else '')
            }
            
        except Exception as e:
            logger.error(f"Error fetching channel info for {channel_identifier}: {e}")
            return None
    
    def get_channel_videos(self, channel_identifier: str, continuation_token: Optional[str] = None) -> Optional[Dict]:
        """
        Get videos from a channel using either @username or channel ID
        
        Args:
            channel_identifier: Either @username or channel ID
            continuation_token: Token for pagination
        
        Returns:
            Dict with videos and continuation token
        """
        try:
            url = f"{self.base_url}/channel/videos"
            
            # Use forUsername if it's a handle, otherwise use id
            if channel_identifier.startswith('@'):
                querystring = {"forUsername": channel_identifier}
            else:
                querystring = {"id": channel_identifier}
            
            if continuation_token:
                querystring['token'] = continuation_token
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            videos = []
            for video in data.get('data', []):
                if video.get('type') == 'video':
                    videos.append({
                        'video_id': video.get('videoId'),
                        'title': video.get('title'),
                        'description': video.get('description', ''),
                        'view_count': self._parse_view_count(video.get('viewCountText', '0')),
                        'view_count_text': video.get('viewCountText', '0'),
                        'published_time': video.get('publishedTimeText'),
                        'published_at': video.get('publishedAt'),
                        'publish_date': video.get('publishDate'),
                        'length': video.get('lengthText'),
                        'thumbnail': video.get('thumbnail', [{}])[-1].get('url') if video.get('thumbnail') else None
                    })
            
            return {
                'videos': videos,
                'continuation_token': data.get('continuation')
            }
            
        except Exception as e:
            logger.error(f"Error fetching channel videos for {channel_identifier}: {e}")
            return None
    
    def _parse_view_count(self, view_count_text: str) -> int:
        """Parse view count text like '296,318 views' or '1.2M views' to integer"""
        try:
            if not view_count_text:
                return 0
            
            # Remove 'views' text and extra spaces
            count_str = view_count_text.lower().replace('views', '').replace('view', '').strip()
            
            # Handle 'K' and 'M' suffixes
            if 'k' in count_str:
                return int(float(count_str.replace('k', '')) * 1000)
            elif 'm' in count_str:
                return int(float(count_str.replace('m', '')) * 1000000)
            else:
                # Remove commas and convert
                return int(count_str.replace(',', ''))
        except:
            return 0
    
    def get_video_info(self, video_id: str) -> Optional[Dict]:
        """Get detailed video information"""
        try:
            url = f"{self.base_url}/video/info"
            querystring = {"id": video_id}
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'video_id': data.get('id'),
                'title': data.get('title'),
                'description': data.get('description'),
                'keywords': data.get('keywords', []),
                'channel_id': data.get('channelId'),
                'channel_title': data.get('channelTitle'),
                'view_count': data.get('viewCount'),
                'like_count': data.get('likeCount'),
                'comment_count': data.get('commentCount', 0),
                'publish_date': data.get('publishDate'),
                'length_seconds': data.get('lengthSeconds'),
                'thumbnails': data.get('thumbnail', []),
                'subtitles': data.get('subtitles', {})
            }
            
        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
            return None
    
    def get_channel_shorts(self, channel_identifier: str, continuation_token: Optional[str] = None) -> Optional[Dict]:
        """
        Get shorts from a channel using either @username or channel ID

        Args:
            channel_identifier: Either @username or channel ID
            continuation_token: Token for pagination

        Returns:
            Dict with shorts and continuation token
        """
        try:
            url = f"{self.base_url}/channel/shorts"

            # Use forUsername if it's a handle, otherwise use id
            if channel_identifier.startswith('@'):
                querystring = {"forUsername": channel_identifier}
            else:
                querystring = {"id": channel_identifier}

            if continuation_token:
                querystring['token'] = continuation_token

            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()

            data = response.json()

            shorts = []
            for short in data.get('data', []):
                if short.get('type') == 'shorts':
                    shorts.append({
                        'video_id': short.get('videoId'),
                        'title': short.get('title'),
                        'description': short.get('description', ''),
                        'view_count': self._parse_view_count(short.get('viewCountText', '0')),
                        'view_count_text': short.get('viewCountText', '0'),
                        'published_time': short.get('publishedTimeText'),
                        'published_at': short.get('publishedAt'),
                        'publish_date': short.get('publishDate'),
                        'length': short.get('lengthText'),
                        'thumbnail': short.get('thumbnail', [{}])[-1].get('url') if short.get('thumbnail') else None,
                        'is_short': True
                    })

            return {
                'shorts': shorts,
                'continuation_token': data.get('continuation')
            }

        except Exception as e:
            logger.error(f"Error fetching channel shorts for {channel_identifier}: {e}")
            return None

    def get_short_info(self, short_id: str) -> Optional[Dict]:
        """Get detailed short information"""
        try:
            url = f"{self.base_url}/shorts/info"
            querystring = {"id": short_id}

            response = requests.get(url, headers=self.headers, params=querystring, timeout=10)
            response.raise_for_status()

            data = response.json()

            return {
                'video_id': data.get('id'),
                'title': data.get('title'),
                'description': data.get('description'),
                'keywords': data.get('keywords', []),
                'channel_id': data.get('channelId'),
                'channel_title': data.get('channelTitle'),
                'view_count': data.get('viewCount'),
                'like_count': data.get('likeCount'),
                'comment_count': data.get('commentCount', 0),
                'publish_date': data.get('publishDate'),
                'length_seconds': data.get('lengthSeconds'),
                'thumbnails': data.get('thumbnail', []),
                'subtitles': data.get('subtitles', {}),
                'is_short': True
            }

        except Exception as e:
            logger.error(f"Error fetching short info: {e}")
            return None

    def filter_videos_by_timeframe(self, videos: List[Dict], days: int) -> List[Dict]:
        """Filter videos by timeframe"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = []

        for video in videos:
            # Try multiple date fields
            pub_date_str = video.get('published_at') or video.get('publishedAt') or video.get('publish_date')

            if pub_date_str:
                try:
                    # Parse ISO format date
                    if 'T' in pub_date_str:
                        pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    else:
                        # Try YYYY-MM-DD format
                        pub_date = datetime.strptime(pub_date_str, '%Y-%m-%d')

                    # Make cutoff_date timezone-aware if pub_date is
                    if pub_date.tzinfo is not None and cutoff_date.tzinfo is None:
                        from datetime import timezone
                        cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)

                    if pub_date >= cutoff_date:
                        filtered.append(video)
                except Exception as e:
                    logger.debug(f"Could not parse date {pub_date_str}: {e}")
                    # If parsing fails, include the video
                    filtered.append(video)
            else:
                # If no date, include it
                filtered.append(video)

        return filtered