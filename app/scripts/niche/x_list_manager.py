"""
X List Manager - Manages X (Twitter) lists integration
Updated for new app structure with environment variables
"""
import requests
import logging
from typing import List, Optional, Dict
import os

logger = logging.getLogger(__name__)

class XListManager:
    """Manager for X (Twitter) lists"""
    
    def __init__(self):
        # Get X API credentials from environment variables
        self.api_key = os.environ.get('X_RAPID_API_KEY')
        self.api_host = os.environ.get('X_RAPID_API_HOST', 'twitter-api45.p.rapidapi.com')
        
        if not self.api_key:
            logger.error("X_RAPID_API_KEY not found in environment variables")
            raise ValueError("X_RAPID_API_KEY environment variable is required")
    
    def fetch_list_members(self, list_id: str, cursor: Optional[str] = None) -> Optional[Dict]:
        """Fetch members of an X (Twitter) list"""
        url = f"https://{self.api_host}/list_members.php"
        
        querystring = {"list_id": list_id}
        if cursor:
            querystring["cursor"] = cursor
            
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host
        }
        
        try:
            logger.debug(f"Fetching X list members for list_id: {list_id}")
            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok':
                return data
            else:
                logger.error(f"API returned error status: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching X list: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error fetching X list: {str(e)}")
            return None
    
    def get_all_list_members(self, list_id: str) -> List[str]:
        """Fetch all members of an X list, handling pagination"""
        all_members = []
        cursor = None
        max_pages = 10  # Safety limit to prevent infinite loops
        page_count = 0
        
        while page_count < max_pages:
            # Fetch a page of members
            result = self.fetch_list_members(list_id, cursor)
            
            if not result or result.get('status') != 'ok':
                logger.error(f"Error fetching X list members: {result}")
                break
                
            # Add members to our list
            members = result.get('members', [])
            if members:
                screen_names = []
                for member in members:
                    screen_name = member.get('screen_name')
                    if screen_name:
                        screen_names.append(screen_name)
                
                all_members.extend(screen_names)
                logger.debug(f"Fetched {len(screen_names)} members from page {page_count + 1}")
            else:
                logger.debug("No members found in this page")
            
            # Check if there are more pages
            next_cursor = result.get('next_cursor')
            if not next_cursor or next_cursor == '0':
                logger.debug("No more pages to fetch")
                break
                
            cursor = next_cursor
            page_count += 1
        
        if page_count >= max_pages:
            logger.warning(f"Reached maximum page limit ({max_pages}) for list {list_id}")
        
        logger.info(f"Total members fetched for list {list_id}: {len(all_members)}")
        return all_members
    
    def validate_list_id(self, list_id: str) -> bool:
        """Validate if a list ID exists and is accessible"""
        try:
            result = self.fetch_list_members(list_id, None)
            return result is not None and result.get('status') == 'ok'
        except Exception as e:
            logger.error(f"Error validating list ID {list_id}: {str(e)}")
            return False