"""
Tenor GIF Service for searching and retrieving GIFs
"""
import os
import requests
import logging
from typing import List, Dict, Optional
import time
from threading import Lock

logger = logging.getLogger(__name__)

class TenorService:
    """Service for interacting with Tenor GIF API with automatic key rotation"""

    def __init__(self):
        # Load all available API keys
        self.api_keys = []
        self.current_key_index = 0
        self.key_lock = Lock()

        # Track failed keys and their retry times
        self.failed_keys = {}  # key_index: retry_after_timestamp

        # Load primary key and additional keys
        primary_key = os.getenv('TENOR_API_KEY')
        if primary_key:
            self.api_keys.append(primary_key)

        # Load additional keys (TENOR_API_KEY2 through TENOR_API_KEY5)
        for i in range(2, 6):
            key = os.getenv(f'TENOR_API_KEY{i}')
            if key:
                self.api_keys.append(key)

        if not self.api_keys:
            logger.warning("No TENOR_API_KEY found in environment variables. GIF search will not work.")
        else:
            logger.info(f"Loaded {len(self.api_keys)} Tenor API keys for rotation")

        self.base_url = 'https://tenor.googleapis.com/v2'

    def _get_next_available_key(self):
        """Get the next available API key that isn't rate-limited"""
        with self.key_lock:
            if not self.api_keys:
                return None

            current_time = time.time()
            attempts = 0

            while attempts < len(self.api_keys):
                # Check if current key is in cooldown
                if self.current_key_index in self.failed_keys:
                    retry_after = self.failed_keys[self.current_key_index]
                    if current_time < retry_after:
                        # Still in cooldown, try next key
                        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                        attempts += 1
                        continue
                    else:
                        # Cooldown expired, remove from failed keys
                        del self.failed_keys[self.current_key_index]

                # Return current key
                key = self.api_keys[self.current_key_index]
                return key, self.current_key_index

            # All keys are rate-limited
            logger.warning("All Tenor API keys are currently rate-limited")
            return None, None

    def _mark_key_failed(self, key_index, cooldown_seconds=1):
        """Mark a key as failed and put it in cooldown"""
        with self.key_lock:
            self.failed_keys[key_index] = time.time() + cooldown_seconds
            # Move to next key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.info(f"Tenor API key {key_index + 1} rate-limited, rotating to key {self.current_key_index + 1}")

    def _make_request_with_rotation(self, endpoint, params, max_retries=None):
        """Make a request with automatic key rotation on rate limit"""
        if max_retries is None:
            max_retries = len(self.api_keys)

        last_error = None
        attempts = 0

        while attempts < max_retries:
            key_info = self._get_next_available_key()
            if not key_info or key_info[0] is None:
                # No keys available
                if last_error:
                    return None, last_error
                return None, "All API keys are rate-limited"

            api_key, key_index = key_info

            # Add key to params
            request_params = params.copy()
            request_params['key'] = api_key

            try:
                response = requests.get(
                    f'{self.base_url}/{endpoint}',
                    params=request_params,
                    timeout=5
                )

                if response.status_code == 200:
                    # Success!
                    return response.json(), None
                elif response.status_code == 429:
                    # Rate limited - mark key as failed and try next
                    logger.warning(f"Tenor API key {key_index + 1} rate limited (429)")
                    self._mark_key_failed(key_index, cooldown_seconds=1)
                    last_error = f"Rate limited (attempt {attempts + 1}/{max_retries})"
                    attempts += 1
                    continue
                else:
                    # Other error - might be temporary, try next key
                    logger.error(f"Tenor API error with key {key_index + 1}: {response.status_code}")
                    self._mark_key_failed(key_index, cooldown_seconds=0.5)
                    last_error = f"API error: {response.status_code}"
                    attempts += 1
                    continue

            except requests.exceptions.Timeout:
                logger.error(f"Tenor API request timed out with key {key_index + 1}")
                last_error = "Request timed out"
                attempts += 1
                continue

            except requests.exceptions.RequestException as e:
                logger.error(f"Tenor API request failed with key {key_index + 1}: {str(e)}")
                last_error = f"Request failed: {str(e)}"
                attempts += 1
                continue

        return None, last_error or "Failed after all retries"

    def search_gifs(self, query: str, limit: int = 8) -> Dict:
        """
        Search for GIFs on Tenor with automatic API key rotation

        Args:
            query: Search query string
            limit: Number of results to return (default: 8, max: 50)

        Returns:
            Dictionary containing GIF results or error
        """
        if not self.api_keys:
            return {'gifs': [], 'error': 'Tenor API key not configured'}

        try:
            # Ensure limit is within bounds
            limit = min(max(1, limit), 50)

            # Build the request parameters (without key, will be added by rotation method)
            params = {
                'q': query,
                'limit': limit,
                'media_filter': 'minimal',  # Changed to minimal like in working example
                'contentfilter': 'medium'  # Safe content only
            }

            # Make request with automatic key rotation
            data, error = self._make_request_with_rotation('search', params)

            if error:
                logger.error(f"Failed to search GIFs after key rotation: {error}")
                return {'gifs': [], 'error': error}

            if data:
                # Format the results
                gifs = []
                for result in data.get('results', []):
                    media_formats = result.get('media_formats', {})

                    # Get the GIF URL from media_formats
                    gif_url = media_formats.get('gif', {}).get('url')
                    preview_url = media_formats.get('tinygif', {}).get('url') or gif_url

                    gif_data = {
                        'id': result.get('id'),
                        'title': result.get('content_description', '') or result.get('title', ''),
                        'url': gif_url,  # Full GIF URL
                        'preview_url': preview_url,  # Preview URL (tinygif or fallback to full)
                        'gif': gif_url,
                        'mp4': media_formats.get('mp4', {}).get('url'),
                        'width': media_formats.get('gif', {}).get('dims', [0])[0] if media_formats.get('gif', {}).get('dims') else 0,
                        'height': media_formats.get('gif', {}).get('dims', [0, 0])[1] if media_formats.get('gif', {}).get('dims') and len(media_formats.get('gif', {}).get('dims', [])) > 1 else 0
                    }

                    # Only add if we have at least a GIF URL
                    if gif_url:
                        gifs.append(gif_data)

                return {'gifs': gifs}

            return {'gifs': [], 'error': 'No data received'}

        except Exception as e:
            logger.error(f"Unexpected error in search_gifs: {str(e)}")
            return {'gifs': [], 'error': 'Internal error'}

    def get_trending_gifs(self, limit: int = 20) -> Dict:
        """
        Get trending GIFs from Tenor with automatic API key rotation

        Args:
            limit: Number of results to return (default: 20, max: 50)

        Returns:
            Dictionary containing trending GIF results or error
        """
        if not self.api_keys:
            return {'gifs': [], 'error': 'Tenor API key not configured'}

        try:
            limit = min(max(1, limit), 50)

            # Build the request parameters (without key, will be added by rotation method)
            params = {
                'limit': limit,
                'media_filter': 'minimal',
                'contentfilter': 'medium'
            }

            # Make request with automatic key rotation
            data, error = self._make_request_with_rotation('featured', params)

            if error:
                logger.error(f"Failed to get trending GIFs after key rotation: {error}")
                return {'gifs': [], 'error': error}

            if data:
                gifs = []
                for result in data.get('results', []):
                    media_formats = result.get('media_formats', {})

                    # Get the GIF URL from media_formats
                    gif_url = media_formats.get('gif', {}).get('url')
                    preview_url = media_formats.get('tinygif', {}).get('url') or gif_url

                    gif_data = {
                        'id': result.get('id'),
                        'title': result.get('content_description', '') or result.get('title', ''),
                        'url': gif_url,
                        'preview_url': preview_url,
                        'gif': gif_url,
                        'mp4': media_formats.get('mp4', {}).get('url')
                    }

                    if gif_url:
                        gifs.append(gif_data)

                return {'gifs': gifs}

            return {'gifs': [], 'error': 'No data received'}

        except Exception as e:
            logger.error(f"Error getting trending GIFs: {str(e)}")
            return {'gifs': [], 'error': 'Failed to fetch trending GIFs'}