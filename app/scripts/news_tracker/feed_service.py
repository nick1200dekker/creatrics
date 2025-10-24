"""
News Radar Feed Service - Personalized news feeds and category management
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from firebase_admin import firestore
from app.system.services.firebase_service import db

logger = logging.getLogger(__name__)

# Available news categories
NEWS_CATEGORIES = [
    'Tech & AI',
    'Crypto & Finance',
    'Sports & Fitness',
    'Gaming & Esports',
    'Entertainment & Culture',
    'Politics & World',
    'Science & Innovation',
    'Business & Startups',
    'Health & Wellness',
    'Climate & Environment'
]

class FeedService:
    """Handles personalized news feeds and user preferences"""

    def __init__(self):
        if not db:
            raise Exception("Firestore not initialized")
        self.db = db

    def get_user_subscriptions(self, user_id: str) -> List[str]:
        """Get user's subscribed categories"""
        try:
            doc_ref = self.db.collection('users').document(user_id)
            doc = doc_ref.get()

            if doc.exists:
                user_data = doc.to_dict()
                subscriptions = user_data.get('news_subscriptions', [])
                # Default to all categories if none set
                return subscriptions if subscriptions else NEWS_CATEGORIES
            else:
                return NEWS_CATEGORIES

        except Exception as e:
            logger.error(f"Error getting subscriptions: {e}")
            return NEWS_CATEGORIES

    def update_user_subscriptions(self, user_id: str, categories: List[str]) -> bool:
        """Update user's category subscriptions"""
        try:
            doc_ref = self.db.collection('users').document(user_id)
            doc_ref.set({
                'news_subscriptions': categories,
                'news_subscriptions_updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)

            logger.info(f"Updated subscriptions for user {user_id}: {categories}")
            return True

        except Exception as e:
            logger.error(f"Error updating subscriptions: {e}")
            return False

    def calculate_feed_score(self, article: Dict) -> float:
        """
        Calculate feed score based on importance and recency

        Formula: (importance_score * 10) + (recency_bonus)
        - importance_score: 1-10 from AI
        - recency_bonus: 0-50 based on age
          - Last hour: +50
          - Last 6 hours: +40
          - Last 24 hours: +30
          - Last 3 days: +20
          - Last week: +10
          - Older: +0
        """
        try:
            importance = article.get('importance_score')
            if importance is None:
                importance = 5  # Default importance if missing

            # Parse published date
            published_str = article.get('created_at') or article.get('published', '')
            if not published_str:
                return importance * 10  # No recency bonus if no date

            # Parse ISO format datetime
            try:
                published = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            except:
                return importance * 10

            # Calculate age
            now = datetime.now(timezone.utc)
            age = now - published

            # Recency bonus
            if age <= timedelta(hours=1):
                recency_bonus = 50
            elif age <= timedelta(hours=6):
                recency_bonus = 40
            elif age <= timedelta(hours=24):
                recency_bonus = 30
            elif age <= timedelta(days=3):
                recency_bonus = 20
            elif age <= timedelta(days=7):
                recency_bonus = 10
            else:
                recency_bonus = 0

            score = (importance * 10) + recency_bonus
            return score

        except Exception as e:
            logger.error(f"Error calculating feed score: {e}")
            return 50  # Return default score on error

    def get_personalized_feed(self, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Get personalized 'For You' feed based on user's category subscriptions
        Sorted by feed score (importance + recency)

        Note: Fetches ALL articles and filters in-memory (no Firestore indexes needed)
        """
        try:
            # Get user's subscribed categories
            subscriptions = self.get_user_subscriptions(user_id)

            # Fetch ALL articles from Firestore (no indexes needed)
            articles_ref = self.db.collection('news_articles')
            all_docs = articles_ref.stream()

            all_articles = []
            for doc in all_docs:
                article = doc.to_dict()

                # Filter by subscribed categories in-memory
                if article.get('category') in subscriptions:
                    article['id'] = doc.id
                    article['feed_score'] = self.calculate_feed_score(article)
                    all_articles.append(article)

            # Sort by feed score (highest first) in-memory
            all_articles.sort(key=lambda x: x['feed_score'], reverse=True)

            # Return top articles
            return all_articles[:limit]

        except Exception as e:
            logger.error(f"Error getting personalized feed: {e}", exc_info=True)
            return []

    def get_category_feed(self, category: str, limit: int = 50) -> List[Dict]:
        """
        Get articles for a specific category
        Sorted by importance score

        Note: Fetches ALL articles and filters in-memory (no Firestore indexes needed)
        """
        try:
            articles_ref = self.db.collection('news_articles')
            all_docs = articles_ref.stream()

            articles = []
            for doc in all_docs:
                article = doc.to_dict()

                # Filter by category in-memory
                if article.get('category') == category:
                    article['id'] = doc.id
                    article['feed_score'] = self.calculate_feed_score(article)
                    articles.append(article)

            # Sort by importance score in-memory
            articles.sort(key=lambda x: x.get('importance_score', 0), reverse=True)

            return articles[:limit]

        except Exception as e:
            logger.error(f"Error getting category feed: {e}", exc_info=True)
            return []

    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        return NEWS_CATEGORIES.copy()

    def cleanup_old_articles(self, hours: int = 72) -> Dict:
        """
        Delete articles older than specified hours (default 72 hours)
        Returns stats about deletion
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            logger.info(f"Cleaning up articles older than {hours} hours (cutoff: {cutoff_time})")

            articles_ref = self.db.collection('news_articles')
            all_docs = articles_ref.stream()

            deleted_count = 0
            kept_count = 0

            for doc in all_docs:
                article = doc.to_dict()
                created_at_str = article.get('created_at') or article.get('published', '')

                if not created_at_str:
                    # Keep articles without timestamp (shouldn't happen)
                    kept_count += 1
                    continue

                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

                    if created_at < cutoff_time:
                        # Delete old article
                        doc.reference.delete()
                        deleted_count += 1
                        logger.debug(f"Deleted old article: {article.get('title', 'Unknown')[:50]}")
                    else:
                        kept_count += 1

                except Exception as e:
                    logger.error(f"Error parsing date for article {doc.id}: {e}")
                    kept_count += 1
                    continue

            stats = {
                'deleted': deleted_count,
                'kept': kept_count,
                'cutoff_hours': hours,
                'cutoff_time': cutoff_time.isoformat()
            }

            logger.info(f"Cleanup complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error cleaning up old articles: {e}", exc_info=True)
            return {'error': str(e), 'deleted': 0, 'kept': 0}
