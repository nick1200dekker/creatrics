"""
News Radar - Automated news ingestion, categorization, and scoring
"""
import os
import json
import hashlib
import logging
import feedparser
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from firebase_admin import firestore
from app.system.services.firebase_service import db
from app.system.ai_provider.ai_provider import get_ai_provider
from app.scripts.news_tracker.news_service import NewsService
from app.scripts.news_tracker.feed_service import FeedService

logger = logging.getLogger(__name__)

# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

# News feed sources
NEWS_FEEDS = [
    # News & Current Affairs
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",

    # Technology
    "https://www.wired.com/feed/rss",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.cnet.com/rss/news/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.engadget.com/rss.xml",
    "https://feeds.feedburner.com/thenextweb",

    # Crypto & Finance
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://www.theblock.co/rss.xml",
    "https://decrypt.co/feed",

    # Business & Finance
    "https://www.forbes.com/business/feed/",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",

    # Politics & World News
    "https://www.theguardian.com/world/rss",
    "https://www.theatlantic.com/feed/all/",
    "https://feeds.npr.org/1001/rss.xml",

    # Sports
    "https://feeds.bbci.co.uk/sport/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.skysports.com/rss/12040",

    # Entertainment
    "https://variety.com/feed/",
    "https://deadline.com/feed/",

    # Fashion & Beauty
    "https://www.vogue.com/feed/rss",
    "https://www.elle.com/rss/all.xml/",
    "https://www.allure.com/feed/rss",
    "https://www.refinery29.com/rss.xml",

    # Gaming & Esports
    "https://www.pcgamer.com/rss/",
    "https://www.polygon.com/rss/index.xml",
    "https://kotaku.com/rss",
    "https://www.vg247.com/feed/",
    "https://www.eurogamer.net/?format=rss",

    # Health & Wellness
    "https://www.statnews.com/feed/",

    # Science
    "https://www.space.com/feeds/all",
    "https://www.livescience.com/feeds/all",
    "https://www.popsci.com/feed/",
]

