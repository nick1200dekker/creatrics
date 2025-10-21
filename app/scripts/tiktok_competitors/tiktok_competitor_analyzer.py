"""
TikTok Competitor Analyzer
Analyzes competitor TikTok accounts and generates insights
"""
import logging
from pathlib import Path
import re
from typing import List, Dict, Optional
from datetime import datetime
from app.scripts.tiktok_competitors.tiktok_api import TikTokAPI
from app.system.ai_provider.ai_provider import get_ai_provider


# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

def load_prompt(filename: str) -> str:
    """Load a prompt from text file"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        raise
logger = logging.getLogger(__name__)

class TikTokCompetitorAnalyzer:
    """Analyzer for TikTok competitor accounts"""
    
    def __init__(self):
        self.tiktok_api = TikTokAPI()
    
    def analyze_competitors(self, account_data: List[Dict], timeframe: str, user_id: str) -> Dict:
        """
        Analyze TikTok competitor accounts
        
        Args:
            account_data: List of dicts with sec_uid, username, nickname
            timeframe: Timeframe in days
            user_id: User ID for tracking
        
        Returns:
            Dict with analysis results
        """
        try:
            days = int(timeframe)
            
            # Fetch data for all accounts
            all_videos = []
            accounts_info = []
            
            for account in account_data:
                sec_uid = account.get('sec_uid')
                username = account.get('username', '')
                nickname = account.get('nickname', '')
                
                logger.info(f"Fetching videos for {nickname} (@{username})")
                
                # Get videos - fetch multiple pages
                videos_result = self.tiktok_api.get_user_videos(sec_uid)
                if not videos_result:
                    logger.warning(f"Could not fetch videos for {username}")
                    continue
                
                videos = videos_result.get('videos', [])
                
                # Try to fetch more videos with pagination
                cursor = videos_result.get('cursor')
                has_more = videos_result.get('hasMore', False)
                fetch_count = 0
                max_fetches = 2
                
                while cursor and has_more and fetch_count < max_fetches:
                    more_videos_result = self.tiktok_api.get_user_videos(sec_uid, cursor=cursor)
                    if more_videos_result:
                        videos.extend(more_videos_result.get('videos', []))
                        cursor = more_videos_result.get('cursor')
                        has_more = more_videos_result.get('hasMore', False)
                        fetch_count += 1
                    else:
                        break
                
                logger.info(f"Fetched {len(videos)} total videos for {nickname}")
                
                # Filter by timeframe
                filtered_videos = self.tiktok_api.filter_videos_by_timeframe(videos, days)
                logger.info(f"After filtering by {days} days: {len(filtered_videos)} videos")
                
                # Add account info to each video
                for video in filtered_videos:
                    video['account_nickname'] = nickname
                    video['account_username'] = username
                    video['sec_uid'] = sec_uid
                
                all_videos.extend(filtered_videos)
                
                # Store account info
                accounts_info.append({
                    'sec_uid': sec_uid,
                    'nickname': nickname,
                    'username': username,
                    'videos_in_timeframe': len(filtered_videos)
                })
            
            if not all_videos:
                return {
                    'success': False,
                    'error': f'No videos found in the last {days} days from any competitor'
                }
            
            # Calculate account stats
            account_stats = self._calculate_account_stats(all_videos, accounts_info)
            
            # Mark overperformers
            for video in all_videos:
                sec_uid = video.get('sec_uid')
                if sec_uid in account_stats:
                    avg_views = account_stats[sec_uid]['avg_views']
                    video_views = int(video.get('view_count', 0) or 0)
                    video['is_overperformer'] = video_views >= (avg_views * 2) if avg_views > 0 else False
                    video['performance_ratio'] = (video_views / avg_views) if avg_views > 0 else 0
            
            # Sort videos
            all_videos.sort(key=lambda x: (
                int(x.get('is_overperformer', False)),
                int(x.get('view_count', 0) or 0)
            ), reverse=True)
            
            logger.info(f"Total videos to analyze: {len(all_videos)}")
            
            # Analyze patterns
            patterns = self._analyze_patterns(all_videos, accounts_info, account_stats)
            
            # Generate insights with AI
            insights = self._generate_insights(all_videos, patterns, days, account_stats)
            
            # Extract token usage
            token_usage = insights.pop('_token_usage', None)
            used_ai = token_usage is not None
            
            if not token_usage:
                token_usage = {
                    'model': 'fallback',
                    'input_tokens': 0,
                    'output_tokens': 0,
                'provider_enum': None
                }
            
            return {
                'success': True,
                'data': {
                    'videos': all_videos[:250],
                    'accounts': accounts_info,
                    'patterns': patterns,
                    'insights': insights,
                    'total_videos': len(all_videos),
                    'timeframe_days': days
                },
                'used_ai': used_ai,
                'token_usage': token_usage
            }
            
        except Exception as e:
            logger.error(f"Error analyzing TikTok competitors: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_account_stats(self, videos: List[Dict], accounts: List[Dict]) -> Dict:
        """Calculate statistics for each account"""
        account_stats = {}
        
        for account in accounts:
            sec_uid = account['sec_uid']
            account_videos = [v for v in videos if v.get('sec_uid') == sec_uid]
            
            if account_videos:
                views = [int(v.get('view_count', 0) or 0) for v in account_videos]
                total_views = sum(views)
                avg_views = total_views / len(views) if views else 0
                
                account_stats[sec_uid] = {
                    'avg_views': avg_views,
                    'total_views': total_views,
                    'video_count': len(account_videos),
                    'account_nickname': account['nickname']
                }
        
        return account_stats
    
    def _analyze_patterns(self, videos: List[Dict], accounts: List[Dict], account_stats: Dict = None) -> Dict:
        """Analyze patterns in video data"""
        if not videos:
            return {}
        
        # Description patterns
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'this', 'that', 'these', 'those', 'is',
                      'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had'}
        
        desc_words = {}
        for video in videos:
            desc = video.get('desc', '').lower()
            words = re.findall(r'\b[a-z]+\b', desc)
            words = [w for w in words if len(w) > 3 and w not in stop_words]
            for word in words:
                desc_words[word] = desc_words.get(word, 0) + 1
        
        top_desc_words = sorted(desc_words.items(), key=lambda x: x[1], reverse=True)[:15]
        
        # Calculate average metrics
        total_views = sum(int(v.get('view_count', 0) or 0) for v in videos)
        total_likes = sum(int(v.get('like_count', 0) or 0) for v in videos)
        avg_views = total_views / len(videos) if videos else 0
        avg_likes = total_likes / len(videos) if videos else 0
        
        # Top performing videos
        top_videos = videos[:10]
        
        # Account upload frequency
        account_upload_freq = {}
        for account in accounts:
            videos_count = account.get('videos_in_timeframe', 0)
            account_upload_freq[account['nickname']] = videos_count
        
        # Overperformers
        overperformers = [v for v in videos if v.get('is_overperformer', False)]
        
        # Account performance
        account_performance = {}
        if account_stats:
            for sec_uid, stats in account_stats.items():
                account_performance[stats['account_nickname']] = {
                    'avg_views': stats['avg_views'],
                    'video_count': stats['video_count']
                }
        
        return {
            'top_desc_words': [{'word': w, 'count': c} for w, c in top_desc_words],
            'avg_views': int(avg_views),
            'avg_likes': int(avg_likes),
            'total_views': total_views,
            'top_videos': top_videos,
            'total_accounts': len(accounts),
            'total_videos_analyzed': len(videos),
            'account_upload_frequency': account_upload_freq,
            'overperformers_count': len(overperformers),
            'account_performance': account_performance
        }
    
    def _generate_insights(self, videos: List[Dict], patterns: Dict, days: int, account_stats: Dict = None, user_subscription: str = None) -> Dict:
        """Generate AI insights from the data"""
        try:
            ai_provider = get_ai_provider(
                script_name='tiktok_competitors/tiktok_competitor_analyzer',
                user_subscription=user_subscription
            )
            
            if not ai_provider or not videos:
                return self._generate_fallback_insights(videos, patterns, days)
            
            # Prepare data summary for AI
            top_videos = videos[:15]
            video_summaries = []
            hashtag_performance = {}

            for v in top_videos:
                views = v.get('view_count', 0)
                likes = v.get('like_count', 0)
                account = v.get('account_nickname', 'Unknown')
                is_overperformer = v.get('is_overperformer', False)
                performance_ratio = v.get('performance_ratio', 0)
                desc = v.get('desc', 'No description')

                # Extract hashtags from description and track their performance
                hashtags = re.findall(r'#\w+', desc)
                for tag in hashtags:
                    if tag not in hashtag_performance:
                        hashtag_performance[tag] = {'total_views': 0, 'count': 0, 'avg_views': 0}
                    hashtag_performance[tag]['total_views'] += views
                    hashtag_performance[tag]['count'] += 1

                status = f" [OVERPERFORMER {performance_ratio:.1f}x avg]" if is_overperformer else ""
                video_summaries.append(f"- '{desc}' by {account} ({views:,} views, {likes:,} likes){status}")

            # Calculate average views per hashtag
            for tag, data in hashtag_performance.items():
                data['avg_views'] = data['total_views'] / data['count'] if data['count'] > 0 else 0

            # Sort hashtags by average views (performance) then by frequency
            top_hashtags = sorted(
                hashtag_performance.items(),
                key=lambda x: (x[1]['avg_views'], x[1]['count']),
                reverse=True
            )[:10]

            # Format hashtag list with performance info
            hashtag_list = ' '.join([
                f"{tag} ({data['avg_views']:,.0f} avg views)"
                for tag, data in top_hashtags
            ])
            
            # Get top words
            top_words = ', '.join([w['word'] for w in patterns.get('top_desc_words', [])[:10]])
            
            # Account performance
            account_performance = patterns.get('account_performance', {})
            sorted_accounts = sorted(
                account_performance.items(),
                key=lambda x: x[1]['avg_views'],
                reverse=True
            )[:5]
            
            performance_info = []
            for account_name, stats in sorted_accounts:
                performance_info.append(
                    f"{account_name} ({stats['avg_views']:,.0f} avg views, {stats['video_count']} videos)"
                )
            
            system_prompt_template = load_prompt('analyze_insights_system.txt')
            system_prompt = system_prompt_template.format(
                current_date=datetime.now().strftime('%B %d, %Y')
            )

            user_prompt_template = load_prompt('analyze_insights_user.txt')
            prompt = user_prompt_template.format(
                days=days,
                video_summaries=chr(10).join(video_summaries),
                top_words=top_words,
                hashtag_list=hashtag_list
            )
            
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
            
            # Store token usage
            usage = response.get('usage', {})
            parsed_insights['_token_usage'] = {
                'model': response.get('model', 'unknown'),
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'provider_enum': response.get('provider_enum')
            }
            
            return parsed_insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return self._generate_fallback_insights(videos, patterns, days)
    
    def _parse_ai_insights(self, insights_text: str) -> Dict:
        """Parse AI-generated insights into structured format"""
        try:
            summary = insights_text
            quick_wins = self._parse_content_ideas(insights_text)
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
            section_match = re.search(r'##\s*Content Opportunities(.+?)(?=##|$)', text, re.DOTALL)
            if not section_match:
                return ideas
            
            section_text = section_match.group(1)
            pattern = r'"([^"]+)"'
            
            for match in re.finditer(pattern, section_text):
                title = match.group(1).strip()
                
                if title and len(title) > 10:
                    ideas.append({
                        'title': title,
                        'opportunity': '',
                        'account': 'Content Opportunity',
                        'views': 0
                    })
            
            return ideas[:8]
            
        except Exception as e:
            logger.error(f"Error parsing content ideas: {e}")
            return ideas
    
    def _parse_trending_from_text(self, text: str) -> List[Dict]:
        """Extract trending topics from the text"""
        topics = []
        
        try:
            section_match = re.search(r'(?:Pattern|Topic|Trend)s?[:\s]+(.+?)(?=##|$)', text, re.DOTALL | re.IGNORECASE)
            
            if section_match:
                section_text = section_match.group(1)
                words = re.findall(r'\b[A-Z][a-z]+\b', section_text)
                word_count = {}
                for word in words:
                    if len(word) > 4:
                        word_count[word] = word_count.get(word, 0) + 1
                
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

Analyzed **{len(videos)} videos** from **{patterns.get('total_accounts', 0)} accounts** over the last {days} days.

**Key Metrics:**
- Average views per video: **{patterns.get('avg_views', 0):,}**
- Average likes per video: **{patterns.get('avg_likes', 0):,}**
- Total views across all videos: **{patterns.get('total_views', 0):,}**

**Top Performing Content:**
The highest-performing videos demonstrate strong audience engagement. Review the top videos list for successful content patterns."""
        
        return {
            'summary': summary,
            'quick_wins': [],
            'trending_topics': self._extract_trending_topics(patterns)
        }
    
    def _extract_trending_topics(self, patterns: Dict) -> List[Dict]:
        """Extract trending topics from description patterns"""
        trending = []
        for word_data in patterns.get('top_desc_words', [])[:10]:
            trending.append({
                'topic': word_data['word'].title(),
                'frequency': word_data['count']
            })
        
        return trending