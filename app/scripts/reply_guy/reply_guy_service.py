"""
Reply Guy Service - Complete version with original functionality + mention filtering and improvements
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uuid

from firebase_admin import firestore
from .list_manager import ListManager
from .reply_analyzer import ReplyAnalyzer
from .reply_generator import ReplyGenerator

logger = logging.getLogger(__name__)

class ReplyGuyService:
    """Main service for Reply Guy functionality"""
    
    def __init__(self):
        self.db = firestore.client()
        self.list_manager = ListManager()
        self.analyzer = ReplyAnalyzer()
        self.generator = ReplyGenerator()
    
    # LIST MANAGEMENT
    
    def get_default_lists(self) -> List[Dict]:
        """Get the single default list - Content Creators"""
        try:
            # Get accounts for the default list
            accounts = self.get_default_list_accounts('content_creators')

            return [{
                'id': 'content_creators',
                'name': 'Reply List',
                'industry': 'Content Creation',
                'account_count': len(accounts),
                'last_updated': datetime.now()
            }]

        except Exception as e:
            logger.error(f"Error getting default lists: {str(e)}")
            return []

    def get_default_list_accounts(self, list_id: str) -> List[str]:
        """Get accounts for a default list - Custom curated list"""
        if list_id == 'content_creators':
            return [
                'elonmusk',
                'NBA',
                'CNN',
                'NoContextHumans',
                'InternetH0F',
                'POTUS',
                'WorldWideWob',
                'TheHateCentral',
                'FilmUpdates',
                'AMAZlNGNATURE',
                'WallStreetApes',
                'DudespostingWs',
                'saylor',
                'Cobratate',
                'defense_civil25',
                'BBCNews',
                'HumanityChad',
                'MarioNawfal',
                'alifarhat79',
                'historyinmemes',
                'WallStreetMav',
                'fasc1nate',
                'Rainmaker1973',
                'DailyLoud',
                'FabrizioRomano',
                'crazyclipsonly',
                'upblissed',
                'wildtiktokss',
                'ShitpostGate',
                'kirawontmiss',
                'WatcherGuru',
                'ElonMuskAOC',
                'greg16676935420',
                'EverythingOOC',
                'unusual_whales',
                'rawsalerts',
                'HumansNoContext',
                'PopBase',
                'pepe_fgm',
                'DiscussingFilm',
                'PopCrave',
                'OddestHistory_',
                'FAFO_TV',
                'creepydotorg',
                'CensoredMen',
                'Morbidful',
                'TheFigen_',
                'scubaryan_',
                'ayeejuju',
                'stxrinsky',
                'ImMeme0',
                'invis4yo',
                'LibertyCappy',
                'interesting_aIl',
                'crazyclips_'
            ]
        return []
    
    def get_user_custom_lists(self, user_id: str) -> List[Dict]:
        """Get user's custom lists"""
        try:
            lists_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom')
            docs = lists_ref.stream()
            
            lists = []
            for doc in docs:
                data = doc.to_dict()
                lists.append({
                    'id': doc.id,
                    'name': data.get('name', ''),
                    'type': data.get('type', 'manual'),
                    'account_count': len(data.get('accounts', [])),
                    'created_at': data.get('created_at'),
                    'last_updated': data.get('last_updated'),
                    'accounts': data.get('accounts', [])  # Include accounts for editing
                })
            
            # Sort by created date (newest first)
            lists.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
            return lists
            
        except Exception as e:
            logger.error(f"Error getting user custom lists: {str(e)}")
            return []
    
    def create_custom_list(self, user_id: str, name: str, list_type: str, x_list_id: Optional[str] = None) -> Dict:
        """Create a new custom list"""
        try:
            list_id = str(uuid.uuid4())
            
            # Prepare list data
            list_data = {
                'name': name,
                'type': list_type,
                'accounts': [],
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
            
            # If it's an X list, fetch the accounts
            if list_type == 'x_list' and x_list_id:
                list_data['x_list_id'] = x_list_id
                accounts = self.list_manager.fetch_x_list_accounts(x_list_id)
                if accounts:
                    list_data['accounts'] = accounts
                else:
                    # Don't fail completely, just create empty list and show warning
                    logger.warning(f"Failed to fetch X list accounts for {x_list_id}, creating empty list")
            
            # Save to Firestore
            doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
            doc_ref.set(list_data)
            
            return {
                'success': True,
                'list': {
                    'id': list_id,
                    'name': name,
                    'type': list_type,
                    'account_count': len(list_data['accounts'])
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating custom list: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def update_custom_list(self, user_id: str, list_id: str, action: str, account: Optional[str] = None) -> Dict:
        """Update a custom list"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {'success': False, 'error': 'List not found'}
            
            data = doc.to_dict()
            accounts = data.get('accounts', [])
            
            if action == 'refresh' and data.get('type') == 'x_list':
                # Refresh X list
                x_list_id = data.get('x_list_id')
                if x_list_id:
                    new_accounts = self.list_manager.fetch_x_list_accounts(x_list_id)
                    if new_accounts:
                        accounts = new_accounts
                    else:
                        return {'success': False, 'error': 'Failed to refresh X list'}
                
            elif action == 'add_account' and account:
                # Add account to manual list
                if account not in accounts:
                    accounts.append(account)
                else:
                    return {'success': False, 'error': 'Account already in list'}
                
            elif action == 'remove_account' and account:
                # Remove account from manual list
                if account in accounts:
                    accounts.remove(account)
                else:
                    return {'success': False, 'error': 'Account not in list'}
            
            # Update the list
            doc_ref.update({
                'accounts': accounts,
                'last_updated': datetime.now()
            })
            
            return {
                'success': True,
                'account_count': len(accounts),
                'accounts': accounts
            }
            
        except Exception as e:
            logger.error(f"Error updating custom list: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def delete_custom_list(self, user_id: str, list_id: str) -> bool:
        """Delete a custom list"""
        try:
            # Delete the list document
            doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
            doc_ref.delete()
            
            # Also delete any analysis for this list
            analysis_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('current_analysis').collection('analyses').document(list_id)
            analysis_ref.delete()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting custom list: {str(e)}")
            return False
    
    # SELECTION & ANALYSIS
    
    def get_current_selection(self, user_id: str) -> Optional[Dict]:
        """Get user's current list selection"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('settings')
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return {
                    'list_id': data.get('selected_list_id'),
                    'list_type': data.get('selected_list_type'),
                    'list_name': data.get('selected_list_name', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current selection: {str(e)}")
            return None
    
    def set_current_selection(self, user_id: str, list_id: str, list_type: str) -> bool:
        """Set user's current list selection"""
        try:
            # Get list name
            list_name = ""
            if list_type == 'default':
                doc_ref = self.db.collection('default_lists').document(list_id)
                doc = doc_ref.get()
                if doc.exists:
                    list_name = doc.to_dict().get('name', '')
            else:
                doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
                doc = doc_ref.get()
                if doc.exists:
                    list_name = doc.to_dict().get('name', '')
            
            # Save selection
            settings_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('settings')
            settings_ref.set({
                'selected_list_id': list_id,
                'selected_list_type': list_type,
                'selected_list_name': list_name,
                'last_updated': datetime.now()
            }, merge=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting current selection: {str(e)}")
            return False
    
    def get_current_analysis(self, user_id: str, list_id: str, list_type: str, limit: Optional[int] = None, offset: int = 0) -> Optional[Dict]:
        """Get current analysis for a list with proper newline conversion and mention filtering

        Args:
            user_id: User ID
            list_id: List ID
            list_type: 'default' or 'custom'
            limit: Max number of tweets to return (None = all tweets, for backwards compatibility)
            offset: Starting index for pagination
        """
        try:
            if list_type == 'default':
                # For default lists, check the global default_list_analyses collection first
                doc_ref = self.db.collection('default_list_analyses').document(list_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    
                    # Filter tweets by recency (last 24h by default)
                    tweets = data.get('tweet_opportunities', [])
                    filtered_tweets = self._filter_recent_tweets(tweets, hours=24)
                    
                    # APPLY MENTION FILTERING - exclude tweets starting with @
                    mention_filtered_tweets = []
                    for tweet in filtered_tweets:
                        tweet_text = tweet.get('text', '').strip()
                        # Convert _new_line_ back to actual newlines for filtering check
                        tweet_text_for_check = tweet_text.replace('_new_line_', '\n').strip()
                        
                        # Skip tweets that start with @ (mentions)
                        if not tweet_text_for_check.startswith('@'):
                            mention_filtered_tweets.append(tweet)
                        else:
                            logger.debug(f"Filtered out mention tweet from default list: {tweet_text_for_check[:50]}...")
                    
                    # Proper newline conversion for display - convert _new_line_ to actual <br> tags
                    for tweet in mention_filtered_tweets:
                        if 'text' in tweet:
                            # Convert our standard marker to <br> tags for HTML display
                            tweet['text'] = tweet['text'].replace('_new_line_', '<br>')

                    # PAGINATION: Apply limit and offset if specified
                    total_count = len(mention_filtered_tweets)
                    if limit is not None:
                        paginated_tweets = mention_filtered_tweets[offset:offset + limit]
                        logger.info(f"Returning {len(paginated_tweets)} of {total_count} opportunities (offset={offset}, limit={limit}) for default list {list_id}")
                    else:
                        paginated_tweets = mention_filtered_tweets
                        logger.info(f"Found {total_count} valid recent opportunities for default list {list_id}")

                    return {
                        'list_id': list_id,
                        'list_type': list_type,
                        'list_name': data.get('list_name', ''),
                        'tweet_opportunities': paginated_tweets,
                        'total_count': total_count,  # Always include total for pagination
                        'timestamp': data.get('last_updated'),
                        'parameters': {
                            'time_range': '24h',
                            'account_count': data.get('analyzed_accounts', 0)
                        }
                    }
                else:
                    logger.info(f"No default analysis found for list {list_id}")
            else:
                # For custom lists, check user's analysis collection
                doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('current_analysis').collection('analyses').document(list_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    
                    # Filter tweets by recency (last 24h by default)
                    tweets = data.get('tweet_opportunities', [])
                    filtered_tweets = self._filter_recent_tweets(tweets, hours=24)
                    
                    # APPLY MENTION FILTERING - exclude tweets starting with @
                    mention_filtered_tweets = []
                    for tweet in filtered_tweets:
                        tweet_text = tweet.get('text', '').strip()
                        # Convert _new_line_ back to actual newlines for filtering check
                        tweet_text_for_check = tweet_text.replace('_new_line_', '\n').strip()
                        
                        # Skip tweets that start with @ (mentions)
                        if not tweet_text_for_check.startswith('@'):
                            mention_filtered_tweets.append(tweet)
                        else:
                            logger.debug(f"Filtered out mention tweet from custom list: {tweet_text_for_check[:50]}...")
                    
                    # Proper newline conversion for display - convert _new_line_ to actual <br> tags
                    for tweet in mention_filtered_tweets:
                        if 'text' in tweet:
                            # Convert our standard marker to <br> tags for HTML display
                            tweet['text'] = tweet['text'].replace('_new_line_', '<br>')

                    # PAGINATION: Apply limit and offset if specified
                    total_count = len(mention_filtered_tweets)
                    if limit is not None:
                        paginated_tweets = mention_filtered_tweets[offset:offset + limit]
                        logger.info(f"Returning {len(paginated_tweets)} of {total_count} opportunities (offset={offset}, limit={limit}) for custom list {list_id}")
                    else:
                        paginated_tweets = mention_filtered_tweets
                        logger.info(f"Found {total_count} valid recent opportunities for custom list {list_id}")

                    return {
                        'list_id': list_id,
                        'list_type': list_type,
                        'list_name': data.get('list_name', ''),
                        'tweet_opportunities': paginated_tweets,
                        'total_count': total_count,  # Always include total for pagination
                        'timestamp': data.get('timestamp'),
                        'parameters': data.get('parameters', {})
                    }
                else:
                    logger.info(f"No custom analysis found for list {list_id}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current analysis: {str(e)}")
            return None
    
    def run_analysis(self, user_id: str, list_id: str, list_type: str, time_range: str = '24h') -> Optional[str]:
        """Run analysis on a list"""
        try:
            # Get list accounts and name
            accounts = []
            list_name = ""

            if list_type == 'default':
                # Get accounts from the default list
                accounts = self.get_default_list_accounts(list_id)
                if list_id == 'content_creators':
                    list_name = 'Reply List'
                logger.info(f"Running analysis for default list {list_id} with {len(accounts)} accounts")
            else:
                # Get accounts for custom lists
                doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('lists').collection('custom').document(list_id)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    accounts = data.get('accounts', [])
                    list_name = data.get('name', '')
            
            if not accounts:
                return None
            
            # Run analysis (analyzer already filters mentions)
            analysis_data = self.analyzer.analyze_accounts(accounts, time_range, list_name)
            
            if analysis_data:
                # Save analysis
                if list_type == 'default':
                    # Save default list analysis to global collection for all users to access
                    analysis_ref = self.db.collection('default_list_analyses').document(list_id)
                    analysis_ref.set({
                        'list_id': list_id,
                        'list_name': list_name,
                        'tweet_opportunities': analysis_data['tweet_opportunities'],
                        'last_updated': datetime.now(),
                        'analyzed_accounts': len(accounts),
                        'parameters': {
                            'time_range': time_range,
                            'account_count': len(accounts)
                        }
                    })
                    logger.info(f"Saved default list analysis for {list_id} with {len(analysis_data['tweet_opportunities'])} opportunities")
                else:
                    # Save custom list analysis to user's collection
                    analysis_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('current_analysis').collection('analyses').document(list_id)
                    analysis_ref.set({
                        'list_id': list_id,
                        'list_type': list_type,
                        'list_name': list_name,
                        'tweet_opportunities': analysis_data['tweet_opportunities'],
                        'timestamp': datetime.now(),
                        'parameters': {
                            'time_range': time_range,
                            'account_count': len(accounts)
                        }
                    })

                return list_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error running analysis: {str(e)}")
            return None
    
    # REPLY GENERATION
    
    def generate_reply(self, user_id: str, tweet_text: str, author: str, style: str, use_brand_voice: bool = False) -> Optional[str]:
        """Generate AI reply with proper newline handling and mention filtering"""
        try:
            # Additional check to prevent generating replies to mention tweets
            tweet_text_stripped = tweet_text.strip()
            if tweet_text_stripped.startswith('@'):
                logger.warning(f"Attempted to generate reply to mention tweet: {tweet_text_stripped[:50]}...")
                return None
            
            # The tweet_text comes from the frontend - convert _new_line_ back to actual newlines for the AI
            clean_tweet_text = tweet_text.replace('_new_line_', '\n')
            
            return self.generator.generate_reply(
                user_id=user_id,
                tweet_text=clean_tweet_text,
                author=author, 
                style=style,
                use_brand_voice=use_brand_voice
            )
            
        except Exception as e:
            logger.error(f"Error generating reply: {str(e)}")
            return None
    
    def has_brand_voice_data(self, user_id: str) -> bool:
        """Check if user has brand voice data"""
        try:
            return self.generator.has_brand_voice_data(user_id)
        except Exception as e:
            logger.error(f"Error checking brand voice: {str(e)}")
            return False
    
    # REPLY STATS
    
    def get_reply_stats(self, user_id: str) -> Dict:
        """Get daily reply statistics"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('stats')
            doc = doc_ref.get()
            
            today = datetime.now().date()
            
            if doc.exists:
                data = doc.to_dict()
                last_date = data.get('last_date')
                
                # Reset if new day
                if last_date != today.isoformat():
                    stats = {
                        'total_replies': 0,
                        'target': 50,
                        'progress_percentage': 0,
                        'last_date': today.isoformat()
                    }
                    doc_ref.set(stats)
                    return stats
                else:
                    total_replies = data.get('total_replies', 0)
                    target = data.get('target', 50)
                    progress_percentage = min(int((total_replies / target) * 100), 100)
                    
                    return {
                        'total_replies': total_replies,
                        'target': target,
                        'progress_percentage': progress_percentage,
                        'last_date': today.isoformat()
                    }
            else:
                # Create new stats
                stats = {
                    'total_replies': 0,
                    'target': 50,
                    'progress_percentage': 0,
                    'last_date': today.isoformat()
                }
                doc_ref.set(stats)
                return stats
                
        except Exception as e:
            logger.error(f"Error getting reply stats: {str(e)}")
            return {'total_replies': 0, 'target': 50, 'progress_percentage': 0}
    
    def log_reply(self, user_id: str, tweet_id: str, reply_text: str) -> Dict:
        """Log a reply and update stats"""
        try:
            # Update stats
            doc_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('stats')
            doc = doc_ref.get()
            
            today = datetime.now().date()
            
            if doc.exists:
                data = doc.to_dict()
                total_replies = data.get('total_replies', 0) + 1
            else:
                total_replies = 1
            
            target = 50
            progress_percentage = min(int((total_replies / target) * 100), 100)
            
            stats = {
                'total_replies': total_replies,
                'target': target,
                'progress_percentage': progress_percentage,
                'last_date': today.isoformat()
            }
            
            doc_ref.set(stats)
            
            # Log the individual reply
            reply_ref = self.db.collection('users').document(str(user_id)).collection('reply_guy').document('reply_log').collection('replies').document()
            reply_ref.set({
                'tweet_id': tweet_id,
                'reply_text': reply_text,
                'timestamp': datetime.now()
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error logging reply: {str(e)}")
            return {'total_replies': 0, 'target': 50, 'progress_percentage': 0}
    
    # UTILITY METHODS
    
    def _filter_recent_tweets(self, tweets: List[Dict], hours: int = 24) -> List[Dict]:
        """Filter tweets to show only recent ones"""
        if not tweets:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_tweets = []
        
        for tweet in tweets:
            try:
                created_at = tweet.get('created_at')
                if created_at:
                    # Parse Twitter date format
                    tweet_date = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)
                    if tweet_date > cutoff_time:
                        filtered_tweets.append(tweet)
                else:
                    # Include tweets without dates
                    filtered_tweets.append(tweet)
            except Exception as e:
                logger.error(f"Error parsing tweet date: {str(e)}")
                # Include tweets with unparseable dates
                filtered_tweets.append(tweet)
        
        return filtered_tweets