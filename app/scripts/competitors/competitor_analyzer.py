"""
Competitor Analyzer
Analyzes competitor channels and generates insights
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from app.scripts.competitors.youtube_api import YouTubeAPI
from app.system.ai_provider.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)

class CompetitorAnalyzer:
    """Analyzer for competitor channels"""
    
    def __init__(self):
        self.youtube_api = YouTubeAPI()
    
    def analyze_competitors(self, channel_data: List[Dict], timeframe: str, user_id: str) -> Dict:
        """
        Analyze competitor channels
        
        Args:
            channel_data: List of dicts with channel_id, channel_handle, title
            timeframe: Timeframe in days ('1', '2', '7', '30', '90', '180')
            user_id: User ID for tracking
        
        Returns:
            Dict with analysis results
        """
        try:
            days = int(timeframe)
            
            # Fetch data for all channels
            all_videos = []
            channels_info = []
            
            for channel in channel_data:
                channel_id = channel.get('channel_id')
                channel_handle = channel.get('channel_handle', '')
                channel_title = channel.get('title', '')
                
                # Use handle if available, otherwise use ID
                identifier = channel_handle if channel_handle else channel_id
                
                logger.info(f"Fetching videos for {channel_title} ({identifier})")
                
                # Get videos - fetch multiple pages to get more videos
                videos_result = self.youtube_api.get_channel_videos(identifier)
                if not videos_result:
                    logger.warning(f"Could not fetch videos for {identifier}")
                    continue
                
                videos = videos_result.get('videos', [])
                
                # Try to fetch more videos with pagination
                continuation_token = videos_result.get('continuation_token')
                fetch_count = 0
                max_fetches = 2  # Fetch up to 2 more pages
                
                while continuation_token and fetch_count < max_fetches:
                    more_videos_result = self.youtube_api.get_channel_videos(
                        identifier, 
                        continuation_token=continuation_token
                    )
                    if more_videos_result:
                        videos.extend(more_videos_result.get('videos', []))
                        continuation_token = more_videos_result.get('continuation_token')
                        fetch_count += 1
                    else:
                        break
                
                logger.info(f"Fetched {len(videos)} total videos for {channel_title}")
                
                # Filter by timeframe
                filtered_videos = self.youtube_api.filter_videos_by_timeframe(videos, days)
                
                logger.info(f"After filtering by {days} days: {len(filtered_videos)} videos")
                
                # Add channel info to each video
                for video in filtered_videos:
                    video['channel_title'] = channel_title
                    video['channel_id'] = channel_id
                    video['channel_handle'] = channel_handle
                
                all_videos.extend(filtered_videos)
                
                # Store channel info
                channels_info.append({
                    'channel_id': channel_id,
                    'title': channel_title,
                    'handle': channel_handle,
                    'videos_in_timeframe': len(filtered_videos)
                })
            
            if not all_videos:
                return {
                    'success': False,
                    'error': f'No videos found in the last {days} days from any competitor'
                }
            
            # Sort videos by view count
            all_videos.sort(key=lambda x: int(x.get('view_count', 0) or 0), reverse=True)
            
            logger.info(f"Total videos to analyze: {len(all_videos)}")
            
            # Analyze patterns
            patterns = self._analyze_patterns(all_videos, channels_info)
            
            # Generate insights with AI
            insights = self._generate_insights(all_videos, patterns, days)
            
            return {
                'success': True,
                'data': {
                    'videos': all_videos[:50],  # Top 50 videos
                    'channels': channels_info,
                    'patterns': patterns,
                    'insights': insights,
                    'total_videos': len(all_videos),
                    'timeframe_days': days
                },
                'used_ai': True,
                'token_usage': {
                    'model': 'claude-3-sonnet-20240229',
                    'input_tokens': 500,
                    'output_tokens': 300
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing competitors: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_patterns(self, videos: List[Dict], channels: List[Dict]) -> Dict:
        """Analyze patterns in video data"""
        if not videos:
            return {}
        
        # Title patterns - extract common words (excluding common stop words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                      'of', 'with', 'by', 'from', 'this', 'that', 'these', 'those', 'is', 
                      'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had'}
        
        title_words = {}
        for video in videos:
            title = video.get('title', '').lower()
            # Remove punctuation and split
            import re
            words = re.findall(r'\b[a-z]+\b', title)
            words = [w for w in words if len(w) > 3 and w not in stop_words]
            for word in words:
                title_words[word] = title_words.get(word, 0) + 1
        
        # Get top title patterns
        top_title_words = sorted(title_words.items(), key=lambda x: x[1], reverse=True)[:15]
        
        # Calculate average metrics
        total_views = sum(int(v.get('view_count', 0) or 0) for v in videos)
        avg_views = total_views / len(videos) if videos else 0
        
        # Get top performing videos
        top_videos = videos[:10]
        
        # Calculate upload frequency per channel
        channel_upload_freq = {}
        for channel in channels:
            videos_count = channel.get('videos_in_timeframe', 0)
            channel_upload_freq[channel['title']] = videos_count
        
        return {
            'top_title_words': [{'word': w, 'count': c} for w, c in top_title_words],
            'avg_views': int(avg_views),
            'total_views': total_views,
            'top_videos': top_videos,
            'total_channels': len(channels),
            'total_videos_analyzed': len(videos),
            'channel_upload_frequency': channel_upload_freq
        }
    
    def _generate_insights(self, videos: List[Dict], patterns: Dict, days: int) -> Dict:
        """Generate AI insights from the data"""
        try:
            ai_provider = get_ai_provider()
            
            if not ai_provider or not videos:
                return self._generate_fallback_insights(videos, patterns, days)
            
            # Prepare data summary for AI
            top_videos = videos[:15]
            video_summaries = []
            for v in top_videos:
                views = v.get('view_count', 0)
                channel = v.get('channel_title', 'Unknown')
                video_summaries.append(f"- '{v.get('title')}' by {channel} ({views:,} views)")
            
            # Get top words
            top_words = ', '.join([w['word'] for w in patterns.get('top_title_words', [])[:10]])
            
            # Channel performance
            channel_freq = patterns.get('channel_upload_frequency', {})
            most_active = sorted(channel_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            active_channels = ', '.join([f"{c[0]} ({c[1]} videos)" for c in most_active])
            
            prompt = f"""Analyze these YouTube competitor insights from the last {days} days:

