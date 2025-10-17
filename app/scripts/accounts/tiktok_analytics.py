# File: app/scripts/accounts/tiktok_analytics.py

"""
TikTok Analytics fetch utility for cron jobs
Based on the refresh logic from analytics_routes.py
"""

import logging
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timedelta
from app.system.services.user_service import UserService
from app.system.services.tiktok_service import TikTokService

logger = logging.getLogger('tiktok_analytics')

def fetch_tiktok_analytics(user_id):
    """
    Fetch and update TikTok analytics for a user
    Called by cron job to refresh analytics daily

    Args:
        user_id (str): User ID to fetch analytics for
    """
    try:
        user_data = UserService.get_user(user_id)
        tiktok_username = user_data.get('tiktok_account', '')
        sec_uid = user_data.get('tiktok_sec_uid', '')

        if not tiktok_username:
            logger.warning(f"No TikTok account connected for user {user_id}")
            return

        logger.info(f"Fetching TikTok analytics for user {user_id}")

        # Fetch fresh user data
        user_info = TikTokService.get_user_info(tiktok_username)

        if not user_info:
            logger.warning(f"TikTok API unavailable for user {user_id} - possibly rate limited")
            return

        # Store secUid
        sec_uid = user_info.get('sec_uid')
        UserService.update_user(user_id, {'tiktok_sec_uid': sec_uid})

        # Fetch posts with pagination
        # IMPORTANT: TikTok API returns OLD videos first with cursor="0"
        # We need to go through ALL available cursors to reach recent videos
        # Then filter by date at the end
        seven_days_ago = datetime.now() - timedelta(days=7)
        all_posts = []
        cursor = "0"
        max_pages = 30
        page = 0

        logger.info(f"Fetching all TikTok posts (API returns oldest first, need all pages for recent posts)")

        while page < max_pages:
            page += 1

            # Retry logic for API calls
            posts_data = None
            max_retries = 3
            for retry in range(max_retries):
                posts_data = TikTokService.get_user_posts(sec_uid, count=35, cursor=cursor)

                if posts_data:
                    break

                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 3  # 3s, 6s, 9s
                    logger.warning(f"Failed to fetch page {page}, retrying in {wait_time}s (attempt {retry + 1}/{max_retries})")
                    import time
                    time.sleep(wait_time)

            if not posts_data:
                logger.warning(f"Failed to fetch posts after {max_retries} retries, stopping pagination at page {page}")
                break

            posts = posts_data.get('posts', [])
            logger.info(f"Page {page}: Got {len(posts)} posts from API")

            # Add all posts - will filter by date later
            all_posts.extend(posts)

            # Check if we have more pages
            has_more = posts_data.get('has_more', False)
            if not has_more or not posts_data.get('cursor'):
                logger.info(f"No more pages available")
                break

            cursor = posts_data.get('cursor')

            # Add delay between pages to avoid rate limiting
            import time
            time.sleep(2)

        logger.info(f"Completed pagination: Fetched {len(all_posts)} total posts")

        # Filter to only posts from last 7 days
        posts_before_filter = len(all_posts)
        recent_posts = []
        for post in all_posts:
            create_time = post.get('create_time')
            if create_time:
                try:
                    post_date = datetime.fromtimestamp(create_time)
                    if post_date >= seven_days_ago:
                        recent_posts.append(post)
                except Exception as e:
                    logger.error(f"Error parsing post date: {e}")
                    recent_posts.append(post)
            else:
                recent_posts.append(post)

        logger.info(f"Filtered to last 7 days: {posts_before_filter} total -> {len(recent_posts)} recent posts")

        # Initialize Firestore if needed
        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app()
            except ValueError:
                pass

        db = firestore.client()

        # Get existing posts from Firestore
        posts_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('posts')
        posts_doc = posts_ref.get()

        existing_posts = []
        if posts_doc.exists:
            existing_posts = posts_doc.to_dict().get('posts', [])

        # Merge new posts with existing posts (deduplicate by ID)
        all_post_ids = set()
        all_posts = []

        for post in recent_posts + existing_posts:
            post_id = post.get('id')
            if post_id and post_id not in all_post_ids:
                all_post_ids.add(post_id)
                all_posts.append(post)

        # Sort by create_time (newest first)
        all_posts.sort(key=lambda x: x.get('create_time', 0), reverse=True)

        # Remove posts older than 6 months
        six_months_ago = datetime.now() - timedelta(days=180)
        posts_before_cleanup = len(all_posts)
        all_posts = [post for post in all_posts if datetime.fromtimestamp(post.get('create_time', 0)) >= six_months_ago]
        posts_deleted = posts_before_cleanup - len(all_posts)

        if posts_deleted > 0:
            logger.info(f"Cleaned up {posts_deleted} TikTok posts older than 6 months")

        # Calculate metrics from last 35 posts
        last_35_posts = all_posts[:35]
        engagement_rate = 0
        total_views_35 = 0
        total_likes_35 = 0
        total_comments_35 = 0
        total_shares_35 = 0
        posts_count = 0

        if last_35_posts:
            posts_count = len(last_35_posts)
            for post in last_35_posts:
                views = post.get('views', 0)
                likes = post.get('likes', 0)
                comments = post.get('comments', 0)
                shares = post.get('shares', 0)

                total_views_35 += views
                total_likes_35 += likes
                total_comments_35 += comments
                total_shares_35 += shares

            # Calculate engagement rate
            if total_views_35 > 0:
                total_engagement = total_likes_35 + total_comments_35 + total_shares_35
                engagement_rate = (total_engagement / total_views_35) * 100

        # Add calculated metrics to user info
        user_info['engagement_rate'] = round(engagement_rate, 2)
        user_info['avg_views_35'] = round(total_views_35 / posts_count, 0) if posts_count > 0 else 0
        user_info['avg_likes_35'] = round(total_likes_35 / posts_count, 0) if posts_count > 0 else 0
        user_info['avg_comments_35'] = round(total_comments_35 / posts_count, 0) if posts_count > 0 else 0
        user_info['avg_shares_35'] = round(total_shares_35 / posts_count, 0) if posts_count > 0 else 0
        user_info['total_views_35'] = total_views_35
        user_info['total_likes_35'] = total_likes_35
        user_info['total_comments_35'] = total_comments_35
        user_info['total_shares_35'] = total_shares_35
        user_info['post_count'] = len(last_35_posts)
        user_info['fetched_at'] = datetime.now().isoformat()

        # Store updated overview data in Firestore
        tiktok_ref = db.collection('users').document(user_id).collection('tiktok_analytics').document('latest')
        tiktok_ref.set(user_info)

        # Store updated posts data in Firestore
        posts_ref.set({
            'posts': all_posts,
            'has_more': False,
            'fetched_at': datetime.now().isoformat(),
            'total_posts': len(all_posts)
        })

        logger.info(f"TikTok analytics fetch completed successfully for user {user_id}")

    except Exception as e:
        logger.error(f"Error fetching TikTok analytics for user {user_id}: {str(e)}")
        raise
