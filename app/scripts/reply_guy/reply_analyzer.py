"""
Reply Analyzer - Fixed version with proper environment variables
Analyzes accounts and finds reply opportunities
"""
import os
import requests
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class ReplyAnalyzer:
    """Analyzes accounts and finds reply opportunities"""
    
    def __init__(self):
        # Get X API credentials from environment variables
        self.x_api_key = os.environ.get('X_RAPID_API_KEY')
        self.x_api_host = os.environ.get('X_RAPID_API_HOST', 'twitter-api45.p.rapidapi.com')
        
        if not self.x_api_key:
            logger.error("X_RAPID_API_KEY not found in environment variables")
            raise ValueError("X_RAPID_API_KEY environment variable is required")
    
    def analyze_accounts(self, accounts: List[str], time_range: str = '24h', list_name: str = '') -> Optional[Dict]:
        """Analyze accounts and find reply opportunities"""
        try:
            logger.info(f"Starting analysis for {len(accounts)} accounts, time range: {time_range}")

            # Fetch tweets for each account
            all_tweets = []
            account_stats = {}
            # Store profile pictures by account to ensure consistency
            account_profiles = {}

            for account in accounts:
                logger.info(f"Fetching tweets for @{account}")
                tweets = self.get_tweets(account)

                if tweets:
                    # Filter out RTs and limit to 10 most recent tweets for faster processing
                    filtered_tweets = [
                        tweet for tweet in tweets
                        if tweet.get('text') and not tweet.get('text', '').startswith('RT @')
                    ][:10]

                    if filtered_tweets:
                        # Extract profile info from first tweet for consistency
                        first_tweet = filtered_tweets[0]
                        if 'author' in first_tweet and isinstance(first_tweet['author'], dict):
                            author_info = first_tweet['author']
                            account_profiles[account] = {
                                'screen_name': author_info.get('screen_name', account),
                                'name': author_info.get('name', account),
                                'avatar': author_info.get('avatar', author_info.get('profile_image_url', ''))
                            }
                        else:
                            account_profiles[account] = {
                                'screen_name': account,
                                'name': account,
                                'avatar': ''
                            }

                        # Filter by time range
                        time_filtered_tweets = self.filter_tweets_by_time_range(filtered_tweets, time_range)

                        # Process tweets to extract necessary data
                        processed_tweets = [self.process_tweet(tweet, account_profiles[account]) for tweet in time_filtered_tweets]

                        # Add account name to each tweet
                        for tweet in processed_tweets:
                            tweet['account'] = account

                        # Calculate account stats
                        account_stats[account] = self.calculate_account_performance(time_filtered_tweets)

                        logger.info(f"Found {len(processed_tweets)} tweets for @{account}")
                        all_tweets.extend(processed_tweets)

                # Rate limiting - reduced for faster processing
                time.sleep(0.2)
            
            logger.info(f"Total tweets collected: {len(all_tweets)}")
            
            # Score and rank tweets
            scored_tweets = self.score_tweets(all_tweets, account_stats)
            
            return {
                'tweet_opportunities': scored_tweets,
                'account_stats': account_stats,
                'analysis_metadata': {
                    'total_accounts': len(accounts),
                    'total_tweets': len(all_tweets),
                    'time_range': time_range,
                    'list_name': list_name
                }
            }
            
        except Exception as e:
            logger.error(f"Error in analyze_accounts: {str(e)}")
            return None
    
    def get_tweets(self, screen_name: str) -> List[Dict]:
        """Fetch tweets using RapidAPI"""
        url = f"https://{self.x_api_host}/timeline.php"
        
        # Remove @ symbol if present
        if screen_name.startswith('@'):
            screen_name = screen_name[1:]
        
        headers = {
            "X-RapidAPI-Host": self.x_api_host,
            "X-RapidAPI-Key": self.x_api_key
        }
        
        params = {"screenname": screen_name}
        
        # Try up to 2 times
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                logger.debug(f"Fetching tweets for @{screen_name} (attempt {attempt+1}/{max_attempts})")
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                tweets = data.get('timeline', [])
                
                # Process tweets to ensure IDs are properly captured
                for tweet in tweets:
                    # Ensure the tweet has an id_str
                    if 'id' in tweet and 'id_str' not in tweet:
                        tweet['id_str'] = str(tweet['id'])
                    
                    # Fix empty author.screen_name
                    if 'author' in tweet:
                        if not tweet['author'].get('screen_name'):
                            tweet['author']['screen_name'] = screen_name
                    else:
                        tweet['author'] = {'screen_name': screen_name}
                    
                    # Ensure author has an avatar field
                    if 'author' in tweet and 'avatar' not in tweet['author']:
                        tweet['author']['avatar'] = tweet['author'].get('profile_image_url', '')
                
                if tweets:
                    logger.debug(f"Successfully fetched {len(tweets)} tweets for @{screen_name}")
                    return tweets
                
                # If no tweets but we have attempts left, wait and retry
                if attempt < max_attempts - 1:
                    logger.debug(f"No tweets found for @{screen_name}, retrying...")
                    time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error fetching tweets for @{screen_name} (attempt {attempt+1}): {str(e)}")
                
                # If we have attempts left, wait and retry
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
        
        logger.warning(f"All attempts to fetch tweets for @{screen_name} failed")
        return []
    
    def process_tweet(self, tweet: Dict, account_profile: Dict = None) -> Dict:
        """Process a tweet to extract and format necessary data with proper newline handling"""
        # Extract tweet ID
        tweet_id = self._extract_tweet_id(tweet)
        
        # Proper newline handling - preserve original text structure
        raw_text = tweet.get('text', '')
        
        # Convert all newline variations to our standard marker
        # This handles: \n, \r\n, \r
        processed_text = raw_text.replace('\r\n', '_new_line_').replace('\r', '_new_line_').replace('\n', '_new_line_')
        
        # Extract basic tweet data
        processed = {
            "tweet_id": tweet_id,
            "text": processed_text,
            "created_at": tweet.get('created_at', ''),
            "engagement": {
                "likes": self._safe_int(tweet.get('favorites', 0)),
                "retweets": self._safe_int(tweet.get('retweets', 0)),
                "views": self._safe_int(tweet.get('views', 0))
            }
        }
        
        # Extract author info - use consistent account profile if provided
        if account_profile:
            processed["author"] = account_profile['screen_name']
            processed["name"] = account_profile['name']
            processed["profile_image_url"] = account_profile['avatar']
        elif 'author' in tweet and isinstance(tweet['author'], dict):
            author = tweet['author']
            processed["author"] = author.get('screen_name', '')
            processed["name"] = author.get('name', author.get('screen_name', ''))
            processed["profile_image_url"] = author.get('avatar', author.get('profile_image_url', ''))
        else:
            # Fallback to account name if author info is missing
            processed["author"] = tweet.get('account', '')
            processed["name"] = tweet.get('account', '')
            processed["profile_image_url"] = ''
        
        # Process media (photos, videos)
        processed["media"] = self._extract_media(tweet)
        
        return processed
    
    def _extract_media(self, tweet: Dict) -> Dict:
        """Extract media from tweet data"""
        media = {}
        
        # Method 1: Direct media field (from your API response)
        if 'media' in tweet and tweet['media']:
            existing_media = tweet['media']
            
            # Handle photos
            if 'photo' in existing_media and existing_media['photo']:
                media['photo'] = []
                for photo in existing_media['photo']:
                    if isinstance(photo, dict) and 'media_url_https' in photo:
                        media['photo'].append({
                            'media_url_https': photo['media_url_https'],
                            'id': photo.get('id', ''),
                            'sizes': photo.get('sizes', {})
                        })
            
            # Handle videos
            if 'video' in existing_media and existing_media['video']:
                media['video'] = []
                for video in existing_media['video']:
                    if isinstance(video, dict):
                        video_data = {
                            'media_url_https': video.get('media_url_https', ''),
                            'id': video.get('id', ''),
                            'aspect_ratio': video.get('aspect_ratio', [16, 9]),
                            'duration': video.get('duration', 0)
                        }
                        
                        # Include video variants if available
                        if 'variants' in video and video['variants']:
                            video_data['variants'] = video['variants']
                        
                        media['video'].append(video_data)
        
        # Method 2: Handle entities structure (fallback)
        if not media and 'entities' in tweet and 'media' in tweet['entities']:
            media_entities = tweet['entities']['media']
            photos = []
            
            for item in media_entities:
                if item.get('type') == 'photo':
                    photos.append({
                        'media_url_https': item.get('media_url_https', ''),
                        'id': item.get('id_str', ''),
                        'sizes': item.get('sizes', {})
                    })
            
            if photos:
                media['photo'] = photos
        
        # Method 3: Handle extended_entities structure (for videos)
        if 'extended_entities' in tweet and 'media' in tweet['extended_entities']:
            media_entities = tweet['extended_entities']['media']
            photos = []
            videos = []
            
            for item in media_entities:
                if item.get('type') == 'photo':
                    photos.append({
                        'media_url_https': item.get('media_url_https', ''),
                        'id': item.get('id_str', ''),
                        'sizes': item.get('sizes', {})
                    })
                elif item.get('type') in ['video', 'animated_gif']:
                    video_data = {
                        'media_url_https': item.get('media_url_https', ''),
                        'id': item.get('id_str', ''),
                        'aspect_ratio': [16, 9],  # Default aspect ratio
                        'duration': 0
                    }
                    
                    # Extract video variants
                    if 'video_info' in item and 'variants' in item['video_info']:
                        video_data['variants'] = item['video_info']['variants']
                        
                        # Try to get duration and aspect ratio
                        video_info = item['video_info']
                        if 'duration_millis' in video_info:
                            video_data['duration'] = video_info['duration_millis']
                        if 'aspect_ratio' in video_info:
                            video_data['aspect_ratio'] = video_info['aspect_ratio']
                    
                    videos.append(video_data)
            
            if photos and 'photo' not in media:
                media['photo'] = photos
            if videos:
                media['video'] = videos
        
        return media
    
    def filter_tweets_by_time_range(self, tweets: List[Dict], time_range: str) -> List[Dict]:
        """Filter tweets by time range"""
        hours_map = {
            '24h': 24,
            '48h': 48,
            '72h': 72,
            '1w': 168
        }
        
        hours = hours_map.get(time_range, 24)
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_tweets = []
        for tweet in tweets:
            try:
                # Twitter date format: "Day Mon DD HH:MM:SS +0000 YYYY"
                tweet_date = datetime.strptime(
                    tweet.get('created_at', ''),
                    "%a %b %d %H:%M:%S %z %Y"
                ).replace(tzinfo=None)
                
                if tweet_date > cutoff_time:
                    filtered_tweets.append(tweet)
            except Exception as e:
                logger.error(f"Error parsing tweet date: {str(e)}")
                continue
        
        return filtered_tweets
    
    def score_tweets(self, tweets: List[Dict], account_stats: Dict) -> List[Dict]:
        """Score tweets based on reply opportunity factors"""
        now = datetime.now()
        scored_tweets = []
        
        for tweet in tweets:
            try:
                # Calculate time factor (recency)
                tweet_date = datetime.strptime(
                    tweet.get('created_at', ''),
                    "%a %b %d %H:%M:%S %z %Y"
                ).replace(tzinfo=None)
                
                hours_ago = (now - tweet_date).total_seconds() / 3600
                
                # Time factor calculation
                if hours_ago < 0.25:  # Less than 15 minutes
                    time_factor = 1.0
                elif hours_ago < 1:  # Less than 1 hour
                    time_factor = 0.9
                elif hours_ago < 3:  # Less than 3 hours
                    time_factor = 0.7
                elif hours_ago < 6:  # Less than 6 hours
                    time_factor = 0.5
                elif hours_ago < 12:  # Less than 12 hours
                    time_factor = 0.3
                else:  # More than 12 hours
                    time_factor = 0.1
                
                # Get engagement metrics
                likes = self._safe_int(tweet.get('engagement', {}).get('likes', 0))
                retweets = self._safe_int(tweet.get('engagement', {}).get('retweets', 0))
                views = self._safe_int(tweet.get('engagement', {}).get('views', 0))
                
                # Calculate engagement rate
                engagement_rate = 0
                if views > 0:
                    engagement_rate = (likes + retweets) / views
                
                # Normalize engagement rate (0-1 scale)
                normalized_engagement = min(engagement_rate * 20, 1.0)
                
                # Views factor
                views_factor = 0.5  # Default
                account = tweet.get('account')
                if account and account in account_stats:
                    avg_views = account_stats[account].get('avg_views_per_tweet', 0)
                    if avg_views > 0:
                        views_factor = min(views / avg_views, 2.0) / 2
                
                # Creator factor
                creator_factor = 0.5  # Default
                if account and account in account_stats:
                    avg_views = account_stats[account].get('avg_views_per_tweet', 0)
                    # Sweet spot: not too small, not too big
                    if avg_views < 100:
                        creator_factor = 0.2
                    elif avg_views < 1000:
                        creator_factor = 0.6
                    elif avg_views < 10000:
                        creator_factor = 1.0
                    elif avg_views < 100000:
                        creator_factor = 0.7
                    else:
                        creator_factor = 0.4
                
                # Calculate final score
                score = (
                    time_factor * 0.4 +
                    normalized_engagement * 0.3 +
                    views_factor * 0.2 +
                    creator_factor * 0.1
                )
                
                # Add score to tweet
                tweet['score'] = score
                tweet['score_factors'] = {
                    'time_factor': time_factor,
                    'engagement_rate': normalized_engagement,
                    'views_factor': views_factor,
                    'creator_factor': creator_factor
                }
                
                scored_tweets.append(tweet)
                
            except Exception as e:
                logger.error(f"Error scoring tweet: {str(e)}")
                continue
        
        # Sort by score (highest first)
        scored_tweets.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return scored_tweets
    
    def calculate_account_performance(self, account_tweets: List[Dict]) -> Dict:
        """Calculate performance metrics for an account"""
        performance = {
            'total_tweets': len(account_tweets),
            'total_likes': 0,
            'total_retweets': 0,
            'total_views': 0,
            'avg_likes_per_tweet': 0,
            'avg_retweets_per_tweet': 0,
            'avg_views_per_tweet': 0,
            'engagement_rate': 0
        }
        
        for tweet in account_tweets:
            favorites = self._safe_int(tweet.get('favorites', 0))
            retweets = self._safe_int(tweet.get('retweets', 0))
            views = self._safe_int(tweet.get('views', 0))
            
            performance['total_likes'] += favorites
            performance['total_retweets'] += retweets
            performance['total_views'] += views
        
        if account_tweets:
            performance['avg_likes_per_tweet'] = performance['total_likes'] / len(account_tweets)
            performance['avg_retweets_per_tweet'] = performance['total_retweets'] / len(account_tweets)
            performance['avg_views_per_tweet'] = performance['total_views'] / len(account_tweets)
            
            total_interactions = performance['total_likes'] + performance['total_retweets']
            total_views = performance['total_views']
            
            performance['engagement_rate'] = (total_interactions / total_views * 100) if total_views > 0 else 0
        
        return performance
    
    def _safe_int(self, value: Any) -> int:
        """Convert value to int safely"""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    
    def _extract_tweet_id(self, tweet: Dict) -> str:
        """Extract tweet ID from tweet data"""
        # Try multiple possible ID fields
        for field in ['id_str', 'tweet_id', 'id']:
            if field in tweet and tweet[field]:
                return str(tweet[field])
        
        logger.warning("No tweet ID found in data")
        return ''