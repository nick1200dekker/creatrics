"""
List Manager - Handles both default and custom lists
"""
import logging
from typing import List, Dict, Optional
from .x_list_manager import XListManager

logger = logging.getLogger(__name__)

class ListManager:
    """Manager for Reply Guy lists (default and custom)"""
    
    def __init__(self):
        self.x_list_manager = XListManager()
    
    def fetch_x_list_accounts(self, x_list_id: str) -> Optional[List[str]]:
        """Fetch accounts from an X list"""
        try:
            return self.x_list_manager.get_all_list_members(x_list_id)
        except Exception as e:
            logger.error(f"Error fetching X list accounts: {str(e)}")
            return None
    
    def validate_account_list(self, accounts: List[str]) -> List[str]:
        """Validate and clean a list of account names"""
        valid_accounts = []
        
        for account in accounts:
            # Remove @ symbol if present
            clean_account = account.strip()
            if clean_account.startswith('@'):
                clean_account = clean_account[1:]
            
            # Basic validation - account name should be alphanumeric + underscore
            if clean_account and clean_account.replace('_', '').isalnum():
                valid_accounts.append(clean_account)
            else:
                logger.warning(f"Invalid account name: {account}")
        
        return valid_accounts
    
    def merge_account_lists(self, *account_lists: List[str]) -> List[str]:
        """Merge multiple account lists and remove duplicates"""
        merged = []
        seen = set()
        
        for account_list in account_lists:
            for account in account_list:
                if account not in seen:
                    merged.append(account)
                    seen.add(account)
        
        return merged
    
    def split_account_list(self, account_list: List[str], chunk_size: int = 50) -> List[List[str]]:
        """Split a large account list into smaller chunks for processing"""
        chunks = []
        for i in range(0, len(account_list), chunk_size):
            chunks.append(account_list[i:i + chunk_size])
        return chunks