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
    
    def extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID from various YouTube URL formats"""
        # Handle @username format
        if '@' in url:
            username = url.split('@')[1].split('/')[0].split('?')[0]
            # Try to get channel ID from username
            # For now, return the username format
            return url.split('@')[1].split('/')[0].split('?')[0]
        
        # Handle /channel/ format
        if '/channel/' in url:
            return url.split('/channel/')[1].split('/')[0].split('?')[0]
        
        # Handle /c/ or /user/ format
        if '/c/' in url or '/user/' in url:
            return url.split('/')[-1].split('?')[0]
        
        # Already a channel ID
        if len(url) == 24 and url.startswith('UC'):
            return url
        
        return None
    
    def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        """Get channel information"""
        try:
            url = f"{self.base_url}/channel/about"
            querystring = {"id": channel_id}
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract relevant info
            meta = data.get('meta', {})
            return {
                'channel_id': meta.get('channelId'),
                'title': meta.get('title'),
                'description': meta.get('description'),
                'avatar': meta.get('avatar', [{}])[0].get('url') if meta.get('avatar') else None,
                'subscriber_count': meta.get('subscriberCount'),
                'video_count': meta.get('videosCount'),
                'keywords': meta.get('keywords', [])
            }
            
        except Exception as e:
            logger.error(f"Error fetching channel info: {e}")
            return None
    
    def get_channel_videos(self, channel_id: str, continuation_token: Optional[str] = None) -> Optional[Dict]:
        """Get videos from a channel"""
        try:
            url = f"{self.base_url}/channel/videos"
            querystring = {"id": channel_id}
            
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
                        'description': video.get('description'),
                        'view_count': video.get('viewCount'),
                        'published_time': video.get('publishedTimeText'),
                        'published_at': video.get('publishedAt'),
                        'length': video.get('lengthText'),
                        'thumbnail': video.get('thumbnail', [{}])[-1].get('url') if video.get('thumbnail') else None
                    })
            
            return {
                'videos': videos,
                'continuation_token': data.get('continuation_token')
            }
            
        except Exception as e:
            logger.error(f"Error fetching channel videos: {e}")
            return None
    
    def get_channel_shorts(self, channel_id: str) -> Optional[List[Dict]]:
        """Get shorts from a channel"""
        try:
            url = f"{self.base_url}/channel/shorts"
            querystring = {"id": channel_id}
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            shorts = []
            for short in data.get('data', []):
                shorts.append({
                    'video_id': short.get('videoId'),
                    'title': short.get('title'),
                    'view_count': short.get('viewCount'),
                    'published_time': short.get('publishedTimeText'),
                    'thumbnail': short.get('thumbnail', [{}])[-1].get('url') if short.get('thumbnail') else None
                })
            
            return shorts
            
        except Exception as e:
            logger.error(f"Error fetching channel shorts: {e}")
            return None
    
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
                'publish_date': data.get('publishDate'),
                'length_seconds': data.get('lengthSeconds'),
                'thumbnails': data.get('thumbnail', []),
                'subtitles': data.get('subtitles', {})
            }
            
        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
            return None
    
    def get_transcript(self, video_id: str) -> Optional[str]:
        """Get video transcript"""
        try:
            url = f"{self.base_url}/get_transcript"
            querystring = {"id": video_id}
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract transcript text
            transcript_data = data.get('transcript', [])
            if isinstance(transcript_data, list):
                return ' '.join([item.get('text', '') for item in transcript_data])
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            return None
    
    def filter_videos_by_timeframe(self, videos: List[Dict], days: int) -> List[Dict]:
        """Filter videos by timeframe"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = []
        
        for video in videos:
            pub_date_str = video.get('published_at')
            if pub_date_str:
                try:
                    # Parse ISO format date
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    if pub_date >= cutoff_date:
                        filtered.append(video)
                except:
                    # If parsing fails, include the video
                    filtered.append(video)
            else:
                # If no date, include it
                filtered.append(video)
        
        return filtered