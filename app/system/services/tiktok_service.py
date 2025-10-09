import requests
import logging
import os
from datetime import datetime

logger = logging.getLogger('tiktok_service')

class TikTokService:
    """Service for interacting with TikTok API via RapidAPI"""

    BASE_URL = "https://tiktok-api23.p.rapidapi.com/api"

    @classmethod
    def _get_headers(cls):
        """Get API headers with key from environment or fallback"""
        api_key = os.environ.get('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        return {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "tiktok-api23.p.rapidapi.com"
        }

    @classmethod
    def get_user_info(cls, username):
        """
        Fetch TikTok user information

        Args:
            username: TikTok username (without @)

        Returns:
            dict: User information including stats and secUid
        """
        try:
            url = f"{cls.BASE_URL}/user/info"
            querystring = {"uniqueId": username}

            response = requests.get(url, headers=cls._get_headers(), params=querystring, timeout=10)

            # Log response for debugging
            logger.info(f"TikTok API response status: {response.status_code}")

            # Handle rate limiting or empty responses
            if response.status_code == 204:
                logger.warning(f"TikTok API returned 204 No Content - API may be rate limited")
                return None

            if response.status_code == 429:
                logger.warning(f"TikTok API rate limit exceeded for user {username}")
                return None

            logger.debug(f"TikTok API response text (first 200 chars): {response.text[:200] if response.text else 'EMPTY'}")

            response.raise_for_status()

            # Check if response has content
            if not response.text or response.text.strip() == '':
                logger.error(f"TikTok API returned empty response for user {username}")
                return None

            # Check if response is JSON
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"TikTok API returned non-JSON response for user {username}: {response.text[:500]}")
                return None

            if data.get('statusCode') != 0:
                logger.error(f"TikTok API error for user {username}: {data.get('status_msg')}")
                return None

            user_info = data.get('userInfo', {})
            user = user_info.get('user', {})
            stats = user_info.get('stats', {})
            stats_v2 = user_info.get('statsV2', {})

            # Use statsV2 for string-based larger numbers if available
            return {
                'user_id': user.get('id'),
                'sec_uid': user.get('secUid'),
                'username': user.get('uniqueId'),
                'nickname': user.get('nickname'),
                'avatar': user.get('avatarThumb'),
                'signature': user.get('signature'),
                'verified': user.get('verified', False),
                'followers': int(stats_v2.get('followerCount', stats.get('followerCount', 0))),
                'following': int(stats_v2.get('followingCount', stats.get('followingCount', 0))),
                'likes': int(stats_v2.get('heartCount', stats.get('heartCount', 0))),
                'videos': int(stats_v2.get('videoCount', stats.get('videoCount', 0))),
                'fetched_at': datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching TikTok user info for {username}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching TikTok user info: {str(e)}")
            return None

    @classmethod
    def get_user_posts(cls, sec_uid, count=35, cursor="0"):
        """
        Fetch TikTok user's recent posts

        Args:
            sec_uid: User's secUid from get_user_info
            count: Number of posts to fetch (default 35, max 35)
            cursor: Pagination cursor (default "0" for first page)

        Returns:
            dict: Posts data including items and pagination info
        """
        try:
            url = f"{cls.BASE_URL}/user/posts"
            querystring = {
                "secUid": sec_uid,
                "count": str(count),
                "cursor": cursor
            }

            response = requests.get(url, headers=cls._get_headers(), params=querystring, timeout=15)

            logger.info(f"TikTok posts API response status: {response.status_code}")
            logger.debug(f"TikTok posts API response text (first 200 chars): {response.text[:200]}")

            response.raise_for_status()

            # Check if response is JSON
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"TikTok API returned non-JSON response for posts: {response.text[:500]}")
                return None

            if not data.get('data'):
                logger.error(f"No data returned for secUid {sec_uid}")
                return None

            posts_data = data.get('data', {})
            item_list = posts_data.get('itemList', [])

            # Process posts
            posts = []
            for item in item_list:
                stats = item.get('stats', {})
                video = item.get('video', {})

                posts.append({
                    'id': item.get('id'),
                    'desc': item.get('desc', ''),
                    'create_time': item.get('createTime'),
                    'video_id': video.get('id'),
                    'cover': video.get('cover'),
                    'duration': video.get('duration'),
                    'play_addr': video.get('playAddr'),
                    'views': stats.get('playCount', 0),
                    'likes': stats.get('diggCount', 0),
                    'comments': stats.get('commentCount', 0),
                    'shares': stats.get('shareCount', 0),
                    'saves': stats.get('collectCount', 0),
                })

            return {
                'posts': posts,
                'has_more': posts_data.get('hasMore', False),
                'cursor': posts_data.get('cursor'),
                'fetched_at': datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching TikTok posts for secUid {sec_uid}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching TikTok posts: {str(e)}")
            return None
