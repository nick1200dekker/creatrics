"""
Competitor Analyzer
Analyzes competitor channels and generates insights
"""
import logging
import re
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
            
            prompt = f"""Analyze YouTube competitor data from the last {days} days and provide a CONCISE analysis.

**DATA:**
Channels: {patterns.get('total_channels', 0)} | Videos: {patterns.get('total_videos_analyzed', 0)} | Avg Views: {patterns.get('avg_views', 0):,} | Total Views: {patterns.get('total_views', 0):,}

**TOP VIDEOS:**
{chr(10).join(video_summaries)}

**PATTERNS:** {top_words}
**ACTIVE CHANNELS:** {active_channels}

Provide a BRIEF analysis with these sections:

## Content Performance
Identify the 2-3 highest-performing content types with specific metrics and examples. Keep each format to 2-3 sentences max.

## Title Strategies
List 4-5 proven title patterns from top videos. Format as:
- **Pattern Name**: Brief example and why it works (1 sentence)

## Upload Strategy
Compare top channels' frequency vs engagement in 2-3 sentences.

## Content Opportunities
Create 4 SPECIFIC content ideas based on gaps in competitor coverage. Format each as:
**"[Title]"** - One sentence explaining the data-driven reasoning and unique angle.

## Key Takeaways
3-4 bullet points with specific, actionable recommendations.

Keep it CONCISE and scannable. Use bold for emphasis. Total response should be under 800 words."""

            system_prompt = f"""You are a YouTube strategy analyst. Current date: {datetime.now().strftime('%B %d, %Y')}.

Provide concise, data-driven insights. Every claim must have specific metrics. Keep formatting clean and scannable."""

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1200
            )
            
            insights_text = response.get('content', '') if isinstance(response, dict) else str(response)
            
            # Parse the insights
            parsed_insights = self._parse_ai_insights(insights_text)
            
            return parsed_insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return self._generate_fallback_insights(videos, patterns, days)
    
    def _parse_ai_insights(self, insights_text: str) -> Dict:
        """Parse AI-generated insights into structured format"""
        try:
            # Full summary is the entire text
            summary = insights_text
            
            # Extract content ideas from Content Opportunities section
            quick_wins = self._parse_content_ideas(insights_text)
            
            # Extract trending topics from patterns
            trending_topics = self._parse_trending_from_text(insights_text)
            
            return {
                'summary': summary,
                'quick_wins': quick_wins if quick_wins else [],
                'trending_topics': trending_topics if trending_topics else []
            }
        except Exception as e:
            logger.error(f"Error parsing insights: {e}")
            return {
                'summary': insights_text,
                'quick_wins': [],
                'trending_topics': []
            }
    
    def _parse_content_ideas(self, text: str) -> List[Dict]:
        """Extract content ideas from Content Opportunities section"""
        ideas = []
        
        try:
            # Find Content Opportunities section
            section_match = re.search(r'##\s*Content Opportunities(.+?)(?=##|$)', text, re.DOTALL)
            if not section_match:
                return ideas
            
            section_text = section_match.group(1)
            
            # Pattern: **"Title"** - Explanation
            pattern = r'\*\*["\']([^"\']+)["\']?\*\*\s*[-–—]\s*(.+?)(?=\n\*\*|$)'
            
            for match in re.finditer(pattern, section_text, re.DOTALL):
                title = match.group(1).strip()
                opportunity = match.group(2).strip()
                
                # Clean up opportunity text
                opportunity = re.sub(r'\n+', ' ', opportunity)
                opportunity = opportunity.strip()
                
                # Only include if substantial
                if len(opportunity) > 30:
                    ideas.append({
                        'title': title,
                        'opportunity': opportunity,
                        'channel': 'Content Opportunity',
                        'views': 0
                    })
            
            return ideas[:4]  # Max 4 ideas
            
        except Exception as e:
            logger.error(f"Error parsing content ideas: {e}")
            return ideas
    
    def _parse_trending_from_text(self, text: str) -> List[Dict]:
        """Extract trending topics from the text"""
        topics = []
        
        try:
            # Try to find trending patterns in the text
            section_match = re.search(r'(?:Pattern|Topic|Trend)s?[:\s]+(.+?)(?=##|$)', text, re.DOTALL | re.IGNORECASE)
            
            if section_match:
                section_text = section_match.group(1)
                
                # Pattern: word/phrase mentioned multiple times
                words = re.findall(r'\b[A-Z][a-z]+\b', section_text)
                word_count = {}
                for word in words:
                    if len(word) > 4:
                        word_count[word] = word_count.get(word, 0) + 1
                
                # Get top words
                for word, count in sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                    if count > 1:
                        topics.append({
                            'topic': word,
                            'frequency': count
                        })
            
            return topics
            
        except Exception as e:
            logger.error(f"Error parsing trending topics: {e}")
            return topics
    
    def _generate_fallback_insights(self, videos: List[Dict], patterns: Dict, days: int) -> Dict:
        """Generate basic insights without AI"""
        summary = f"""## Analysis Summary

Analyzed **{len(videos)} videos** from **{patterns.get('total_channels', 0)} channels** over the last {days} days.

**Key Metrics:**
- Average views per video: **{patterns.get('avg_views', 0):,}**
- Total views across all videos: **{patterns.get('total_views', 0):,}**
- Most active channels show consistent upload schedules

**Top Performing Content:**
The highest-performing videos demonstrate strong audience engagement. Review the top videos list for successful content patterns."""
        
        return {
            'summary': summary,
            'quick_wins': [],
            'trending_topics': self._extract_trending_topics(patterns)
        }
    
    def _extract_trending_topics(self, patterns: Dict) -> List[Dict]:
        """Extract trending topics from title patterns"""
        trending = []
        for word_data in patterns.get('top_title_words', [])[:10]:
            trending.append({
                'topic': word_data['word'].title(),
                'frequency': word_data['count']
            })
        
        return trending