def load_prompt(filename: str) -> str:
    """Load a prompt from text file"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        raise

def generate_article_hash(title: str, link: str) -> str:
    """Generate unique hash for article to prevent duplicates"""
    content = f"{title}||{link}"
    return hashlib.md5(content.encode()).hexdigest()

class NewsRadarService:
    """Handles automated news ingestion, categorization, and scoring"""

    def __init__(self):
        if not db:
            raise Exception("Firestore not initialized")
        self.db = db
        self.news_service = NewsService()

    def fetch_all_news(self) -> List[Dict]:
        """Fetch news from all RSS feeds"""
        all_news = []

        for feed_url in NEWS_FEEDS:
            try:
                logger.info(f"Fetching from: {feed_url}")
                news_items = self.news_service.fetch_news(feed_url, limit=10)

                for item in news_items:
                    # Generate unique hash
                    item['article_hash'] = generate_article_hash(item['title'], item['link'])
                    item['feed_url'] = feed_url
                    all_news.append(item)

            except Exception as e:
                logger.error(f"Error fetching from {feed_url}: {e}")
                continue

        logger.info(f"Fetched {len(all_news)} total news items from {len(NEWS_FEEDS)} feeds")
        return all_news

    def check_article_exists(self, article_hash: str) -> bool:
        """Check if article already processed in Firestore"""
        try:
            doc_ref = self.db.collection('news_articles').document(article_hash)
            doc = doc_ref.get()
            return doc.exists
        except Exception as e:
            logger.error(f"Error checking article existence: {e}")
            return False

    def categorize_and_score_batch(self, articles: List[Dict]) -> Dict[int, Dict]:
        """Categorize multiple articles in a single AI call (batch processing)"""
        try:
            # Build article list for prompt
            articles_text = ""
            for idx, article in enumerate(articles):
                articles_text += f"\n[Article {idx}]\n"
                articles_text += f"Title: {article['title']}\n"
                articles_text += f"Description: {article.get('description', 'No description')}\n"
                articles_text += f"Source: {article['source']}\n"

            # Load batch prompt template
            batch_prompt = load_prompt('categorize_batch.txt')
            prompt = batch_prompt.format(articles=articles_text)

            ai_provider = get_ai_provider(
                script_name='news_tracker/news_ingestion',
                user_subscription=None
            )

            # Calculate max tokens: ~100 tokens per article for JSON response
            max_tokens = min(len(articles) * 100, 8000)

            logger.info(f"Batch categorizing {len(articles)} articles in single AI call...")

            # ASYNC AI call - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=max_tokens
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

            content = response.get('content', '').strip()

            # Try to parse JSON from response
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            results = json.loads(content)

            # Convert list to dict keyed by article_id
            categorizations = {}
            for result in results:
                article_id = result.get('article_id')
                if article_id is not None:
                    categorizations[article_id] = {
                        'category': result.get('category'),
                        'importance_score': result.get('importance_score'),
                        'reasoning': result.get('reasoning', '')
                    }

            logger.info(f"Successfully categorized {len(categorizations)}/{len(articles)} articles")
            return categorizations

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI batch response as JSON: {content[:500]}")
            logger.error(f"JSON error: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error in batch categorization: {e}", exc_info=True)
            return {}

    def save_article(self, article: Dict, categorization: Dict) -> bool:
        """Save processed article to Firestore"""
        try:
            article_hash = article['article_hash']

            doc_data = {
                'article_hash': article_hash,
                'title': article['title'],
                'link': article['link'],
                'description': article.get('description', ''),
                'published': article.get('published', ''),
                'source': article['source'],
                'image': article.get('image'),
                'feed_url': article['feed_url'],

                # AI categorization
                'category': categorization['category'],
                'importance_score': categorization['importance_score'],
                'reasoning': categorization.get('reasoning', ''),

                # Metadata
                'processed_at': firestore.SERVER_TIMESTAMP,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }

            # Save to Firestore
            self.db.collection('news_articles').document(article_hash).set(doc_data)
            logger.info(f"Saved article: {article['title'][:50]}... | Category: {categorization['category']} | Score: {categorization['importance_score']}")
            return True

        except Exception as e:
            logger.error(f"Error saving article: {e}", exc_info=True)
            return False

    def process_news_batch(self) -> Dict:
        """Main process: fetch, categorize, score, and save new articles"""
        logger.info("Starting news ingestion process...")

        stats = {
            'fetched': 0,
            'new': 0,
            'duplicate': 0,
            'categorized': 0,
            'failed': 0,
            'saved': 0
        }

        # Fetch all news
        all_news = self.fetch_all_news()
        stats['fetched'] = len(all_news)

        # Filter out duplicates FIRST (batch processing only new articles)
        new_articles = []
        for article in all_news:
            if self.check_article_exists(article['article_hash']):
                stats['duplicate'] += 1
            else:
                new_articles.append(article)
                stats['new'] += 1

        logger.info(f"Found {stats['new']} new articles (skipped {stats['duplicate']} duplicates)")

        if not new_articles:
            logger.info("No new articles to process")
            return stats

        # Process in batches of 30 articles (AI can handle this better)
        BATCH_SIZE = 30

        for batch_start in range(0, len(new_articles), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(new_articles))
            batch = new_articles[batch_start:batch_end]

            logger.info(f"Processing batch {batch_start}-{batch_end} ({len(batch)} articles)...")
            categorizations = self.categorize_and_score_batch(batch)

            logger.info(f"Successfully categorized {len(categorizations)}/{len(batch)} articles")

            # Save articles IMMEDIATELY after categorization
            for idx, cat in categorizations.items():
                try:
                    article = batch[idx]

                    if not cat:
                        logger.warning(f"No categorization for article {batch_start + idx}: {article['title'][:50]}")
                        stats['failed'] += 1
                        continue

                    stats['categorized'] += 1

                    # Save to database
                    if self.save_article(article, cat):
                        stats['saved'] += 1
                    else:
                        stats['failed'] += 1

                except Exception as e:
                    logger.error(f"Error saving article {batch_start + idx}: {e}")
                    stats['failed'] += 1
                    continue

            logger.info(f"Saved {stats['saved']}/{stats['categorized']} articles so far")

        # Cleanup old articles (older than 72 hours)
        logger.info("Cleaning up old articles...")
        feed_service = FeedService()
        cleanup_stats = feed_service.cleanup_old_articles(hours=72)
        stats['cleanup'] = cleanup_stats

        logger.info(f"News ingestion complete: {stats}")
        return stats

def run_news_ingestion():
    """Entry point for news ingestion process"""
    try:
        service = NewsRadarService()
        return service.process_news_batch()
    except Exception as e:
        logger.error(f"Fatal error in news ingestion: {e}", exc_info=True)
        return {'error': str(e)}
