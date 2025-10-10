"""
X Content Suggestions Module
Analyzes user's last 25 X posts and generates personalized content suggestions
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class XContentSuggestions:
    """Generate personalized X post suggestions based on user's recent posts"""

    def __init__(self):
        self.max_posts_to_analyze = 25

    def get_user_posts(self, user_id: str) -> List[Dict]:
        """Fetch user's last 25 posts from Firebase"""
        try:
            from firebase_admin import firestore
            db = firestore.client()

            # Get posts from x_posts/timeline collection
            posts_ref = db.collection('users').document(str(user_id)).collection('x_posts').document('timeline')
            posts_doc = posts_ref.get()

            if not posts_doc.exists:
                logger.info(f"No X posts found for user {user_id}")
                return []

            posts_data = posts_doc.to_dict()
            posts = posts_data.get('posts', [])

            if not posts:
                logger.info(f"No posts in X timeline for user {user_id}")
                return []

            # Sort by created_at or views to get most recent/relevant posts
            sorted_posts = sorted(posts, key=lambda x: x.get('created_at', ''), reverse=True)

            # Get last 25 posts
            recent_posts = sorted_posts[:self.max_posts_to_analyze]

            logger.info(f"Retrieved {len(recent_posts)} posts for user {user_id}")
            return recent_posts

        except Exception as e:
            logger.error(f"Error fetching user posts: {e}")
            return []

    def format_posts_for_analysis(self, posts: List[Dict]) -> str:
        """Format posts into a string for AI analysis"""
        try:
            formatted = "=== USER'S RECENT POSTS ===\n\n"

            for i, post in enumerate(posts, 1):
                post_text = post.get('text', '').strip()
                views = post.get('views', 0)
                likes = post.get('likes', 0)
                replies = post.get('replies', 0)
                retweets = post.get('retweets', 0)

                if post_text:
                    # Clean URLs for better analysis
                    import re
                    clean_text = re.sub(r'https?://\S+', '[LINK]', post_text)

                    formatted += f"Post {i}:\n"
                    formatted += f"{clean_text}\n"
                    formatted += f"(👁️ {views:,} views | ❤️ {likes} likes | 💬 {replies} replies | 🔁 {retweets} retweets)\n\n"

            return formatted

        except Exception as e:
            logger.error(f"Error formatting posts: {e}")
            return ""

    def get_cached_suggestions(self, user_id: str) -> Optional[Dict]:
        """Get cached suggestions from Firebase if they exist and are < 24 hours old"""
        try:
            from firebase_admin import firestore
            from datetime import timezone

            db = firestore.client()
            cache_ref = db.collection('users').document(str(user_id)).collection('x_content_suggestions').document('cache')
            cache_doc = cache_ref.get()

            if not cache_doc.exists:
                logger.info(f"No cached suggestions found for user {user_id}")
                return None

            cache_data = cache_doc.to_dict()
            cached_at = cache_data.get('cached_at')

            if not cached_at:
                return None

            # Convert Firestore timestamp to datetime
            if hasattr(cached_at, 'timestamp'):
                cached_datetime = datetime.fromtimestamp(cached_at.timestamp(), tz=timezone.utc)
            else:
                cached_datetime = datetime.fromisoformat(str(cached_at))

            # Check if cache is less than 24 hours old
            now = datetime.now(timezone.utc)
            age_hours = (now - cached_datetime).total_seconds() / 3600

            if age_hours < 24:
                logger.info(f"Using cached suggestions for user {user_id} (age: {age_hours:.1f} hours)")
                return {
                    'success': True,
                    'suggestions': cache_data.get('suggestions', []),
                    'cached': True,
                    'cached_at': cached_datetime.isoformat(),
                    'age_hours': round(age_hours, 1)
                }
            else:
                logger.info(f"Cache expired for user {user_id} (age: {age_hours:.1f} hours)")
                return None

        except Exception as e:
            logger.error(f"Error getting cached suggestions: {e}")
            return None

    def save_suggestions_to_cache(self, user_id: str, suggestions: List[Dict]) -> bool:
        """Save suggestions to Firebase cache"""
        try:
            from firebase_admin import firestore

            db = firestore.client()
            cache_ref = db.collection('users').document(str(user_id)).collection('x_content_suggestions').document('cache')

            cache_data = {
                'suggestions': suggestions,
                'cached_at': datetime.now(),
                'user_id': str(user_id)
            }

            cache_ref.set(cache_data)
            logger.info(f"Saved {len(suggestions)} suggestions to cache for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving suggestions to cache: {e}")
            return False

    def generate_suggestions(self, user_id: str, force_refresh: bool = False) -> Dict:
        """
        Generate 5 content suggestions based on user's recent posts

        Args:
            user_id: User ID
            force_refresh: If True, bypass cache and generate new suggestions

        Returns:
            Dict with success status, suggestions, and token usage
        """
        try:
            # Check cache first unless force refresh
            if not force_refresh:
                cached = self.get_cached_suggestions(user_id)
                if cached:
                    return cached

            # Get user's recent posts
            posts = self.get_user_posts(user_id)

            if not posts or len(posts) < 5:
                return {
                    'success': False,
                    'error': 'Not enough posts to analyze. Connect your X account and ensure you have at least 5 posts.',
                    'suggestions': []
                }

            # Format posts for AI analysis
            posts_context = self.format_posts_for_analysis(posts)

            if not posts_context:
                return {
                    'success': False,
                    'error': 'Unable to process posts for analysis',
                    'suggestions': []
                }

            # Create the AI prompt
            prompt = self._build_analysis_prompt(posts_context)

            # Get AI provider
            ai_provider = get_ai_provider()

            # Generate suggestions
            response = ai_provider.create_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert X (Twitter) content strategist who analyzes posting patterns and generates viral content ideas."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=1500
            )

            # Parse the response
            suggestions = self._parse_suggestions(response.get('content', ''))

            if not suggestions or len(suggestions) < 5:
                return {
                    'success': False,
                    'error': 'Unable to generate enough suggestions',
                    'suggestions': []
                }

            # Save to cache
            self.save_suggestions_to_cache(user_id, suggestions[:5])

            return {
                'success': True,
                'suggestions': suggestions[:5],  # Return exactly 5
                'cached': False,
                'token_usage': {
                    'input_tokens': response.get('usage', {}).get('input_tokens', 0),
                    'output_tokens': response.get('usage', {}).get('output_tokens', 0),
                    'model': response.get('provider', 'unknown')
                }
            }

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {
                'success': False,
                'error': str(e),
                'suggestions': []
            }

    def _build_analysis_prompt(self, posts_context: str) -> str:
        """Build the AI prompt for content analysis"""
        prompt = f"""Analyze the following X posts from a content creator and generate 5 highly engaging content suggestions they should post today.

{posts_context}

Based on these posts, identify:
1. The creator's niche and main topics
2. Their EXACT writing style (tone, formatting, sentence structure, paragraph breaks, emoji usage, capitalization patterns)
3. What type of content gets the most engagement
4. Patterns in their successful posts

CRITICAL: You must PERFECTLY MIMIC their writing style. Study:
- How they structure sentences (short vs long)
- How they use line breaks and spacing
- Their punctuation patterns
- Their emoji placement and frequency
- Their capitalization style
- Their energy level and tone
- Their use of questions, statements, or calls-to-action

Now generate EXACTLY 5 content suggestions that:
- Match their EXACT writing style (this is most important)
- Stay within their niche but explore fresh angles/ideas
- Are timely and relevant for TODAY
- Have viral potential based on their past performance
- Are specific enough to post immediately (not just topics)
- Cover different aspects/angles within their niche
- Sound EXACTLY like they wrote it themselves

Each suggestion should feel like it came directly from this creator - same voice, same rhythm, same formatting.

Format your response as a JSON array with exactly 5 objects, each containing:
- "title": A catchy 3-5 word title for the suggestion
- "content": The actual post text (ready to publish, 100-280 characters)
- "reason": Why this will perform well (1 sentence)
- "hook_type": The type of hook used (question/stat/story/hot_take/thread)

Example format:
[
  {{
    "title": "Growth Mindset Insight",
    "content": "Most people want results without the struggle.\n\nBut the struggle IS the result.\n\nIt's where you build the character needed to keep what you earn.",
    "reason": "Philosophical insights matching your tone perform well with your audience",
    "hook_type": "hot_take"
  }}
]

Return ONLY the JSON array, no other text."""

        return prompt

    def _parse_suggestions(self, ai_response: str) -> List[Dict]:
        """Parse AI response into structured suggestions"""
        try:
            import json
            import re

            # Try to extract JSON from response
            # Remove markdown code blocks if present
            cleaned = ai_response.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*\n', '', cleaned)
                cleaned = re.sub(r'\n```\s*$', '', cleaned)

            # Parse JSON
            suggestions = json.loads(cleaned)

            # Validate structure
            if not isinstance(suggestions, list):
                logger.error("Response is not a list")
                return []

            validated_suggestions = []
            for suggestion in suggestions:
                if isinstance(suggestion, dict) and all(k in suggestion for k in ['title', 'content', 'reason', 'hook_type']):
                    validated_suggestions.append(suggestion)

            logger.info(f"Parsed {len(validated_suggestions)} valid suggestions")
            return validated_suggestions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {ai_response}")
            return []
        except Exception as e:
            logger.error(f"Error parsing suggestions: {e}")
            return []

    def has_sufficient_data(self, user_id: str) -> bool:
        """Check if user has enough posts for suggestions"""
        try:
            posts = self.get_user_posts(user_id)
            return len(posts) >= 5
        except Exception as e:
            logger.error(f"Error checking data sufficiency: {e}")
            return False
