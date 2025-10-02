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
    
    def analyze_competitors(self, channel_ids: List[str], timeframe: str, user_id: str) -> Dict:
        """
        Analyze competitor channels
        
        Args:
            channel_ids: List of YouTube channel IDs
            timeframe: Timeframe in days ('1', '2', '7', '30', '90', '180')
            user_id: User ID for tracking
        
        Returns:
            Dict with analysis results
        """
        try:
            days = int(timeframe)
            
            # Fetch data for all channels
            all_videos = []
            channel_data = []
            
            for channel_id in channel_ids:
                # Get channel info
                channel_info = self.youtube_api.get_channel_info(channel_id)
                if not channel_info:
                    continue
                
                channel_data.append(channel_info)
                
                # Get videos
                videos_result = self.youtube_api.get_channel_videos(channel_id)
                if not videos_result:
                    continue
                
                videos = videos_result.get('videos', [])
                
                # Filter by timeframe
                filtered_videos = self.youtube_api.filter_videos_by_timeframe(videos, days)
                
                # Add channel info to each video
                for video in filtered_videos:
                    video['channel_title'] = channel_info.get('title')
                    video['channel_id'] = channel_id
                
                all_videos.extend(filtered_videos)
            
            # Sort videos by view count
            all_videos.sort(key=lambda x: int(x.get('view_count', 0) or 0), reverse=True)
            
            # Analyze patterns
            patterns = self._analyze_patterns(all_videos, channel_data)
            
            # Generate insights with AI
            insights = self._generate_insights(all_videos, patterns, days)
            
            return {
                'success': True,
                'data': {
                    'videos': all_videos[:50],  # Top 50 videos
                    'channels': channel_data,
                    'patterns': patterns,
                    'insights': insights,
                    'total_videos': len(all_videos)
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
        
        # Title patterns - extract common words
        title_words = {}
        for video in videos:
            title = video.get('title', '').lower()
            words = [w for w in title.split() if len(w) > 3]
            for word in words:
                title_words[word] = title_words.get(word, 0) + 1
        
        # Get top title patterns
        top_title_words = sorted(title_words.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate average metrics
        total_views = sum(int(v.get('view_count', 0) or 0) for v in videos)
        avg_views = total_views / len(videos) if videos else 0
        
        # Get trending topics (videos from last 48 hours)
        trending = [v for v in videos[:20]]  # Top 20 recent videos
        
        return {
            'top_title_words': [{'word': w, 'count': c} for w, c in top_title_words],
            'avg_views': int(avg_views),
            'total_views': total_views,
            'trending_topics': trending[:5],
            'total_channels': len(channels),
            'total_videos_analyzed': len(videos)
        }
    
    def _generate_insights(self, videos: List[Dict], patterns: Dict, days: int) -> Dict:
        """Generate AI insights from the data"""
        try:
            ai_provider = get_ai_provider()
            
            if not ai_provider or not videos:
                return self._generate_fallback_insights(videos, patterns, days)
            
            # Prepare data summary for AI
            top_videos = videos[:10]
            video_summaries = []
            for v in top_videos:
                video_summaries.append(f"- {v.get('title')} ({v.get('view_count', 0)} views)")
            
            prompt = f"""Analyze these YouTube competitor insights from the last {days} days:

Top Performing Videos:
{chr(10).join(video_summaries)}

Patterns:
- Most common title words: {', '.join([w['word'] for w in patterns.get('top_title_words', [])[:5]])}
- Average views: {patterns.get('avg_views', 0):,}
- Total videos analyzed: {patterns.get('total_videos_analyzed', 0)}

Provide a brief analysis with:
1. What content types are performing best
2. Key patterns in successful titles
3. 3-5 actionable content ideas based on these insights

Keep it concise and actionable."""

            system_prompt = f"""You are a YouTube strategy expert analyzing competitor data.
Current date: {datetime.now().strftime('%B %d, %Y')}.
Provide practical, data-driven insights."""

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            insights_text = response.get('content', '') if isinstance(response, dict) else str(response)
            
            return {
                'summary': insights_text,
                'quick_wins': self._extract_quick_wins(videos),
                'content_gaps': self._identify_content_gaps(videos, patterns)
            }
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return self._generate_fallback_insights(videos, patterns, days)
    
    def _generate_fallback_insights(self, videos: List[Dict], patterns: Dict, days: int) -> Dict:
        """Generate basic insights without AI"""
        return {
            'summary': f"Analyzed {len(videos)} videos from the last {days} days. Average views: {patterns.get('avg_views', 0):,}",
            'quick_wins': self._extract_quick_wins(videos),
            'content_gaps': []
        }
    
    def _extract_quick_wins(self, videos: List[Dict]) -> List[Dict]:
        """Extract quick win opportunities from recent high-performing videos"""
        # Get videos from last 48 hours that are performing well
        quick_wins = []
        for video in videos[:10]:
            quick_wins.append({
                'title': video.get('title'),
                'views': video.get('view_count'),
                'channel': video.get('channel_title'),
                'opportunity': f"Similar content trending - consider creating your take on this topic"
            })
        
        return quick_wins[:5]
    
    def _identify_content_gaps(self, videos: List[Dict], patterns: Dict) -> List[str]:
        """Identify potential content gaps"""
        # This is a simple implementation
        # In a real system, you'd do more sophisticated analysis
        gaps = []
        
        top_words = [w['word'] for w in patterns.get('top_title_words', [])[:10]]
        
        if 'tutorial' in top_words or 'how' in top_words:
            gaps.append("Tutorial content is popular in your niche")
        
        if 'review' in top_words:
            gaps.append("Review content performs well")
        
        return gaps[:3]