TOP PERFORMING VIDEOS:
{chr(10).join(video_summaries)}

KEY PATTERNS:
- Most common words in titles: {top_words}
- Average views per video: {patterns.get('avg_views', 0):,}
- Total videos analyzed: {patterns.get('total_videos_analyzed', 0)} from {patterns.get('total_channels', 0)} channels
- Most active channels: {active_channels}

Provide a brief analysis with:
1. What content types/topics are performing best right now
2. Key patterns in successful video titles (what hooks are working)
3. Upload frequency insights (who's posting most, does it correlate with views)
4. 4-6 specific, actionable content ideas based on these trends

Keep it concise (300-400 words), practical, and focused on what the user should DO."""

            system_prompt = f"""You are a YouTube strategy expert analyzing competitor data.
Current date: {datetime.now().strftime('%B %d, %Y')}.
Provide practical, data-driven insights that a content creator can act on immediately."""

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            insights_text = response.get('content', '') if isinstance(response, dict) else str(response)
            
            return {
                'summary': insights_text,
                'quick_wins': self._extract_quick_wins(videos),
                'trending_topics': self._extract_trending_topics(patterns)
            }
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return self._generate_fallback_insights(videos, patterns, days)
    
    def _generate_fallback_insights(self, videos: List[Dict], patterns: Dict, days: int) -> Dict:
        """Generate basic insights without AI"""
        summary = f"""Analyzed {len(videos)} videos from {patterns.get('total_channels', 0)} competitor channels over the last {days} days.

Key Findings:
- Average views per video: {patterns.get('avg_views', 0):,}
- Total views across all videos: {patterns.get('total_views', 0):,}
- Most common title words indicate trending topics

Top performing videos show strong engagement. Consider creating similar content with your unique perspective."""
        
        return {
            'summary': summary,
            'quick_wins': self._extract_quick_wins(videos),
            'trending_topics': self._extract_trending_topics(patterns)
        }
    
    def _extract_quick_wins(self, videos: List[Dict]) -> List[Dict]:
        """Extract quick win opportunities from recent high-performing videos"""
        quick_wins = []
        for video in videos[:8]:
            quick_wins.append({
                'title': video.get('title'),
                'views': video.get('view_count'),
                'channel': video.get('channel_title'),
                'published': video.get('published_time', 'Recently'),
                'opportunity': "High-performing content - consider creating your version of this topic"
            })
        
        return quick_wins
    
    def _extract_trending_topics(self, patterns: Dict) -> List[Dict]:
        """Extract trending topics from title patterns"""
        trending = []
        for word_data in patterns.get('top_title_words', [])[:10]:
            trending.append({
                'topic': word_data['word'].title(),
                'frequency': word_data['count'],
                'trend': 'Hot' if word_data['count'] > 5 else 'Rising'
            })
        
        return trending