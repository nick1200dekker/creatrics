"""
TikTok Trend Analyzer
Analyzes TikTok videos to identify trending keywords based on viral potential
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
import statistics

logger = logging.getLogger(__name__)


class TikTokTrendAnalyzer:
    """
    Analyzes TikTok search results for trending content
    Calculates viral potential based on:
    - Video recency (how old the video is)
    - View count (engagement level)
    - Engagement ratios (likes, shares, comments)
    """

    def __init__(self):
        self.current_time = int(datetime.now().timestamp())

    def calculate_video_age_hours(self, create_time: int) -> float:
        """Calculate video age in hours from unix timestamp"""
        try:
            age_seconds = self.current_time - create_time
            age_hours = age_seconds / 3600
            return round(age_hours, 1)
        except Exception as e:
            logger.error(f"Error calculating video age: {e}")
            return 0

    def calculate_viral_potential(self, video: dict) -> int:
        """
        Calculate viral potential score (0-100) based on:
        1. Video recency (newer = better)
        2. View velocity (views per hour)
        3. Engagement rate

        Returns integer score from 0-100
        """
        try:
            # Extract data
            create_time = video.get('createTime', 0)
            views = video.get('playCount', 0)
            likes = video.get('diggCount', 0)
            shares = video.get('shareCount', 0)
            comments = video.get('commentCount', 0)

            # Calculate age in hours
            age_hours = self.calculate_video_age_hours(create_time)

            if age_hours == 0 or views == 0:
                return 0

            # 1. RECENCY SCORE (0-40 points)
            # Ideal window: 0-72 hours (3 days)
            if age_hours <= 24:  # Less than 1 day
                recency_score = 40
            elif age_hours <= 48:  # 1-2 days
                recency_score = 35
            elif age_hours <= 72:  # 2-3 days
                recency_score = 30
            elif age_hours <= 168:  # 3-7 days
                recency_score = 20
            elif age_hours <= 336:  # 7-14 days
                recency_score = 10
            else:  # Older than 14 days
                recency_score = 5

            # 2. VIEW VELOCITY SCORE (0-40 points)
            # Calculate views per hour
            views_per_hour = views / age_hours if age_hours > 0 else 0

            # Scoring tiers based on views per hour
            if views_per_hour >= 50000:  # 50K+ views/hour = viral
                velocity_score = 40
            elif views_per_hour >= 20000:  # 20K-50K views/hour = high potential
                velocity_score = 35
            elif views_per_hour >= 10000:  # 10K-20K views/hour = strong
                velocity_score = 30
            elif views_per_hour >= 5000:   # 5K-10K views/hour = good
                velocity_score = 25
            elif views_per_hour >= 2000:   # 2K-5K views/hour = moderate
                velocity_score = 20
            elif views_per_hour >= 1000:   # 1K-2K views/hour = emerging
                velocity_score = 15
            elif views_per_hour >= 500:    # 500-1K views/hour = early
                velocity_score = 10
            else:                           # < 500 views/hour
                velocity_score = 5

            # 3. ENGAGEMENT SCORE (0-20 points)
            # Calculate engagement rate (likes + shares + comments) / views
            total_engagement = likes + shares + comments
            engagement_rate = (total_engagement / views) * 100 if views > 0 else 0

            # Scoring based on engagement rate
            if engagement_rate >= 15:  # 15%+ = exceptional
                engagement_score = 20
            elif engagement_rate >= 10:  # 10-15% = very good
                engagement_score = 17
            elif engagement_rate >= 7:   # 7-10% = good
                engagement_score = 14
            elif engagement_rate >= 5:   # 5-7% = average
                engagement_score = 10
            elif engagement_rate >= 3:   # 3-5% = below average
                engagement_score = 6
            else:                        # < 3% = low
                engagement_score = 3

            # Calculate total viral potential
            viral_potential = int(recency_score + velocity_score + engagement_score)

            return min(100, viral_potential)  # Cap at 100

        except Exception as e:
            logger.error(f"Error calculating viral potential: {e}")
            return 0

    def determine_trend_status(self, viral_potential: int, age_hours: float) -> str:
        """
        Determine trend status based on viral potential and age
        Returns: 'emerging', 'trending', 'viral', 'mature'
        """
        if age_hours <= 48:  # Less than 2 days
            if viral_potential >= 80:
                return 'viral'
            elif viral_potential >= 65:
                return 'trending'
            else:
                return 'emerging'
        elif age_hours <= 168:  # 2-7 days
            if viral_potential >= 75:
                return 'trending'
            else:
                return 'mature'
        else:  # Older than 7 days
            return 'mature'

    def analyze_videos(self, videos: List[dict]) -> Dict:
        """
        Analyze a list of TikTok videos and return trend analysis

        Args:
            videos: List of video dicts from TikTok API (item_list format)

        Returns:
            Dict with analysis results including:
            - analyzed_videos: List of videos with viral scores
            - total_videos: Total count
            - avg_viral_potential: Average score
            - trend_summary: Overall trend assessment
        """
        analyzed_videos = []
        viral_scores = []
        seen_video_ids = set()  # Track video IDs to avoid duplicates

        duplicate_count = 0
        zero_view_count = 0

        for video_data in videos:
            try:
                # Handle both formats: direct item or wrapped in item key
                if 'item' in video_data:
                    video = video_data['item']
                else:
                    video = video_data

                # Get video ID and check for duplicates
                video_id = video.get('id')
                if not video_id:
                    continue

                if video_id in seen_video_ids:
                    duplicate_count += 1
                    continue  # Skip duplicates

                seen_video_ids.add(video_id)

                # Extract stats
                stats = video.get('stats', {})

                # Filter out invalid videos with 0 views
                if stats.get('playCount', 0) == 0:
                    zero_view_count += 1
                    continue

                # Build analyzed video object
                create_time = video.get('createTime', 0)
                age_hours = self.calculate_video_age_hours(create_time)

                video_info = {
                    'id': video.get('id'),
                    'desc': video.get('desc', ''),
                    'createTime': create_time,
                    'age_hours': age_hours,
                    'age_display': self.format_age_display(age_hours),
                    'playCount': stats.get('playCount', 0),
                    'diggCount': stats.get('diggCount', 0),
                    'shareCount': stats.get('shareCount', 0),
                    'commentCount': stats.get('commentCount', 0),
                    'collectCount': stats.get('collectCount', 0),
                    'author': {
                        'uniqueId': video.get('author', {}).get('uniqueId', ''),
                        'nickname': video.get('author', {}).get('nickname', ''),
                    },
                    'video': {
                        'cover': video.get('video', {}).get('cover', ''),
                        'playAddr': video.get('video', {}).get('playAddr', ''),
                        'duration': video.get('video', {}).get('duration', 0)
                    },
                    'challenges': [
                        {'title': c.get('title', ''), 'id': c.get('id', '')}
                        for c in video.get('challenges', [])
                    ]
                }

                # Calculate viral potential
                video_info['viral_potential'] = self.calculate_viral_potential(stats)
                video_info['trend_status'] = self.determine_trend_status(
                    video_info['viral_potential'],
                    age_hours
                )

                # Calculate engagement rate
                total_eng = stats.get('diggCount', 0) + stats.get('shareCount', 0) + stats.get('commentCount', 0)
                views = stats.get('playCount', 0)
                video_info['engagement_rate'] = round((total_eng / views * 100), 2) if views > 0 else 0

                # Calculate views per hour
                video_info['views_per_hour'] = int(views / age_hours) if age_hours > 0 else 0

                analyzed_videos.append(video_info)
                viral_scores.append(video_info['viral_potential'])

            except Exception as e:
                logger.error(f"Error analyzing video: {e}")
                continue

        # Log filtering statistics
        logger.info(f"Filtering stats - Duplicates: {duplicate_count}, Zero views: {zero_view_count}, Kept: {len(analyzed_videos)}")

        # Sort by viral potential (highest first)
        analyzed_videos.sort(key=lambda x: x['viral_potential'], reverse=True)

        # Calculate summary statistics
        avg_viral_potential = int(statistics.mean(viral_scores)) if viral_scores else 0
        median_viral_potential = int(statistics.median(viral_scores)) if viral_scores else 0

        # Count by trend status
        status_counts = {
            'viral': sum(1 for v in analyzed_videos if v['trend_status'] == 'viral'),
            'trending': sum(1 for v in analyzed_videos if v['trend_status'] == 'trending'),
            'emerging': sum(1 for v in analyzed_videos if v['trend_status'] == 'emerging'),
            'mature': sum(1 for v in analyzed_videos if v['trend_status'] == 'mature')
        }

        # Determine overall trend assessment
        if status_counts['viral'] >= 3:
            trend_summary = 'High viral activity - Multiple videos are exploding right now!'
        elif status_counts['trending'] >= 5:
            trend_summary = 'Strong trending momentum - This topic is hot!'
        elif status_counts['emerging'] >= 5:
            trend_summary = 'Emerging trend - Early stage with potential'
        else:
            trend_summary = 'Established topic - Steady but mature content'

        return {
            'analyzed_videos': analyzed_videos,
            'total_videos': len(analyzed_videos),
            'avg_viral_potential': avg_viral_potential,
            'median_viral_potential': median_viral_potential,
            'status_counts': status_counts,
            'trend_summary': trend_summary,
            'top_hashtags': self.extract_top_hashtags(analyzed_videos),
            'analyzed_at': datetime.now().isoformat()
        }

    def format_age_display(self, age_hours: float) -> str:
        """Format age in human-readable format"""
        if age_hours < 1:
            return f"{int(age_hours * 60)}m ago"
        elif age_hours < 24:
            return f"{int(age_hours)}h ago"
        else:
            days = int(age_hours / 24)
            return f"{days}d ago"

    def extract_top_hashtags(self, videos: List[dict], limit: int = 10) -> List[Dict]:
        """Extract and count most common hashtags across videos"""
        hashtag_counts = {}

        for video in videos:
            for challenge in video.get('challenges', []):
                tag = challenge.get('title', '').lower()
                if tag:
                    if tag in hashtag_counts:
                        hashtag_counts[tag]['count'] += 1
                    else:
                        hashtag_counts[tag] = {
                            'title': tag,
                            'count': 1,
                            'id': challenge.get('id', '')
                        }

        # Sort by count and return top N
        sorted_tags = sorted(hashtag_counts.values(), key=lambda x: x['count'], reverse=True)
        return sorted_tags[:limit]
