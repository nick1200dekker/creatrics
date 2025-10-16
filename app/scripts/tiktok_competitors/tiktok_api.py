"""
TikTok API Integration
Handles all TikTok data fetching via RapidAPI
"""
import os
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class TikTokAPI:
    """TikTok API handler using RapidAPI"""
    
    def __init__(self):
        self.api_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.base_url = "https://tiktok-api23.p.rapidapi.com/api"
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "tiktok-api23.p.rapidapi.com"
        }
    
    def extract_username(self, url: str) -> Optional[str]:
        """Extract username from TikTok URL"""
        # Handle @username format
        if '@' in url:
            username = url.split('@')[1].split('/')[0].split('?')[0]
            return username
        
        # If it starts with @, return as is
        if url.startswith('@'):
            return url[1:]  # Remove @ symbol
        
        # Already a username
        if '/' not in url and '.' not in url:
            return url
        
        return None
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """
        Get user information using username
        
        Args:
            username: TikTok username (without @)
        
        Returns:
            Dict with user info or None
        """
        try:
            url = f"{self.base_url}/user/info"
            querystring = {"uniqueId": username}
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('statusCode') != 0:
                logger.error(f"TikTok API error: {data.get('status_msg')}")
                return None
            
            user_info = data.get('userInfo', {})
            user = user_info.get('user', {})
            stats = user_info.get('stats', {})
            
            return {
                'sec_uid': user.get('secUid'),
                'username': user.get('uniqueId'),
                'nickname': user.get('nickname'),
                'bio': user.get('signature', ''),
                'avatar': user.get('avatarLarger'),
                'follower_count': stats.get('followerCount', 0),
                'following_count': stats.get('followingCount', 0),
                'video_count': stats.get('videoCount', 0),
                'heart_count': stats.get('heartCount', 0),
                'verified': user.get('verified', False)
            }
            
        except Exception as e:
            logger.error(f"Error fetching user info for {username}: {e}")
            return None
    
    def get_user_videos(self, sec_uid: str, cursor: str = "0", count: int = 35) -> Optional[Dict]:
        """
        Get videos from a user
        
        Args:
            sec_uid: User's secUid
            cursor: Pagination cursor
            count: Number of videos to fetch
        
        Returns:
            Dict with videos and cursor
        """
        try:
            url = f"{self.base_url}/user/posts"
            querystring = {
                "secUid": sec_uid,
                "count": str(count),
                "cursor": cursor
            }
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('data'):
                return {'videos': [], 'cursor': None, 'hasMore': False}
            
            videos = []
            for item in data.get('data', {}).get('itemList', []):
                video_data = self._parse_video_data(item)
                if video_data:
                    videos.append(video_data)
            
            return {
                'videos': videos,
                'cursor': data.get('data', {}).get('cursor'),
                'hasMore': data.get('data', {}).get('hasMore', False)
            }
            
        except Exception as e:
            logger.error(f"Error fetching user videos for {sec_uid}: {e}")
            return None
    
    def search_videos(self, keyword: str, cursor: str = "0") -> Optional[Dict]:
        """
        Search for videos by keyword
        
        Args:
            keyword: Search term
            cursor: Pagination cursor
        
        Returns:
            Dict with videos and cursor
        """
        try:
            url = f"{self.base_url}/search/video"
            querystring = {
                "keyword": keyword,
                "cursor": cursor,
                "search_id": "0"
            }
            
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('data'):
                return {'videos': [], 'users': [], 'cursor': None}
            
            # Extract unique users from search results
            users_dict = {}
            for item in data.get('data', []):
                author = item.get('author', {})
                user_id = author.get('id')
                if user_id and user_id not in users_dict:
                    users_dict[user_id] = {
                        'sec_uid': author.get('secUid'),
                        'username': author.get('uniqueId'),
                        'nickname': author.get('nickname'),
                        'avatar': author.get('avatarLarger'),
                        'verified': author.get('verified', False)
                    }
            
            return {
                'users': list(users_dict.values()),
                'cursor': data.get('cursor')
            }
            
        except Exception as e:
            logger.error(f"Error searching videos for {keyword}: {e}")
            return None
    
    def _parse_video_data(self, item: Dict) -> Optional[Dict]:
        """Parse video data from API response"""
        try:
            video_id = item.get('id')
            if not video_id:
                return None
            
            stats = item.get('stats', {})
            author = item.get('author', {})
            
            # Parse create time
            create_time = item.get('createTime')
            published_at = None
            if create_time:
                try:
                    published_at = datetime.fromtimestamp(int(create_time), tz=timezone.utc)
                except:
                    pass
            
            return {
                'video_id': video_id,
                'desc': item.get('desc', ''),
                'create_time': create_time,
                'published_at': published_at.isoformat() if published_at else None,
                'view_count': stats.get('playCount', 0),
                'like_count': stats.get('diggCount', 0),
                'comment_count': stats.get('commentCount', 0),
                'share_count': stats.get('shareCount', 0),
                'video_url': f"https://www.tiktok.com/@{author.get('uniqueId')}/video/{video_id}",
                'author_username': author.get('uniqueId'),
                'author_nickname': author.get('nickname'),
                'cover': item.get('video', {}).get('cover')
            }
        except Exception as e:
            logger.error(f"Error parsing video data: {e}")
            return None
    
    def filter_videos_by_timeframe(self, videos: List[Dict], days: int) -> List[Dict]:
        """Filter videos by timeframe"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = []
        
        for video in videos:
            pub_date = None
            
            # Try to parse published_at
            pub_date_str = video.get('published_at')
            if pub_date_str:
                try:
                    pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                except:
                    pass
            
            # Fallback to create_time
            if not pub_date:
                create_time = video.get('create_time')
                if create_time:
                    try:
                        pub_date = datetime.fromtimestamp(int(create_time), tz=timezone.utc)
                    except:
                        pass
            
            if pub_date and pub_date >= cutoff_date:
                filtered.append(video)
        
        return filtered
    
    def format_count(self, count: int) -> str:
        """Format count with K/M suffix"""
        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        elif count >= 1000:
            return f"{count / 1000:.1f}K"
        else:
            return str(count)