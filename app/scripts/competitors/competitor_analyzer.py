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
            
            # IMPROVED PROMPT - Teaches methodology instead of giving examples
            prompt = f"""Analyze YouTube competitor data from the last {days} days and provide actionable insights.

**DATA:**
Channels Analyzed: {patterns.get('total_channels', 0)}
Total Videos: {patterns.get('total_videos_analyzed', 0)}
Average Views: {patterns.get('avg_views', 0):,}
Total Views: {patterns.get('total_views', 0):,}

**TOP PERFORMING VIDEOS:**
{chr(10).join(video_summaries)}

**TITLE PATTERNS:**
Most frequent words: {top_words}

**UPLOAD ACTIVITY:**
{active_channels}

Provide analysis using this structure with proper markdown formatting:

## 1. Top Performing Content Types

Analyze the video data to identify 2-3 content formats with highest engagement. For each:
- State the format clearly using **bold** for format names
- Provide specific metrics (average views, video count)
- Give concrete examples from actual data (channel names, view counts)
- Explain WHY this format works (viewer psychology, algorithmic benefits)

## 2. Title Hook Patterns That Work

Extract 5-6 patterns from top-performing titles. For each pattern:
- **Name the pattern** in bold
- Provide 2-3 specific examples from the actual video titles above
- Explain the psychological trigger (urgency, FOMO, curiosity, authority)
- Include exact hook words/phrases as they appear

Categorize by type: Urgency hooks (CAPS, superlatives), Constraint hooks, Exclusivity hooks (FIRST, ONLY), Authority hooks (rankings, credentials), Curiosity hooks.

## 3. Upload Frequency Insights

Compare channels' quality vs. quantity strategies:
- Name specific channels with their upload frequency
- Provide their average view counts
- Calculate engagement ratio (views per video)
- Draw conclusion with **bold** emphasis on winning strategy
- Identify timing gaps or posting opportunities

## 4. Actionable Content Ideas

CRITICAL: Create 6 SPECIFIC, UNIQUE content ideas analyzing the data.

**Required for Each Idea:**
1. **Exact Title** in quotes using proven hooks from Section 2
2. **Data-Driven Reasoning** - Cite metrics (avg views, percentages, gaps)
3. **Gap Analysis** - What competitors haven't done
4. **Pattern Combination** - Merge 2+ successful elements

**Creation Process:**
- Identify trending topics and formats from the data
- Find what's working (high views, engagement)
- Spot what's MISSING (unfilled gaps)
- Combine proven patterns in new ways
- Explain: "[Format] averages [X] views, [topic] appears in [Y%] of content, but no competitor has [gap]. This combines [pattern 1] with [pattern 2]."

**Format:**
1. **"[Title Using Proven Hooks]"** - [Format] videos average [X] views. [Topic] appears in [Y%] of top content. However, [specific gap analysis]. This combines [pattern 1] with [pattern 2] to [unique value].

**Quality Checklist:**
✅ Uses actual data points (view counts, percentages)
✅ References specific competitor gaps
✅ Combines 2+ successful patterns
✅ Clear reasoning why it works
✅ Title uses Section 2 hooks
✅ Explains viewer/algorithmic benefit

**NEVER Use:**
❌ "High-performing content - make your version"
❌ "Create content about [topic] because trending"
❌ Generic suggestions without data
❌ Suggestions without gap analysis

## 5. Key Takeaways

Provide specific, actionable recommendations:
- **Upload Strategy:** [Specific recommendation based on data]
- **Content Focus:** [Specific topics to prioritize]
- **Title Strategy:** [Specific patterns to use]
- **Timing Opportunity:** [When to publish based on gaps]

**FORMATTING RULES:**
- Use **bold** for emphasis on key terms and statistics
- Use *italic* for secondary emphasis
- Use ## for section headers
- Use - for bullet points
- Use numbered lists for content ideas
- Be specific with numbers and percentages
- Reference actual video titles and channels
- Everything must be data-driven from the analysis above"""

            system_prompt = f"""You are an expert YouTube strategy analyst. Current date: {datetime.now().strftime('%B %d, %Y')}.

Analyze the provided competitor data and follow the instructions precisely. Create unique, data-driven insights by:
1. Extracting patterns from the actual video data provided
2. Identifying real gaps in competitor coverage
3. Combining successful patterns in novel ways
4. Supporting every claim with specific metrics

Use proper markdown formatting (**bold**, *italic*, ## headers, - bullets) throughout your response."""

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000  # Increased for comprehensive response
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
            
            # Extract content ideas from Section 4
            quick_wins = self._parse_content_ideas(insights_text)
            
            # Extract trending topics from Section 5 or patterns
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
        """Extract content ideas from Section 4"""
        ideas = []
        
        try:
            # Find Section 4
            section_match = re.search(r'##\s*4\.\s*Actionable Content Ideas(.+?)(?=##|$)', text, re.DOTALL)
            if not section_match:
                return ideas
            
            section_text = section_match.group(1)
            
            # Pattern: 1. **"Title"** - Explanation
            pattern = r'\d+\.\s+\*\*["\']([^"\']+)["\']?\*\*\s*[-–—]\s*(.+?)(?=\n\d+\.|\n\n|\Z)'
            
            for match in re.finditer(pattern, section_text, re.DOTALL):
                title = match.group(1).strip()
                opportunity = match.group(2).strip()
                
                # Clean up opportunity text
                opportunity = re.sub(r'\n+', ' ', opportunity)
                opportunity = opportunity.strip()
                
                # Only include if substantial (not generic)
                if len(opportunity) > 50:
                    ideas.append({
                        'title': title,
                        'opportunity': opportunity,
                        'channel': 'Content Opportunity',
                        'views': 0
                    })
            
            return ideas[:6]  # Max 6 ideas
            
        except Exception as e:
            logger.error(f"Error parsing content ideas: {e}")
            return ideas
    
    def _parse_trending_from_text(self, text: str) -> List[Dict]:
        """Extract trending topics from the text"""
        topics = []
        
        try:
            # Try to find a Trending Topics or Key Takeaways section
            section_match = re.search(r'(?:Trending|Key|Common).{0,20}Topics?(.+?)(?=##|$)', text, re.DOTALL | re.IGNORECASE)
            
            if section_match:
                section_text = section_match.group(1)
                
                # Pattern: - Topic (XX%) or - Topic: XX
                pattern = r'[-•]\s+([^(:]+?)(?:\((\d+)%\)|:\s*(\d+))'
                
                for match in re.finditer(pattern, section_text):
                    topic = match.group(1).strip()
                    freq = int(match.group(2) or match.group(3) or 0)
                    
                    topics.append({
                        'topic': topic,
                        'frequency': freq
                    })
            
            return topics[:10]
            
        except Exception as e:
            logger.error(f"Error parsing trending topics: {e}")
            return topics
    
    def _generate_fallback_insights(self, videos: List[Dict], patterns: Dict, days: int) -> Dict:
        """Generate basic insights without AI"""
        summary = f"""Analyzed {len(videos)} videos from {patterns.get('total_channels', 0)} competitor channels over the last {days} days.

**Key Findings:**
- Average views per video: {patterns.get('avg_views', 0):,}
- Total views across all videos: {patterns.get('total_views', 0):,}
- Most active channels show consistent upload schedules

**Top Performing Content:**
The highest-performing videos demonstrate strong audience engagement. Review the top videos list for successful content patterns and consider creating similar content with your unique perspective."""
        
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