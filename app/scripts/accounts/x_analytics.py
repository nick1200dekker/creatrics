"""
X Analytics module for fetching and processing X/Twitter metrics
with Firebase storage integration using both latest and historical storage
Enhanced to fetch 6 months of historical data on initial connection
and daily updates for posts within last 7 days
"""
import os
import json
import requests
import time
import logging
import re
from datetime import datetime, timedelta
from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class XAnalytics:
    """Handle X/Twitter analytics data fetching and processing with Firebase storage"""
    
    # Track running fetches to prevent duplicates
    running_fetches = {}
    
    def __init__(self, user_id):
        """Initialize the X Analytics object with user data and API credentials"""
        self.user_id = user_id
        
        # Get API credentials from environment variables
        self.api_key = self._get_api_credentials('key')
        self.api_host = self._get_api_credentials('host')
        
        # Initialize Firestore DB if not already initialized
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                # App already initialized
                pass
        
        # Get Firestore client
        self.db = firestore.client()
        
        # Get X handle from Firebase
        self.x_handle = self._get_handle()
        logger.info(f"Initialized X Analytics for handle: {self.x_handle}")
    
    def _get_api_credentials(self, credential_type):
        """Get API credentials from environment variables"""
        if credential_type == 'key':
            # Get from environment variables (works both locally and in Cloud Run)
            api_key = os.environ.get('X_RAPID_API_KEY')
            if api_key:
                return api_key
            
            # No fallback - log error and raise exception
            logger.error("X_RAPID_API_KEY not found in environment variables")
            raise ValueError("X_RAPID_API_KEY environment variable is required")
        
        elif credential_type == 'host':
            # Get from environment variables with default fallback
            return os.environ.get('X_RAPID_API_HOST', 'twitter-api45.p.rapidapi.com')
    
    def _get_handle(self):
        """Get the X handle from Firebase for the current user"""
        try:
            # Get user document from Firestore
            user_doc = self.db.collection('users').document(self.user_id).get()
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                # Get X account username from user data
                handle = user_data.get('x_account', '')
                # Strip @ symbol if present
                return handle.lstrip('@') if handle else None
            return None
        except Exception as e:
            logger.error(f"Error getting X handle: {str(e)}")
            return None
    
    def get_account_info(self):
        """Get account info for an X handle"""
        if not self.x_handle:
            logger.error("No X handle provided")
            return None
        
        # Ensure username has no @ symbol
        username = self.x_handle.lstrip('@')
        
        url = f"https://{self.api_host}/screenname.php"
        
        querystring = {"screenname": username}
        
        headers = {
            "X-RapidAPI-Host": self.api_host,
            "X-RapidAPI-Key": self.api_key
        }
        
        # Try up to 2 times (initial attempt + 1 retry)
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                logger.info(f"Fetching account info for {username} (attempt {attempt+1}/{max_attempts})")
                response = requests.get(url, headers=headers, params=querystring)
                
                # Handle HTTP error status codes
                if response.status_code != 200:
                    logger.error(f"Error fetching account info: {response.status_code} {response.reason}")
                    
                    # For any error, retry but don't trigger cool-down
                    if attempt < max_attempts - 1:
                        logger.info(f"Retrying account info fetch for {username}...")
                        time.sleep(5)  # Increase wait time to 5 seconds before retry
                        continue
                    
                    return None
                
                # Process successful response
                data = response.json()
                
                # The account info is directly in the response
                if data and isinstance(data, dict):
                    # Check for critical fields to validate response
                    if 'sub_count' in data and 'friends' in data:
                        logger.info(f"Successfully fetched account info for {username}")
                        return data
                
                # No valid data but we have attempts left, retry
                if attempt < max_attempts - 1:
                    logger.info(f"No account data found for {username}, retrying...")
                    time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error fetching account info: {str(e)}")
                
                # If we have attempts left, wait briefly and retry
                if attempt < max_attempts - 1:
                    logger.info(f"Retrying account info fetch for {username}...")
                    time.sleep(5)
        
        return None
    
    def get_timeline_data(self, max_posts=None, is_initial=False):
        """
        Get timeline data for an X handle
        Args:
            max_posts: Maximum number of posts to fetch (None = unlimited)
            is_initial: Whether this is the initial fetch (for 6 months of data)
        """
        if not self.x_handle:
            logger.error("No X handle provided")
            return None
        
        # Ensure username has no @ symbol
        username = self.x_handle.lstrip('@')
        
        url = f"https://{self.api_host}/timeline.php"
        
        querystring = {"screenname": username}
        
        headers = {
            "X-RapidAPI-Host": self.api_host,
            "X-RapidAPI-Key": self.api_key
        }
        
        # Store all fetched posts here
        all_posts = []
        cursor = None
        
        # Set target based on whether this is initial fetch
        # For initial: try to get as much historical data as API allows (target 1000 posts)
        # For refresh: only get last week of posts (stop when we hit posts older than 7 days)
        six_months_ago = datetime.now() - timedelta(days=180)
        one_week_ago = datetime.now() - timedelta(days=7)
        target_posts = max_posts if max_posts else (1000 if is_initial else 200)  # 200 for refresh to ensure we get a full week

        logger.info(f"Fetching {'initial historical' if is_initial else 'last 7 days'} timeline data for {username}")

        # We need to paginate until we have enough posts or reach the time cutoff
        while len(all_posts) < target_posts:
            # Try up to 2 times for each page (initial attempt + 1 retry)
            max_attempts = 2
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Fetching timeline page for {username} (attempt {attempt+1}/{max_attempts})")
                    
                    # Add cursor parameter if we have one
                    if cursor:
                        querystring["cursor"] = cursor
                        
                    response = requests.get(url, headers=headers, params=querystring)
                    
                    # Handle HTTP error status codes
                    if response.status_code != 200:
                        logger.error(f"Error fetching timeline: {response.status_code} {response.reason}")
                        
                        # For any error, retry but don't trigger cool-down
                        if attempt < max_attempts - 1:
                            logger.info(f"Retrying timeline fetch for {username}...")
                            time.sleep(5)  # Increase wait time to 5 seconds before retry
                            continue
                        
                        # If we have some posts already, return them
                        if all_posts:
                            logger.info(f"Returning {len(all_posts)} posts collected so far")
                            return all_posts
                        return None
                    
                    # Process successful response
                    data = response.json()
                    tweets = data.get('timeline', [])
                    
                    # Process tweets to ensure IDs are properly captured
                    for tweet in tweets:
                        # Parse created_at to check time cutoffs
                        created_at = tweet.get('created_at', '')
                        if created_at:
                            try:
                                tweet_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                                tweet_date_local = tweet_date.replace(tzinfo=None)

                                # For initial fetch: stop at 6 months
                                if is_initial and tweet_date_local < six_months_ago:
                                    logger.info(f"Reached posts older than 6 months, stopping")
                                    return all_posts

                                # For refresh: stop at 7 days
                                if not is_initial and tweet_date_local < one_week_ago:
                                    logger.info(f"Reached posts older than 7 days, stopping refresh")
                                    return all_posts

                            except Exception as e:
                                logger.debug(f"Error parsing date: {e}")

                        # Ensure the tweet has an id_str
                        if 'id' in tweet and not 'id_str' in tweet:
                            tweet['id_str'] = str(tweet['id'])

                        # Fix empty author.screen_name by setting it to the requested screen_name
                        if 'author' in tweet:
                            if not tweet['author'].get('screen_name'):
                                tweet['author']['screen_name'] = username
                        else:
                            tweet['author'] = {'screen_name': username}

                        # Only add non-retweets to our collection
                        if not tweet.get('retweeted', False):
                            all_posts.append(tweet)
                    
                    logger.info(f"Fetched {len(tweets)} tweets, now have {len(all_posts)} total non-RT posts")
                    
                    # Check if we need to fetch more pages
                    if 'next_cursor' in data and len(all_posts) < target_posts:
                        cursor = data['next_cursor']
                        logger.info(f"Found next cursor, will fetch next page")
                        # Success for this page, break the retry loop
                        break
                    else:
                        # No more pages or we have enough posts
                        logger.info(f"No more pages or have enough posts, returning {len(all_posts)} posts")
                        return all_posts
                    
                except Exception as e:
                    logger.error(f"Error fetching timeline: {str(e)}")
                    
                    # If we have attempts left, wait briefly and retry
                    if attempt < max_attempts - 1:
                        logger.info(f"Retrying timeline fetch for {username}...")
                        time.sleep(5)
            
            # If we didn't break out of the loop with a successful fetch, we've exhausted retries
            if not 'next_cursor' in data:
                break
                
            # Small delay between pages to avoid rate limiting
            time.sleep(1)
        
        # If we've made it here, we either have enough posts or no more pages
        logger.info(f"Completed timeline fetch with {len(all_posts)} posts")

        # Log date distribution of fetched posts
        if all_posts:
            post_dates = []
            for post in all_posts:
                created_at = post.get('created_at', '')
                if created_at:
                    try:
                        post_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                        post_dates.append(post_date.replace(tzinfo=None).strftime('%Y-%m-%d'))
                    except:
                        pass

            if post_dates:
                unique_dates = sorted(set(post_dates))
                logger.info(f"Fetched posts span {len(unique_dates)} unique days from {unique_dates[0]} to {unique_dates[-1]}")
                logger.info(f"All unique post dates: {', '.join(unique_dates)}")

        return all_posts
    
    def get_replies_data(self):
        """Get replies data for the user"""
        if not self.x_handle:
            logger.error("No X handle provided for replies")
            return None
        
        # Check if a fetch is already running for this user
        if f"{self.user_id}_replies" in XAnalytics.running_fetches and XAnalytics.running_fetches[f"{self.user_id}_replies"]:
            logger.info(f"A replies data fetch is already running for user {self.user_id}")
            return None
        
        try:
            # Mark that a fetch is in progress for this user
            XAnalytics.running_fetches[f"{self.user_id}_replies"] = True
            
            # Fetch replies data
            replies_data = self._fetch_replies_data()
            
            # Reset the status regardless of success or failure
            XAnalytics.running_fetches[f"{self.user_id}_replies"] = False
            
            return replies_data
            
        except Exception as e:
            # Make sure to reset status even if an exception occurs
            XAnalytics.running_fetches[f"{self.user_id}_replies"] = False
            logger.error(f"Error in get_replies_data: {str(e)}")
            return None
    
    def _fetch_replies_data(self):
        """Fetch replies data from API and return it"""
        try:
            username = self.x_handle.lstrip('@')
            logger.info(f"Fetching replies for {username}")

            # Track all replies
            all_replies = []
            cursor = None
            max_attempts = 3

            # Initialize pagination safeguard variables
            prev_reply_count = 0
            pagination_no_progress_count = 0

            # Set 7 days cutoff for replies
            one_week_ago = datetime.now() - timedelta(days=7)

            # Paginate through replies using cursor until we have 100 replies or no more results
            while len(all_replies) < 100:
                remaining_attempts = max_attempts
                success = False
                
                while remaining_attempts > 0 and not success:
                    try:
                        # Prepare API request
                        url = f"https://{self.api_host}/replies.php"
                        
                        headers = {
                            "X-RapidAPI-Host": self.api_host,
                            "X-RapidAPI-Key": self.api_key
                        }
                        
                        # Prepare query parameters
                        querystring = {"screenname": username}
                        if cursor:
                            querystring["cursor"] = cursor
                        
                        # Make the API request
                        logger.info(f"Fetching replies page for {username} (cursor: {cursor[:20] if cursor else 'None'}...)")
                        response = requests.get(url, headers=headers, params=querystring)
                        
                        # Check if the response is valid
                        if response.status_code != 200:
                            logger.error(f"API error: Status code {response.status_code}")
                            raise Exception(f"Bad status code: {response.status_code}")
                            
                        data = response.json()
                        
                        # Log the response structure for debugging
                        if not cursor:  # Only log on first request
                            logger.debug(f"Replies API response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                        
                        # Check if response contains timeline data
                        if 'timeline' in data and isinstance(data['timeline'], list):
                            # The API returns posts in conversation order
                            # We need to analyze the relationship between posts
                            timeline = data['timeline']
                            logger.info(f"Found {len(timeline)} posts in timeline")
                            
                            replies_found_this_page = 0
                            i = 0
                            
                            while i < len(timeline):
                                # Get current post
                                current_post = timeline[i]
                                
                                # Check if this is an original post or a reply
                                is_reply = current_post.get('in_reply_to_status_id_str') is not None
                                is_by_user = current_post.get('author', {}).get('screen_name', '').lower() == username.lower()
                                
                                if is_by_user and is_reply and i > 0:
                                    # Check if reply is within last 7 days
                                    reply_date_str = current_post.get('created_at', '')
                                    if reply_date_str:
                                        try:
                                            reply_date = datetime.strptime(reply_date_str, '%a %b %d %H:%M:%S %z %Y')
                                            reply_date_local = reply_date.replace(tzinfo=None)

                                            # Skip replies older than 7 days
                                            if reply_date_local < one_week_ago:
                                                logger.info(f"Reached replies older than 7 days, stopping")
                                                return all_replies
                                        except Exception as e:
                                            logger.debug(f"Error parsing reply date: {e}")

                                    # This is a reply by our user
                                    # Find the original post it's replying to
                                    original_post = None

                                    # Look for the original post in the timeline
                                    # It might be directly before our reply or elsewhere
                                    for j in range(i-1, -1, -1):
                                        potential_original = timeline[j]
                                        # Check if this is the post being replied to
                                        if potential_original.get('tweet_id') == current_post.get('in_reply_to_status_id_str'):
                                            original_post = potential_original
                                            break

                                    # If we can't find the original post, use the previous post as a fallback
                                    if original_post is None and i > 0:
                                        original_post = timeline[i-1]

                                    # Create the reply pair if we have an original post
                                    # Only include replies to main posts (not replies to replies)
                                    if original_post is not None and original_post.get('in_reply_to_status_id_str') is None:
                                        reply_pair = {
                                            'original_post': self._extract_essential_post_data(original_post),
                                            'reply': self._extract_essential_post_data(current_post, is_reply=True)
                                        }
                                        all_replies.append(reply_pair)
                                        replies_found_this_page += 1
                                
                                i += 1
                            
                            logger.info(f"Found {replies_found_this_page} replies on this page, total: {len(all_replies)}")
                            
                            # Check if there are more results
                            if data.get('next_cursor') and len(all_replies) < 100:
                                cursor = data['next_cursor']
                                logger.info(f"Getting next page with cursor: {cursor[:20]}...")
                                success = True
                                
                                # Add safety pagination limit to prevent infinite loops
                                if len(all_replies) == prev_reply_count:
                                    pagination_no_progress_count += 1
                                    if pagination_no_progress_count >= 5:
                                        logger.info(f"Breaking pagination loop - no new replies found after 5 pages")
                                        break
                                else:
                                    pagination_no_progress_count = 0
                                
                                prev_reply_count = len(all_replies)
                            else:
                                # No more results or we have enough
                                logger.info(f"Completed replies fetch with {len(all_replies)} reply pairs")
                                break
                        else:
                            logger.warning(f"Unexpected API response format: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                            # If no timeline data, return what we have
                            if len(all_replies) > 0:
                                logger.info(f"Returning {len(all_replies)} replies collected so far")
                                return all_replies
                            return []
                        
                    except Exception as e:
                        logger.error(f"Error fetching replies data (attempt {max_attempts - remaining_attempts + 1}): {str(e)}")
                        remaining_attempts -= 1
                        time.sleep(2)  # Wait before retrying
                
                # If we couldn't get this page after multiple attempts, stop
                if not success and remaining_attempts <= 0:
                    logger.error("Failed to fetch replies data after multiple attempts")
                    if len(all_replies) > 0:
                        # If we have some replies, continue with what we have
                        break
                    return []
                
                # If we don't have a cursor or we've reached the target reply count, break
                if not cursor or len(all_replies) >= 100:
                    break
            
            # Take only the first 100 replies and sort by views
            replies_to_store = all_replies[:100] if len(all_replies) > 100 else all_replies
            
            # Sort replies by views of the reply itself (descending)
            sorted_replies = sorted(
                replies_to_store,
                key=lambda r: r['reply'].get('views', 0),
                reverse=True
            )
            
            logger.info(f"Returning {len(sorted_replies)} sorted replies")
            return sorted_replies
            
        except Exception as e:
            logger.error(f"Error in _fetch_replies_data: {str(e)}")
            return []
    
    def get_analytics_data(self, is_initial=False):
        """
        Get analytics data for X account
        Args:
            is_initial: Whether this is the initial fetch (for 6 months of data)
        """
        logger.info(f"Fetching {'initial' if is_initial else 'updated'} X analytics data...")
        
        # Get account info from X API
        account_info = self.get_account_info()
        if not account_info:
            logger.error("Failed to get account info")
            return None
        
        # Get timeline data from X API
        if is_initial:
            # For initial fetch, get 6 months of data
            timeline_data = self.get_timeline_data(is_initial=True)
        else:
            # For daily updates, get recent posts
            timeline_data = self.get_timeline_data(max_posts=100)
        
        if not timeline_data:
            logger.error("Failed to get timeline data")
            return None
        
        # Add a small delay before fetching replies to avoid rate limiting
        time.sleep(2)
        
        # Get replies data from X API
        replies_data = self.get_replies_data()
        if replies_data:
            logger.info(f"Fetched {len(replies_data)} replies")
            # Store replies in Firebase
            self._store_replies(replies_data)
        else:
            logger.warning("No replies data fetched")
        
        # Store posts
        if is_initial:
            # Store all historical posts
            self._store_all_posts(timeline_data)
        else:
            # Update recent posts only
            self._update_recent_posts(timeline_data)
        
        # Calculate and store metrics
        metrics = self._calculate_metrics(account_info, timeline_data)
        self._store_metrics(metrics)
        
        # Calculate and store daily metrics
        self._calculate_daily_metrics()
        
        return metrics
    
    def _calculate_metrics(self, account_info, all_posts):
        """Calculate metrics based on account info and posts data"""
        # Use the 15 most recent posts for rolling averages
        recent_posts = all_posts[:15] if len(all_posts) >= 15 else all_posts
        
        now = datetime.now()
        
        # Default values
        result = {
            "timestamp": now.isoformat(),
            "user_id": self.user_id,
            "followers_count": 0,
            "following_count": 0,
            "followers_to_following_ratio": 0,
            "ratio_status": "N/A",
            "rolling_avg_views": 0,
            "rolling_avg_engagement": 0,
            "total_posts_analyzed": len(all_posts),
            "last_updated": now.strftime("%b %d, %Y %I:%M %p")
        }
        
        # Extract metrics from API data if available
        if account_info:
            # Handle sub_count (followers)
            try:
                followers = int(account_info.get('sub_count', 0))
                result["followers_count"] = followers if followers else 0
            except (TypeError, ValueError):
                result["followers_count"] = 0
            
            # Handle friends (following)
            try:
                following = int(account_info.get('friends', 0))
                result["following_count"] = following if following else 0
            except (TypeError, ValueError):
                result["following_count"] = 0
            
            # Calculate following to followers ratio
            if result["followers_count"] > 0:
                # Calculate ratio as percentage of following to followers
                result["followers_to_following_ratio"] = (float(result["following_count"]) / float(result["followers_count"])) * 100
                
                # Set status based on ratio
                ratio = result["followers_to_following_ratio"]
                if ratio < 60:
                    result["ratio_status"] = "Good"
                elif ratio < 100:
                    result["ratio_status"] = "Average"
                else:
                    result["ratio_status"] = "Low"
            else:
                # Set default values when followers is 0
                result["followers_to_following_ratio"] = 999  # If no followers, set a high ratio
                result["ratio_status"] = "Low"
        
        # Process recent posts for rolling averages
        if recent_posts:
            # Calculate rolling average views
            total_views = 0
            valid_view_count = 0
            
            # Calculate rolling average engagement
            total_engagements = 0
            total_impressions = 0
            
            for tweet in recent_posts:
                # Process views
                views = self._parse_count_value(tweet.get('views'))
                if views > 0:
                    total_views += views
                    valid_view_count += 1
                
                # Process engagement (likes + retweets + bookmarks)
                likes = self._parse_count_value(tweet.get('favorites'))
                retweets = self._parse_count_value(tweet.get('retweets')) or self._parse_count_value(tweet.get('retweet_count'))
                bookmarks = self._parse_count_value(tweet.get('bookmarks'))
                
                # Sum up all engagement metrics
                total_engagements += (likes + retweets + bookmarks)
                
                if views > 0:
                    total_impressions += views
            
            # Calculate rolling averages
            result['rolling_avg_views'] = total_views / max(1, valid_view_count) if valid_view_count > 0 else 0
            
            if total_impressions > 0:
                result['rolling_avg_engagement'] = (total_engagements / total_impressions) * 100
            else:
                # If we don't have view data, calculate engagement based on followers
                if result["followers_count"] > 0:
                    result['rolling_avg_engagement'] = (total_engagements / result["followers_count"]) * 100
                else:
                    result['rolling_avg_engagement'] = 0
        
        return result
    
    def _parse_count_value(self, value):
        """Parse count values, handling string values with K or M suffixes"""
        if value is None:
            return 0
            
        try:
            # Handle string values with K or M
            if isinstance(value, str):
                value = value.replace(',', '')
                if 'K' in value:
                    return int(float(value.replace('K', '')) * 1000)
                elif 'M' in value:
                    return int(float(value.replace('M', '')) * 1000000)
                else:
                    return int(value)
            else:
                return int(value)
        except (ValueError, TypeError):
            return 0
    
    def _store_metrics(self, metrics):
        """Store the analytics metrics in Firebase with both latest and historical data"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Store as latest (for dashboard)
            latest_ref = self.db.collection('users').document(self.user_id).collection('x_analytics').document('latest')
            latest_ref.set(metrics)
            
            # Store as historical data
            history_ref = self.db.collection('users').document(self.user_id).collection('x_analytics').document('history').collection('daily').document(today)
            history_ref.set(metrics)
            
            logger.info(f"X Analytics metrics stored successfully in Firebase for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error storing metrics in Firebase: {str(e)}")
    
    def _extract_media_url(self, post):
        """Extract media URL from post if available - prioritizes video URLs over thumbnails"""
        try:
            # Check if post has media
            if 'media' in post:
                media = post['media']
                
                # Check for video (prioritize video over photo)
                if 'video' in media and media['video'] and len(media['video']) > 0:
                    video = media['video'][0]
                    # Get variants and select a good quality one
                    if 'variants' in video and video['variants']:
                        # Filter video variants (not m3u8 playlists)
                        mp4_variants = [
                            v for v in video['variants'] 
                            if v.get('content_type', '') == 'video/mp4' and 'bitrate' in v and 'url' in v
                        ]
                        
                        if mp4_variants:
                            # Sort by bitrate and get a medium quality
                            sorted_variants = sorted(mp4_variants, key=lambda x: x.get('bitrate', 0))
                            # Get a medium-quality variant (not too high, not too low)
                            if len(sorted_variants) > 2:
                                # Use the middle variant
                                return sorted_variants[len(sorted_variants) // 2].get('url', '')
                            else:
                                # If just 1-2 variants, use the highest quality
                                return sorted_variants[-1].get('url', '')
                    
                # Check for photo (only use if no video found)
                if 'photo' in media and media['photo'] and len(media['photo']) > 0:
                    return media['photo'][0].get('media_url_https', '')
            
            # No media found
            return ''
        except Exception as e:
            logger.debug(f"Error extracting media URL: {str(e)}")
            return ''
    
    def _store_all_posts(self, posts):
        """Store all posts in Firebase with individual documents"""
        try:
            # Ensure we're only storing non-retweets
            filtered_posts = [post for post in posts if not post.get('retweeted', False)]
            logger.info(f"Storing {len(filtered_posts)} non-retweet posts")
            
            # Get posts collection reference
            posts_collection = self.db.collection('users').document(self.user_id).collection('x_posts_individual')
            
            # Store each post as individual document
            batch = self.db.batch()
            batch_count = 0
            
            for post in filtered_posts:
                # Extract media URL if available
                media_url = self._extract_media_url(post)
                
                # Get the complete text - preserve as-is from API
                post_text = post.get('text', '')
                
                # Parse created_at date
                created_at = post.get('created_at', '')
                post_date = None
                if created_at:
                    try:
                        post_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                    except Exception as e:
                        logger.debug(f"Error parsing date: {e}")
                
                # Create post data with all required fields
                post_data = {
                    'id': post.get('tweet_id') or post.get('id_str') or post.get('id', ''),
                    'text': post_text,  # Raw text with all formatting preserved
                    'created_at': created_at,
                    'created_at_timestamp': post_date.timestamp() if post_date else None,
                    'views': self._parse_count_value(post.get('views')),
                    'likes': self._parse_count_value(post.get('favorites')),
                    'retweets': self._parse_count_value(post.get('retweets')) or self._parse_count_value(post.get('retweet_count')),
                    'replies': self._parse_count_value(post.get('reply_count') or post.get('replies')),
                    'bookmarks': self._parse_count_value(post.get('bookmarks')),
                    'media_url': media_url,
                    'last_updated': datetime.now().isoformat(),
                    'is_historical': True  # Mark as historical data
                }
                
                # Use tweet ID as document ID
                doc_id = post_data['id']
                if doc_id:
                    doc_ref = posts_collection.document(doc_id)
                    batch.set(doc_ref, post_data, merge=True)
                    batch_count += 1
                    
                    # Commit batch every 100 documents
                    if batch_count >= 100:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
                        logger.info(f"Committed batch of 100 posts")
            
            # Commit remaining batch
            if batch_count > 0:
                batch.commit()
                logger.info(f"Committed final batch of {batch_count} posts")
            
            logger.info(f"Stored {len(filtered_posts)} posts for user {self.user_id}")
            
            # Also update the timeline document for backward compatibility
            self._store_posts(filtered_posts[:100])  # Store most recent 100 in timeline doc
            
        except Exception as e:
            logger.error(f"Error storing all posts in Firebase: {str(e)}")
    
    def _update_recent_posts(self, posts):
        """Update only posts from the last 7 days and cleanup posts older than 6 months"""
        try:
            seven_days_ago = datetime.now() - timedelta(days=7)
            six_months_ago = datetime.now() - timedelta(days=180)
            posts_collection = self.db.collection('users').document(self.user_id).collection('x_posts_individual')

            # First, cleanup posts older than 6 months
            logger.info(f"Checking for posts older than 6 months to delete")
            all_posts_query = posts_collection.stream()
            posts_to_delete = []

            for doc in all_posts_query:
                post_data = doc.to_dict()
                created_at = post_data.get('created_at', '')
                if created_at:
                    try:
                        post_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                        if post_date.replace(tzinfo=None) < six_months_ago:
                            posts_to_delete.append(doc.id)
                    except Exception as e:
                        logger.debug(f"Error parsing date for cleanup: {e}")

            # Delete old posts in batches
            if posts_to_delete:
                logger.info(f"Deleting {len(posts_to_delete)} posts older than 6 months")
                batch = self.db.batch()
                batch_count = 0

                for post_id in posts_to_delete:
                    doc_ref = posts_collection.document(post_id)
                    batch.delete(doc_ref)
                    batch_count += 1

                    if batch_count >= 500:  # Firestore batch limit
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0

                if batch_count > 0:
                    batch.commit()

                logger.info(f"Successfully deleted {len(posts_to_delete)} old posts")
            else:
                logger.info("No posts older than 6 months to delete")

            # Filter posts from last 7 days for update
            recent_posts = []
            for post in posts:
                created_at = post.get('created_at', '')
                if created_at:
                    try:
                        post_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                        if post_date.replace(tzinfo=None) >= seven_days_ago:
                            recent_posts.append(post)
                    except Exception as e:
                        logger.debug(f"Error parsing date: {e}")

            logger.info(f"Updating {len(recent_posts)} posts from last 7 days")
            
            if not recent_posts:
                logger.info("No recent posts to update")
                # Still update the timeline document with latest 100 posts
                self._store_posts(posts[:100])
                return
            
            # Update posts
            batch = self.db.batch()
            batch_count = 0
            
            for post in recent_posts:
                # Extract media URL if available
                media_url = self._extract_media_url(post)
                
                # Get the complete text - preserve as-is from API
                post_text = post.get('text', '')
                
                # Parse created_at date
                created_at = post.get('created_at', '')
                post_date = None
                if created_at:
                    try:
                        post_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                    except Exception as e:
                        logger.debug(f"Error parsing date: {e}")
                
                # Create post data with updated metrics
                post_data = {
                    'id': post.get('tweet_id') or post.get('id_str') or post.get('id', ''),
                    'text': post_text,
                    'created_at': created_at,
                    'created_at_timestamp': post_date.timestamp() if post_date else None,
                    'views': self._parse_count_value(post.get('views')),
                    'likes': self._parse_count_value(post.get('favorites')),
                    'retweets': self._parse_count_value(post.get('retweets')) or self._parse_count_value(post.get('retweet_count')),
                    'replies': self._parse_count_value(post.get('reply_count') or post.get('replies')),
                    'bookmarks': self._parse_count_value(post.get('bookmarks')),
                    'media_url': media_url,
                    'last_updated': datetime.now().isoformat()
                }
                
                # Use tweet ID as document ID
                doc_id = post_data['id']
                if doc_id:
                    doc_ref = posts_collection.document(doc_id)
                    batch.set(doc_ref, post_data, merge=True)
                    batch_count += 1
                    
                    # Commit batch every 100 documents
                    if batch_count >= 100:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
            
            # Commit remaining batch
            if batch_count > 0:
                batch.commit()
            
            logger.info(f"Updated {len(recent_posts)} recent posts")
            
            # Also update the timeline document
            self._store_posts(posts[:100])  # Store most recent 100 in timeline doc
            
        except Exception as e:
            logger.error(f"Error updating recent posts: {str(e)}")
    
    def _calculate_daily_metrics(self):
        """Calculate daily metrics from individual posts"""
        try:
            # Get all posts
            posts_collection = self.db.collection('users').document(self.user_id).collection('x_posts_individual')

            # Get posts from last 180 days (6 months) for daily metrics
            cutoff_date = datetime.now() - timedelta(days=180)
            logger.info(f"Calculating daily metrics with cutoff date: {cutoff_date.strftime('%Y-%m-%d')}")

            # Query posts (we'll filter by date in memory since Firestore doesn't support timestamp queries well)
            all_posts = posts_collection.stream()

            # Group posts by day
            daily_data = {}
            posts_processed = 0
            posts_within_cutoff = 0
            date_parse_errors = 0
            
            for doc in all_posts:
                post = doc.to_dict()
                created_at = post.get('created_at', '')
                
                if created_at:
                    try:
                        # Try different date formats
                        post_date = None
                        if isinstance(created_at, str):
                            # Twitter API format: "Wed Jun 05 14:26:15 +0000 2024"
                            try:
                                post_date = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                            except ValueError:
                                # Try ISO format as fallback
                                try:
                                    post_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                except:
                                    continue
                        
                        if post_date:
                            post_date_local = post_date.replace(tzinfo=None)

                            # Count all posts for metrics
                            posts_processed += 1

                            if post_date_local >= cutoff_date:
                                posts_within_cutoff += 1
                                date_key = post_date_local.strftime('%Y-%m-%d')

                                if date_key not in daily_data:
                                    daily_data[date_key] = {
                                        'date': date_key,
                                        'posts_count': 0,
                                        'total_views': 0,
                                        'total_likes': 0,
                                        'total_retweets': 0,
                                        'total_replies': 0,
                                        'total_bookmarks': 0,
                                        'total_engagement': 0
                                    }
                                
                                daily_data[date_key]['posts_count'] += 1
                                daily_data[date_key]['total_views'] += post.get('views', 0)
                                daily_data[date_key]['total_likes'] += post.get('likes', 0)
                                daily_data[date_key]['total_retweets'] += post.get('retweets', 0)
                                daily_data[date_key]['total_replies'] += post.get('replies', 0)
                                daily_data[date_key]['total_bookmarks'] += post.get('bookmarks', 0)
                                daily_data[date_key]['total_engagement'] += (
                                    post.get('likes', 0) + 
                                    post.get('retweets', 0) + 
                                    post.get('replies', 0) + 
                                    post.get('bookmarks', 0)
                                )
                    except Exception as e:
                        date_parse_errors += 1
                        logger.debug(f"Error processing post date: {e}")

            logger.info(f"Processed {posts_processed} total posts")
            logger.info(f"Posts within {cutoff_date.strftime('%Y-%m-%d')} cutoff: {posts_within_cutoff}")
            logger.info(f"Date parse errors: {date_parse_errors}")
            logger.info(f"Unique days with posts: {len(daily_data)}")

            # Log date range if we have data
            if daily_data:
                sorted_dates = sorted(daily_data.keys())
                logger.info(f"Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
                logger.info(f"Days with posts: {', '.join(sorted_dates)}")
            
            # Calculate engagement rates and averages
            for date_key, data in daily_data.items():
                if data['total_views'] > 0:
                    data['engagement_rate'] = (data['total_engagement'] / data['total_views']) * 100
                else:
                    data['engagement_rate'] = 0
                
                if data['posts_count'] > 0:
                    data['avg_views_per_post'] = data['total_views'] / data['posts_count']
                    data['avg_engagement_per_post'] = data['total_engagement'] / data['posts_count']
                else:
                    data['avg_views_per_post'] = 0
                    data['avg_engagement_per_post'] = 0
            
            # Store daily metrics
            daily_metrics_ref = self.db.collection('users').document(self.user_id).collection('x_analytics').document('daily_metrics')
            daily_metrics_ref.set({
                'last_updated': datetime.now().isoformat(),
                'metrics': daily_data
            })
            
            logger.info(f"Calculated and stored daily metrics for {len(daily_data)} days")
            
        except Exception as e:
            logger.error(f"Error calculating daily metrics: {str(e)}")
    
    def _store_posts(self, posts):
        """Store all posts in Firebase subcollection (backward compatibility)"""
        try:
            # Ensure we're only storing non-retweets
            filtered_posts = [post for post in posts if not post.get('retweeted', False)]
            logger.info(f"Storing {len(filtered_posts)} non-retweet posts in timeline document")
            
            # Prepare posts with essential data
            processed_posts = []
            for post in filtered_posts[:100]:  # Limit to 100 posts
                # Extract media URL if available
                media_url = self._extract_media_url(post)
                
                # Get the complete text - preserve as-is from API
                post_text = post.get('text', '')
                
                # Create post data with all required fields
                post_data = {
                    'id': post.get('tweet_id') or post.get('id_str') or post.get('id', ''),
                    'text': post_text,  # Raw text with all formatting preserved
                    'created_at': post.get('created_at', ''),
                    'views': self._parse_count_value(post.get('views')),
                    'likes': self._parse_count_value(post.get('favorites')),
                    'retweets': self._parse_count_value(post.get('retweets')) or self._parse_count_value(post.get('retweet_count')),
                    'replies': self._parse_count_value(post.get('reply_count') or post.get('replies')),
                    'bookmarks': self._parse_count_value(post.get('bookmarks')),
                    'media_url': media_url,
                }
                processed_posts.append(post_data)
            
            # Store all posts in one document in subcollection
            posts_doc = {
                'user_id': self.user_id,
                'timestamp': datetime.now().isoformat(),
                'posts': processed_posts
            }
            
            # Store with fixed name 'timeline'
            posts_ref = self.db.collection('users').document(self.user_id).collection('x_posts').document('timeline')
            posts_ref.set(posts_doc)
            
            logger.info(f"Stored {len(processed_posts)} posts in timeline document for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error storing posts in Firebase: {str(e)}")
    
    def _store_replies(self, replies):
        """Store replies data in Firebase subcollection"""
        try:
            if not replies:
                logger.warning(f"No replies to store for user {self.user_id}")
                return
                
            logger.info(f"Storing {len(replies)} replies")
            
            # Prepare replies data
            replies_doc = {
                'user_id': self.user_id,
                'timestamp': datetime.now().isoformat(),
                'screen_name': self.x_handle,
                'count': len(replies),
                'replies': replies
            }
            
            # Store with fixed name 'data'
            replies_ref = self.db.collection('users').document(self.user_id).collection('x_replies').document('data')
            replies_ref.set(replies_doc)
            
            logger.info(f"Stored {len(replies)} replies for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error storing replies in Firebase: {str(e)}")
    
    def _extract_essential_post_data(self, post, is_reply=False):
        """Extract only essential data from a post to reduce file size"""
        if not post:
            return {}
            
        # Convert views to int for proper sorting
        views = post.get('views', '0')
        if isinstance(views, dict) and 'count' in views:
            views = views['count']
            
        if views and isinstance(views, str):
            # Remove commas and handle K/M suffixes
            views = views.replace(',', '')
            if 'K' in views:
                try:
                    views = int(float(views.replace('K', '')) * 1000)
                except (ValueError, TypeError):
                    views = 0
            elif 'M' in views:
                try:
                    views = int(float(views.replace('M', '')) * 1000000)
                except (ValueError, TypeError):
                    views = 0
            else:
                try:
                    views = int(views)
                except (ValueError, TypeError):
                    views = 0
            
        # Get text - preserve as-is from API
        text = post.get('text', '')
        
        # Process text if this is a reply
        if is_reply and post.get('in_reply_to_status_id_str') is not None:
            # Strip out handles from the beginning of the text
            text = self._strip_handles(text)
            
        # Fallback ID fields
        tweet_id = post.get('tweet_id') or post.get('id_str')
        in_reply_to_id = post.get('in_reply_to_status_id_str')
        
        # Handle different author structures
        author = post.get('author', {})
        if isinstance(author, dict):
            author_name = author.get('name', '')
            author_screen_name = author.get('screen_name', '')
        else:
            author_name = ''
            author_screen_name = ''
            
        return {
            'id': tweet_id,
            'text': text,
            'created_at': post.get('created_at', ''),
            'views': views,
            'likes': post.get('favorites', post.get('favorite_count', 0)),
            'retweets': post.get('retweets', post.get('retweet_count', 0)),
            'replies': post.get('replies', post.get('reply_count', 0)),
            'in_reply_to_id': in_reply_to_id,
            'author': {
                'name': author_name,
                'screen_name': author_screen_name
            }
        }
    
    def _strip_handles(self, text):
        """Strip @ handles from the beginning of text while preserving newlines and formatting"""
        if not text:
            return ""
        
        # Remove @handles only from the very beginning of the text
        # This pattern matches one or more @username mentions at the start, followed by optional whitespace
        pattern = r'^(@\w+\s*)+\s*'
        cleaned_text = re.sub(pattern, '', text)
        
        return cleaned_text.strip()
    
    def refresh_data(self, is_initial=False):
        """Refresh all data from the API and update Firebase"""
        return self.get_analytics_data(is_initial=is_initial)

def fetch_x_analytics(user_id, is_initial=False):
    """
    Fetch X analytics data for a user
    Args:
        user_id: The user ID
        is_initial: Whether this is the initial fetch (for 6 months of data)
    """
    analytics = XAnalytics(user_id)
    return analytics.get_analytics_data(is_initial=is_initial)

def clean_user_data(user_id):
    """Clean all X analytics data for a user when they disconnect their account"""
    try:
        logger.info(f"Cleaning X analytics data for user {user_id}")
        
        # Initialize Firestore DB if not already initialized
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                # App already initialized
                pass
        
        # Get Firestore client
        db = firestore.client()
        
        deleted_count = 0
        
        # Delete the latest analytics document
        logger.info(f"Deleting X analytics data for user {user_id}")
        latest_ref = db.collection('users').document(user_id).collection('x_analytics').document('latest')
        if latest_ref.get().exists:
            latest_ref.delete()
            deleted_count += 1
            logger.debug(f"Deleted analytics document: latest")
        
        # Delete historical data
        history_collection = db.collection('users').document(user_id).collection('x_analytics').document('history').collection('daily')
        history_docs = history_collection.stream()
        for doc in history_docs:
            doc.reference.delete()
            deleted_count += 1
        
        # Delete the specific posts document
        logger.info(f"Deleting X posts data for user {user_id}")
        posts_ref = db.collection('users').document(user_id).collection('x_posts').document('timeline')
        if posts_ref.get().exists:
            posts_ref.delete()
            deleted_count += 1
            logger.debug(f"Deleted posts document: timeline")
        
        # Delete individual posts
        posts_collection = db.collection('users').document(user_id).collection('x_posts_individual')
        posts_docs = posts_collection.stream()
        for doc in posts_docs:
            doc.reference.delete()
            deleted_count += 1
        
        # Delete daily metrics
        daily_metrics_ref = db.collection('users').document(user_id).collection('x_analytics').document('daily_metrics')
        if daily_metrics_ref.get().exists:
            daily_metrics_ref.delete()
            deleted_count += 1
        
        # Delete the specific replies document
        logger.info(f"Deleting X replies data for user {user_id}")
        replies_ref = db.collection('users').document(user_id).collection('x_replies').document('data')
        if replies_ref.get().exists:
            replies_ref.delete()
            deleted_count += 1
            logger.debug(f"Deleted replies document: data")
        
        logger.info(f"Successfully cleaned X analytics data for user {user_id} - deleted {deleted_count} documents")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning user data: {str(e)}")
        return False

def get_users_with_x():
    """Get all user IDs who have X connected"""
    try:
        # Initialize Firestore if needed
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        db = firestore.client()
        users_collection = db.collection('users')
        
        # Query users where x_account field exists and is not empty
        query = users_collection.where('x_account', '!=', '').where('x_account', '!=', None)
        
        # Execute query and get user IDs
        docs = query.stream()
        user_ids = [doc.id for doc in docs]
        
        logger.info(f"Found {len(user_ids)} users with X connected")
        return user_ids
        
    except Exception as e:
        logger.error(f"Error querying users with X: {str(e)}")
        return []