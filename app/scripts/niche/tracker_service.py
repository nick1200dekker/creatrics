"""
Tracker Service - Main service for Creator Tracker functionality
Handles Firebase storage and business logic with improved chart formatting
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uuid
import threading

from firebase_admin import firestore
from .creator_analyzer import CreatorAnalyzer
from .x_list_manager import XListManager

logger = logging.getLogger(__name__)

class TrackerService:
    """Main service for Creator Tracker functionality"""
    
    def __init__(self):
        self.db = firestore.client()
        self.analyzer = CreatorAnalyzer()
        self.x_list_manager = XListManager()
        
        # Store active analysis processes
        self.active_analyses = {}
    
    # LIST MANAGEMENT
    
    def get_user_lists(self, user_id: str) -> List[Dict]:
        """Get all creator lists for a user"""
        try:
            lists_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists')
            docs = lists_ref.stream()
            
            lists = []
            for doc in docs:
                data = doc.to_dict()
                lists.append({
                    'name': doc.id,
                    'creators': data.get('creators', []),
                    'is_x_list': data.get('is_x_list', False),
                    'x_list_id': data.get('x_list_id'),
                    'created_at': data.get('created_at'),
                    'updated_at': data.get('updated_at')
                })
            
            # Sort by name
            lists.sort(key=lambda x: x['name'])
            return lists
            
        except Exception as e:
            logger.error(f"Error getting user lists: {str(e)}")
            return []
    
    def create_list(self, user_id: str, list_name: str, list_type: str = 'manual', x_list_id: Optional[str] = None) -> Dict:
        """Create a new creator list"""
        try:
            # Sanitize list name
            clean_name = ''.join(c for c in list_name if c.isalnum() or c in [' ', '_']).replace(' ', '_')
            
            # Check if list already exists
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(clean_name)
            if doc_ref.get().exists:
                return {
                    'success': False, 
                    'message': f'List "{clean_name}" already exists'
                }
            
            # Prepare list data
            list_data = {
                'creators': [],
                'is_x_list': list_type == 'x_list',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # If it's an X list, fetch the creators
            if list_type == 'x_list' and x_list_id:
                list_data['x_list_id'] = x_list_id
                try:
                    creators = self.x_list_manager.get_all_list_members(x_list_id)
                    if creators:
                        list_data['creators'] = creators
                        logger.info(f"Fetched {len(creators)} creators for X list {x_list_id}")
                    else:
                        logger.warning(f"No creators found for X list {x_list_id}")
                except Exception as e:
                    logger.error(f"Error fetching X list: {str(e)}")
                    return {
                        'success': False, 
                        'message': f'Error fetching X list: {str(e)}'
                    }
            
            # Save to Firestore
            doc_ref.set(list_data)
            
            return {
                'success': True,
                'message': f'List "{clean_name}" created successfully with {len(list_data["creators"])} creators',
                'list_name': clean_name,
                'creator_count': len(list_data['creators'])
            }
            
        except Exception as e:
            logger.error(f"Error creating list: {str(e)}")
            return {
                'success': False, 
                'message': f'Error creating list: {str(e)}'
            }
    
    def delete_list(self, user_id: str, list_name: str) -> bool:
        """Delete a creator list"""
        try:
            # Delete the list
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(list_name)
            doc_ref.delete()
            
            # Also delete any analyses for this list
            analyses_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('analyses').collection('results')
            analyses = analyses_ref.where('list_name', '==', list_name).stream()
            for analysis in analyses:
                analysis.reference.delete()
            
            # Remove from default list if it was set
            settings_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('settings')
            settings_doc = settings_ref.get()
            if settings_doc.exists and settings_doc.to_dict().get('default_list') == list_name:
                settings_ref.update({'default_list': firestore.DELETE_FIELD})
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting list: {str(e)}")
            return False
    
    def add_creator_to_list(self, user_id: str, list_name: str, creator_handle: str) -> Dict:
        """Add a creator to a specific list"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(list_name)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'success': False,
                    'message': 'Selected list does not exist'
                }
            
            data = doc.to_dict()
            
            # Check if it's an X list (which can't be manually edited)
            if data.get('is_x_list', False):
                return {
                    'success': False,
                    'message': 'This is an X list and cannot be edited manually. Please use the Update List feature.'
                }
            
            creators = data.get('creators', [])
            
            # Check if creator already exists
            if creator_handle in creators:
                return {
                    'success': False,
                    'message': f'Creator "{creator_handle}" already exists in the list'
                }
            
            # Add creator
            creators.append(creator_handle)
            
            # Update document
            doc_ref.update({
                'creators': creators,
                'updated_at': datetime.now()
            })
            
            return {
                'success': True,
                'message': f'Creator "{creator_handle}" added successfully',
                'creators': creators
            }
            
        except Exception as e:
            logger.error(f"Error adding creator: {str(e)}")
            return {
                'success': False,
                'message': f'Error adding creator: {str(e)}'
            }
    
    def remove_creator_from_list(self, user_id: str, list_name: str, creator_handle: str) -> Dict:
        """Remove a creator from a specific list"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(list_name)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'success': False,
                    'error': 'List not found'
                }
            
            data = doc.to_dict()
            
            # Check if it's an X list
            if data.get('is_x_list', False):
                return {
                    'success': False,
                    'error': 'This is an X list and cannot be edited manually. Please use the Update List feature.'
                }
            
            creators = data.get('creators', [])
            
            # Check if creator exists
            if creator_handle not in creators:
                return {
                    'success': False,
                    'error': f'Creator {creator_handle} not found in this list'
                }
            
            # Remove creator
            creators.remove(creator_handle)
            
            # Update document
            doc_ref.update({
                'creators': creators,
                'updated_at': datetime.now()
            })
            
            return {
                'success': True,
                'message': f'Creator {creator_handle} removed successfully',
                'creators': creators
            }
            
        except Exception as e:
            logger.error(f"Error removing creator: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_list_creators(self, user_id: str, list_name: str) -> List[str]:
        """Get creators for a specific list"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(list_name)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict().get('creators', [])
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting list creators: {str(e)}")
            return []
    
    def update_x_list(self, user_id: str, list_name: str) -> Dict:
        """Update an X list with latest members"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(list_name)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    'success': False,
                    'message': 'List not found'
                }
            
            data = doc.to_dict()
            
            if not data.get('is_x_list', False):
                return {
                    'success': False,
                    'message': 'This is not an X list'
                }
            
            x_list_id = data.get('x_list_id')
            if not x_list_id:
                return {
                    'success': False,
                    'message': 'No X list ID found'
                }
            
            # Fetch updated creators
            creators = self.x_list_manager.get_all_list_members(x_list_id)
            if not creators:
                return {
                    'success': False,
                    'message': 'Failed to fetch X list members or list is empty'
                }
            
            # Update document
            doc_ref.update({
                'creators': creators,
                'updated_at': datetime.now()
            })
            
            return {
                'success': True,
                'message': f'X list updated with {len(creators)} creators',
                'creators': creators
            }
            
        except Exception as e:
            logger.error(f"Error updating X list: {str(e)}")
            return {
                'success': False,
                'message': f'Error updating X list: {str(e)}'
            }
    
    # DEFAULT LIST MANAGEMENT
    
    def get_default_list(self, user_id: str) -> Optional[str]:
        """Get the user's default list name"""
        try:
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('settings')
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict().get('default_list')
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting default list: {str(e)}")
            return None
    
    def set_default_list(self, user_id: str, list_name: str) -> bool:
        """Set a list as the default list"""
        try:
            # Verify list exists
            doc_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('lists').collection('user_lists').document(list_name)
            if not doc_ref.get().exists:
                return False
            
            # Set as default
            settings_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('settings')
            settings_ref.set({
                'default_list': list_name,
                'updated_at': datetime.now()
            }, merge=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting default list: {str(e)}")
            return False
    
    # ANALYSIS MANAGEMENT
    
    def get_analysis_status(self, user_id: str) -> Dict:
        """Get current analysis status"""
        if user_id not in self.active_analyses:
            return {
                'running': False,
                'step': 'No analysis running',
                'progress': 0,
                'status': 'idle'
            }
        return self.active_analyses[user_id]
    
    def set_analysis_status(self, user_id: str, status: Dict):
        """Set analysis status"""
        self.active_analyses[user_id] = status
    
    def start_analysis(self, user_id: str, list_name: str, time_range: str = '24h') -> Optional[str]:
        """Start creator analysis"""
        try:
            # Get creators from list
            creators = self.get_list_creators(user_id, list_name)
            if not creators:
                logger.error(f"No creators found in list {list_name}")
                return None
            
            # Set initial status
            self.set_analysis_status(user_id, {
                'running': True,
                'step': 'Starting analysis...',
                'progress': 5,
                'status': 'started'
            })
            
            # Generate analysis ID
            analysis_id = str(uuid.uuid4())
            
            # Start analysis in background thread
            thread = threading.Thread(
                target=self._run_analysis_background,
                args=(user_id, analysis_id, creators, time_range, list_name)
            )
            thread.daemon = True
            thread.start()
            
            return analysis_id
            
        except Exception as e:
            logger.error(f"Error starting analysis: {str(e)}")
            return None
    
    def _run_analysis_background(self, user_id: str, analysis_id: str, creators: List[str], time_range: str, list_name: str):
        """Run analysis in background thread"""
        try:
            self.set_analysis_status(user_id, {
                'running': True,
                'step': f'Analyzing {len(creators)} creators...',
                'progress': 10,
                'status': 'running'
            })
            
            # Run analysis
            analysis_result = self.analyzer.analyze_creators(
                user_id=user_id,
                creators=creators,
                time_range=time_range,
                list_name=list_name
            )
            
            if analysis_result:
                # Save to Firestore
                analysis_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('analyses').collection('results').document(analysis_id)
                analysis_data = {
                    'analysis_id': analysis_id,
                    'list_name': list_name,
                    'timestamp': datetime.now(),
                    'parameters': {
                        'time_range': time_range,
                        'analyzed_creators': creators,
                        'list_name': list_name
                    },
                    'hot_on_timeline': analysis_result.get('hot_on_timeline', ''),
                    'top_performing_tweets': analysis_result.get('top_performing_tweets', []),
                    'creator_stats': analysis_result.get('creator_stats', {}),
                    'performance_chart_data': analysis_result.get('performance_chart_data', [])
                }
                
                analysis_ref.set(analysis_data)
                
                # Update latest analysis reference
                latest_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('latest_analysis')
                latest_ref.set({
                    'analysis_id': analysis_id,
                    'list_name': list_name,
                    'timestamp': datetime.now()
                }, merge=True)
                
                self.set_analysis_status(user_id, {
                    'running': False,
                    'step': 'Analysis complete',
                    'progress': 100,
                    'status': 'completed',
                    'result_id': analysis_id
                })
                
            else:
                self.set_analysis_status(user_id, {
                    'running': False,
                    'step': 'Analysis failed',
                    'progress': 0,
                    'status': 'error'
                })
                
        except Exception as e:
            logger.error(f"Error in background analysis: {str(e)}")
            self.set_analysis_status(user_id, {
                'running': False,
                'step': f'Error: {str(e)}',
                'progress': 0,
                'status': 'error'
            })
    
    def get_latest_analysis(self, user_id: str, list_name: Optional[str] = None) -> Optional[Dict]:
        """Get the latest analysis for a user"""
        try:
            # If list_name provided, get analysis for that specific list
            if list_name:
                analyses_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('analyses').collection('results')
                query = analyses_ref.where('list_name', '==', list_name).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1)
                docs = list(query.stream())
                
                if docs:
                    return docs[0].to_dict()
            
            # Otherwise get the latest analysis overall
            latest_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('latest_analysis')
            latest_doc = latest_ref.get()
            
            if latest_doc.exists:
                analysis_id = latest_doc.to_dict().get('analysis_id')
                if analysis_id:
                    analysis_ref = self.db.collection('users').document(str(user_id)).collection('creator_tracker').document('analyses').collection('results').document(analysis_id)
                    analysis_doc = analysis_ref.get()
                    if analysis_doc.exists:
                        return analysis_doc.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest analysis: {str(e)}")
            return None
    
    def transform_chart_data(self, performance_data: List[Dict]) -> Optional[Dict]:
        """Transform performance data for charts with FIXED engagement rate calculation"""
        try:
            if not performance_data:
                return None
            
            # Helper function to safely get numeric values
            def safe_number(value, default=0):
                try:
                    return float(value) if value is not None else default
                except (ValueError, TypeError):
                    return default
            
            # Get top 10 for each metric with proper sorting
            tweets_top10 = sorted(
                performance_data, 
                key=lambda x: safe_number(x.get('tweets', 0)), 
                reverse=True
            )[:10]
            
            likes_top10 = sorted(
                performance_data, 
                key=lambda x: safe_number(x.get('likes', 0)), 
                reverse=True
            )[:10]
            
            views_top10 = sorted(
                performance_data, 
                key=lambda x: safe_number(x.get('views', 0)), 
                reverse=True
            )[:10]
            
            engagement_top10 = sorted(
                performance_data, 
                key=lambda x: safe_number(x.get('engagement_rate', 0)), 
                reverse=True
            )[:10]
            
            return {
                'tweets_count': {
                    'creators': [item.get('creator', '') for item in tweets_top10],
                    'values': [safe_number(item.get('tweets', 0)) for item in tweets_top10]
                },
                'likes_count': {
                    'creators': [item.get('creator', '') for item in likes_top10],
                    'values': [safe_number(item.get('likes', 0)) for item in likes_top10]
                },
                'views_count': {
                    'creators': [item.get('creator', '') for item in views_top10],
                    'values': [safe_number(item.get('views', 0)) for item in views_top10]
                },
                'engagement_rate': {
                    'creators': [item.get('creator', '') for item in engagement_top10],
                    # FIXED: Don't multiply by 100 again since engagement_rate is already a percentage
                    'values': [round(safe_number(item.get('engagement_rate', 0)), 1) for item in engagement_top10]
                }
            }
            
        except Exception as e:
            logger.error(f"Error transforming chart data: {str(e)}")
            return None
    
    def get_analysis_history(self, user_id: str, list_name: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get analysis history for a user"""
        try:
            analyses_ref = (self.db.collection('users')
                           .document(str(user_id))
                           .collection('creator_tracker')
                           .document('analyses')
                           .collection('results'))
            
            query = analyses_ref.order_by('timestamp', direction=firestore.Query.DESCENDING)
            
            if list_name:
                query = query.where('list_name', '==', list_name)
            
            query = query.limit(limit)
            docs = list(query.stream())
            
            analyses = []
            for doc in docs:
                data = doc.to_dict()
                
                # Handle timestamp
                timestamp_obj = data.get('timestamp')
                timestamp_str = ""
                if timestamp_obj:
                    if hasattr(timestamp_obj, 'seconds'):
                        timestamp_str = datetime.fromtimestamp(timestamp_obj.seconds).isoformat()
                    elif isinstance(timestamp_obj, datetime):
                        timestamp_str = timestamp_obj.isoformat()
                
                analyses.append({
                    'analysis_id': doc.id,
                    'list_name': data.get('list_name'),
                    'timestamp': {'seconds': timestamp_obj.seconds if hasattr(timestamp_obj, 'seconds') else 0},
                    'timestamp_str': timestamp_str,
                    'parameters': data.get('parameters', {}),
                    'creator_count': len(data.get('parameters', {}).get('analyzed_creators', [])),
                    'tweet_count': len(data.get('top_performing_tweets', []))
                })
            
            return analyses
            
        except Exception as e:
            logger.error(f"Error getting analysis history: {str(e)}")
            return []