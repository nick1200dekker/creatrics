"""
Creator Analyzer - Simplified version focused on great prompts
Updated with AI Provider integration
"""
import os
import requests
import time
import logging
from pathlib import Path
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
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

class CreatorAnalyzer:
    """Analyzes creators and generates insights"""
    
    def __init__(self):
        # Get X API key from environment
        self.x_api_key = os.environ.get('X_RAPID_API_KEY')
        self.x_api_host = os.environ.get('X_RAPID_API_HOST', 'twitter-api45.p.rapidapi.com')
        
        if not self.x_api_key:
            logger.error("X_RAPID_API_KEY not found in environment variables")
            raise ValueError("X_RAPID_API_KEY environment variable is required")
        
        # Load prompt template
        self._load_prompt_template()

    def _load_prompt_template(self):
        """Load prompt template from prompt.txt file"""
        try:
            self.prompt_template = load_prompt('prompt.txt')
            logger.info("Prompt template loaded successfully from prompts/prompt.txt")
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            raise

    def estimate_and_check_ai_credits(self, user_id: str, tweets_count: int) -> Dict:
        """Estimate AI credits needed for timeline analysis"""
        try:
            from app.system.credits.credits_manager import CreditsManager
            
            credits_manager = CreditsManager()
            
            # Use AI provider's default model for estimation
            ai_provider = get_ai_provider(
                script_name='niche/creator_analyzer',
                user_subscription=user_subscription
            )
            model_name = ai_provider.default_model
            
            # Estimate cost from text content
            estimated_text = 'x' * (tweets_count * 150)  # Rough estimation
            cost_estimate = credits_manager.estimate_llm_cost_from_text(
                text_content=estimated_text,
                model_name=model_name
            )
            
            # Analysis requires more processing than simple generation
            required_credits = cost_estimate['final_cost'] * 2.0  # Multiply by 2.0 for analysis
            
            # Check if user has sufficient credits
            credit_check = credits_manager.check_sufficient_credits(
                user_id=user_id,
                required_credits=required_credits
            )
            
            result = {
                'success': True,
                'sufficient_credits': credit_check['sufficient'],
                'required_credits': required_credits,
                'current_credits': credit_check.get('current_credits', 0),
                'cost_estimate': cost_estimate
            }
            
            return result
                
        except Exception as e:
            logger.error(f"Error estimating AI credits: {e}")
            return {'success': False, 'error': str(e)}

    def deduct_actual_ai_credits(self, user_id: str, input_tokens: int, output_tokens: int, model: str) -> bool:
        """Deduct actual credits used"""
        try:
            from app.system.credits.credits_manager import CreditsManager
            
            credits_manager = CreditsManager()
            
            result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                description=f"Creator Timeline Analysis - {input_tokens + output_tokens} tokens",
                feature_id="creator_tracker_analysis"
            )
            
            return result['success']
                
        except Exception as e:
            logger.error(f"Error deducting AI credits: {e}")
            return False

    def analyze_creators(self, user_id: str, creators: List[str], time_range: str = '24h', list_name: str = '', status_callback=None) -> Optional[Dict]:
        """Analyze creators and generate insights"""
        try:
            logger.info(f"Starting creator analysis: {len(creators)} creators for time range {time_range}")
            
            if status_callback:
                status_callback("Fetching tweets from creators...", 50)
            
            # Fetch tweets for each creator
            all_tweets = []
            creator_stats = {}
            
            for i, creator in enumerate(creators):
                logger.info(f"Fetching tweets for @{creator}")
                tweets = self.get_tweets(creator)
                
                # FIXED: Simplified progress update - don't show individual creator names
                if status_callback:
                    progress = 50 + (i / len(creators)) * 30  # 50-80% range
                    # Just show "Analyzing creators..." instead of specific creator names
                    status_callback("Analyzing creators...", progress)
                
                # Filter out RTs and limit to 50 most recent tweets
                filtered_tweets = [
                    tweet for tweet in tweets 
                    if tweet.get('text') is not None and not tweet.get('text', '').startswith('RT @')
                ][:50]
                
                if filtered_tweets:
                    time_filtered_tweets = self.filter_tweets_by_time_range(filtered_tweets, time_range)
                    processed_tweets = [self.process_tweet(tweet, creator) for tweet in time_filtered_tweets]
                    creator_stats[creator] = self.calculate_creator_performance(time_filtered_tweets)
                    
                    logger.info(f"Found {len(processed_tweets)} tweets for @{creator} in the last {time_range}")
                    all_tweets.extend(processed_tweets)
                else:
                    logger.info(f"No tweets found for @{creator}")
                    creator_stats[creator] = {
                        'total_tweets': 0, 'total_likes': 0, 'total_retweets': 0, 'total_views': 0,
                        'avg_likes_per_tweet': 0, 'avg_retweets_per_tweet': 0, 'avg_views_per_tweet': 0,
                        'engagement_rate': 0
                    }
                
                time.sleep(1)  # Rate limiting
            
            logger.info(f"Total tweets collected: {len(all_tweets)}")
            
            if status_callback:
                status_callback("Generating AI insights...", 85)
            
            # Sort all tweets by engagement
            all_tweets.sort(key=lambda x: (
                self._safe_int(x.get('engagement', {}).get('likes', 0)) + 
                self._safe_int(x.get('engagement', {}).get('retweets', 0))
            ), reverse=True)
            
            # Generate timeline analysis with AI
            hot_on_timeline = self.generate_timeline_analysis(all_tweets[:300], user_id)
            
            if status_callback:
                status_callback("Finalizing results...", 95)
            
            # Prepare performance chart data
            performance_chart_data = [
                {
                    'creator': creator,
                    'tweets': perf['total_tweets'],
                    'likes': perf['total_likes'],
                    'retweets': perf['total_retweets'],
                    'views': perf['total_views'],
                    'engagement_rate': round(perf['engagement_rate'], 0)  # Round to whole number
                }
                for creator, perf in creator_stats.items()
            ]
            
            if status_callback:
                status_callback("Analysis complete!", 100)
            
            return {
                'hot_on_timeline': hot_on_timeline,
                'top_performing_tweets': all_tweets[:20],
                'creator_stats': creator_stats,
                'performance_chart_data': performance_chart_data
            }
            
        except Exception as e:
            logger.error(f"Error in analyze_creators: {str(e)}")
            return None

    def generate_timeline_analysis(self, tweets: List[Dict], user_id: str, user_subscription: str = None) -> str:
        """Generate AI-powered timeline analysis and content suggestions"""
        try:
            if not tweets:
                return "<p>No timeline data available at this moment.</p>"
            
            # Check credits
            credit_check = self.estimate_and_check_ai_credits(user_id, len(tweets))
            if not credit_check.get('success', False) or not credit_check.get('sufficient_credits', False):
                return self._generate_simple_fallback(tweets)
            
            # Prepare tweets data
            tweets_data = self._prepare_tweets_for_ai(tweets)
            
            # Use the loaded prompt template
            prompt = self.prompt_template.format(tweets_data=tweets_data)

            # Get AI provider and generate content
            ai_provider = get_ai_provider(
                script_name='niche/creator_analyzer',
                user_subscription=user_subscription
            )
            
            response = ai_provider.create_completion(
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a social media strategist helping content creators identify trends and create valuable, engaging content. Follow the format exactly. Use # for subheaders (e.g., #Content Suggestions#). In Top Trending Topics, use REAL usernames from the data and make it feel conversational - show WHO is talking about WHAT with specific engagement numbers. For Content Ideas, write SHORT social media posts (1-2 sentences max) that provide REAL VALUE - lessons, insights, actionable advice. Avoid empty shock value content."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=3500
            )
            
            # Deduct credits using unified response
            if response.get('usage'):
                self.deduct_actual_ai_credits(
                    user_id, 
                    response['usage']['input_tokens'], 
                    response['usage']['output_tokens'],
                    response['model']
                )
            
            # Process the AI response
            ai_response = response['content'].strip()
            
            # Convert # headers to proper HTML headers and style @mentions
            ai_response = self._format_ai_response(ai_response)
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating timeline analysis: {e}")
            return self._generate_simple_fallback(tweets)

    def _format_ai_response(self, response: str) -> str:
        """Format AI response with proper HTML headers and styled @mentions"""
        # Convert #Header# to proper HTML headers
        response = re.sub(r'#([^#]+)#', r'<h2>\1</h2>', response)
        
        # Convert **text** to <strong>text</strong>
        response = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', response)
        
        # Style @mentions with blue color
        response = re.sub(r'@([a-zA-Z0-9_]+)', r'<span class="mention">@\1</span>', response)
        
        # Add proper line breaks
        response = response.replace('\n\n', '<br><br>')
        response = response.replace('\n', '<br>')
        
        # Fix double breaks after h2 headers - reduce to single break
        response = re.sub(r'(</h2>)<br><br>', r'\1<br>', response)
        
        return response

    def _prepare_tweets_for_ai(self, tweets: List[Dict]) -> str:
        """Prepare tweet data for AI analysis"""
        tweets_data = ""
        
        for i, tweet in enumerate(tweets[:200], 1):  # Top 200 tweets
            creator = tweet.get('creator', 'unknown')
            text = tweet.get('text', '')[:200]  # Limit length
            likes = self._safe_int(tweet.get('engagement', {}).get('likes', 0))
            retweets = self._safe_int(tweet.get('engagement', {}).get('retweets', 0))
            views = self._safe_int(tweet.get('engagement', {}).get('views', 0))
            
            total_engagement = likes + retweets
            
            tweets_data += f"{i}. @{creator}: {text}\n"
            tweets_data += f"   Engagement: {total_engagement:,} (L:{likes:,}, RT:{retweets:,}, V:{views:,})\n\n"
        
        return tweets_data

    def _generate_simple_fallback(self, tweets: List[Dict]) -> str:
        """Simple fallback when AI is unavailable"""
        if not tweets:
            return "<p>No timeline data available at this moment.</p>"
        
        top_tweets = tweets[:20]
        total_engagement = sum(
            self._safe_int(tweet.get('engagement', {}).get('likes', 0)) + 
            self._safe_int(tweet.get('engagement', {}).get('retweets', 0))
            for tweet in top_tweets
        )
        
        creators = list(set([tweet.get('creator', '') for tweet in top_tweets[:10]]))
        
        return f"""
        <h2>Timeline Activity Summary</h2><br><br>
        High activity detected with {total_engagement:,} total engagements across top content.<br><br>
        <strong>Active Creators:</strong> {', '.join([f'<span class="mention">@{c}</span>' for c in creators[:5]])}<br><br>
        AI analysis temporarily unavailable. Upgrade or try again later for detailed insights and content suggestions.
        """

    def get_tweets(self, screen_name: str) -> List[Dict]:
        """Fetch tweets using RapidAPI with retry functionality"""
        url = f"https://{self.x_api_host}/timeline.php"
        
        if screen_name.startswith('@'):
            screen_name = screen_name[1:]
        
        headers = {
            "X-RapidAPI-Host": self.x_api_host,
            "X-RapidAPI-Key": self.x_api_key
        }
        
        params = {"screenname": screen_name}
        
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                tweets = data.get('timeline', [])
                
                # Process tweets
                for tweet in tweets:
                    if 'id' in tweet and 'id_str' not in tweet:
                        tweet['id_str'] = str(tweet['id'])
                    
                    if 'author' in tweet:
                        if not tweet['author'].get('screen_name'):
                            tweet['author']['screen_name'] = screen_name
                        if 'avatar' not in tweet['author']:
                            tweet['author']['avatar'] = tweet['author'].get('profile_image_url', '')
                    else:
                        tweet['author'] = {'screen_name': screen_name, 'avatar': ''}
                
                if tweets:
                    return tweets
                
                if attempt < max_attempts - 1:
                    time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error fetching tweets for @{screen_name}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
        
        return []
    
    def process_tweet(self, tweet: Dict, creator_name: str) -> Dict:
        """Process a tweet to extract necessary data"""
        tweet_id = self._extract_tweet_id(tweet)
        
        processed = {
            "tweet_id": tweet_id,
            "creator": creator_name,
            "text": tweet.get('text', ''),
            "created_at": tweet.get('created_at', ''),
            "engagement": {
                "likes": self._safe_int(tweet.get('favorites', 0)),
                "retweets": self._safe_int(tweet.get('retweets', 0)),
                "views": self._safe_int(tweet.get('views', 0))
            }
        }
        
        if 'author' in tweet and isinstance(tweet['author'], dict):
            author = tweet['author']
            processed["name"] = author.get('name', author.get('screen_name', creator_name))
            processed["profile_image_url"] = author.get('avatar', author.get('profile_image_url', ''))
        else:
            processed["name"] = creator_name
            processed["profile_image_url"] = ''
        
        processed["media"] = self._extract_media(tweet)
        
        return processed
    
    def _extract_media(self, tweet: Dict) -> Dict:
        """Extract media from tweet data"""
        media = {}
        
        if 'media' in tweet and tweet['media']:
            return tweet['media']
        
        if 'entities' in tweet and 'media' in tweet['entities']:
            media_entities = tweet['entities']['media']
            photos = []
            
            for item in media_entities:
                if item.get('type') == 'photo':
                    photos.append({
                        'media_url_https': item.get('media_url_https', ''),
                        'id': item.get('id_str', '')
                    })
            
            if photos:
                media['photo'] = photos
        
        return media
    
    def filter_tweets_by_time_range(self, tweets: List[Dict], time_range: str) -> List[Dict]:
        """Filter tweets by time range"""
        hours = {'24h': 24, '48h': 48, '72h': 72, '1w': 168}.get(time_range, 24)
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_tweets = []
        for tweet in tweets:
            try:
                tweet_date = datetime.strptime(
                    tweet.get('created_at', ''),
                    "%a %b %d %H:%M:%S %z %Y"
                ).replace(tzinfo=None)
                
                if tweet_date > cutoff_time:
                    filtered_tweets.append(tweet)
            except Exception:
                continue
        
        return filtered_tweets
    
    def calculate_creator_performance(self, creator_tweets: List[Dict]) -> Dict:
        """Calculate performance metrics for a creator with improved engagement rate calculation"""
        performance = {
            'total_tweets': len(creator_tweets),
            'total_likes': 0, 'total_retweets': 0, 'total_views': 0,
            'avg_likes_per_tweet': 0, 'avg_retweets_per_tweet': 0, 'avg_views_per_tweet': 0,
            'engagement_rate': 0
        }
        
        total_interactions = 0
        total_views = 0
        valid_tweets_with_views = 0
        
        for tweet in creator_tweets:
            favorites = self._safe_int(tweet.get('favorites', 0))
            retweets = self._safe_int(tweet.get('retweets', 0))
            views = self._safe_int(tweet.get('views', 0))
            
            performance['total_likes'] += favorites
            performance['total_retweets'] += retweets
            performance['total_views'] += views
            
            total_interactions += (favorites + retweets)
            
            if views > 0:
                total_views += views
                valid_tweets_with_views += 1
        
        if creator_tweets:
            performance['avg_likes_per_tweet'] = performance['total_likes'] / len(creator_tweets)
            performance['avg_retweets_per_tweet'] = performance['total_retweets'] / len(creator_tweets)
            performance['avg_views_per_tweet'] = performance['total_views'] / len(creator_tweets)
            
            # FIXED: Improved engagement rate calculation
            if valid_tweets_with_views > 0 and total_views > 0:
                # Standard engagement rate calculation: (likes + retweets) / views * 100
                performance['engagement_rate'] = (total_interactions / total_views) * 100
                # Cap at reasonable maximum (10% is very high engagement)
                performance['engagement_rate'] = min(performance['engagement_rate'], 10.0)
            else:
                # Fallback when views aren't available - use much more conservative approach
                if len(creator_tweets) > 0:
                    avg_interactions_per_tweet = total_interactions / len(creator_tweets)
                    # Estimate views based on typical ratios and calculate conservative engagement
                    if avg_interactions_per_tweet > 0:
                        # Assume very conservative view ratios for estimation
                        estimated_views_per_tweet = avg_interactions_per_tweet * 50  # Very conservative multiplier
                        estimated_total_views = estimated_views_per_tweet * len(creator_tweets)
                        performance['engagement_rate'] = (total_interactions / estimated_total_views) * 100
                        # Cap at 5% for estimated calculations
                        performance['engagement_rate'] = min(performance['engagement_rate'], 5.0)
                    else:
                        performance['engagement_rate'] = 0
            
            # Ensure engagement rate is always reasonable
            performance['engagement_rate'] = max(0, min(10, performance['engagement_rate']))
        
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
        """Extract tweet ID"""
        id_str = tweet.get('id_str', None)
        id_num = tweet.get('id', None)
        tweet_id = tweet.get('tweet_id', None)
        
        if id_str:
            return str(id_str)
        elif tweet_id:
            return str(tweet_id)
        elif id_num:
            return str(id_num)
        
        return ''