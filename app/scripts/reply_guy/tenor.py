"""
Tenor GIF Service for searching and retrieving GIFs
"""
import os
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class TenorService:
    """Service for interacting with Tenor GIF API"""

    def __init__(self):
        # Get API key from environment or use a working default
        self.api_key = os.getenv('TENOR_API_KEY')
        if not self.api_key:
            # Use a valid API key
            self.api_key = 'AIzaSyCJNKcn2rsj2RtCi0kQ_eAFSOmclbPT2VE'
        self.base_url = 'https://tenor.googleapis.com/v2'

    def search_gifs(self, query: str, limit: int = 8) -> Dict:
        """
        Search for GIFs on Tenor

        Args:
            query: Search query string
            limit: Number of results to return (default: 8, max: 50)

        Returns:
            Dictionary containing GIF results or error
        """
        try:
            # Ensure limit is within bounds
            limit = min(max(1, limit), 50)

            # Build the request
            params = {
                'q': query,
                'key': self.api_key,
                'limit': limit,
                'media_filter': 'minimal',  # Changed to minimal like in working example
                'contentfilter': 'medium'  # Safe content only
            }

            # Log the request for debugging
            logger.info(f"Searching Tenor for: {query} with key: {self.api_key[:10]}...")

            response = requests.get(
                f'{self.base_url}/search',
                params=params,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

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

                logger.info(f"Found {len(gifs)} GIFs for query: {query}")
                return {'gifs': gifs}

            else:
                logger.error(f"Tenor API error: {response.status_code}, Response: {response.text}")
                return {'gifs': [], 'error': f'API error: {response.status_code}'}

        except requests.exceptions.Timeout:
            logger.error("Tenor API request timed out")
            return {'gifs': [], 'error': 'Request timed out'}

        except requests.exceptions.RequestException as e:
            logger.error(f"Tenor API request failed: {str(e)}")
            return {'gifs': [], 'error': 'Failed to fetch GIFs'}

        except Exception as e:
            logger.error(f"Unexpected error in search_gifs: {str(e)}")
            return {'gifs': [], 'error': 'Internal error'}

    def get_trending_gifs(self, limit: int = 20) -> Dict:
        """
        Get trending GIFs from Tenor

        Args:
            limit: Number of results to return (default: 20, max: 50)

        Returns:
            Dictionary containing trending GIF results or error
        """
        try:
            limit = min(max(1, limit), 50)

            params = {
                'key': self.api_key,
                'limit': limit,
                'media_filter': 'minimal',
                'contentfilter': 'medium'
            }

            response = requests.get(
                f'{self.base_url}/featured',
                params=params,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

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

            else:
                logger.error(f"Tenor API error: {response.status_code}, Response: {response.text}")
                return {'gifs': [], 'error': f'API error: {response.status_code}'}

        except Exception as e:
            logger.error(f"Error getting trending GIFs: {str(e)}")
            return {'gifs': [], 'error': 'Failed to fetch trending GIFs'}