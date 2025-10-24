"""
News Tracker Service - Fetch news and generate X posts
"""
import os
import requests
import feedparser
import logging
from pathlib import Path
from typing import List, Dict, Optional
from app.system.ai_provider.ai_provider import get_ai_provider
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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

class NewsService:
    """Handles news fetching and X post generation"""

    def __init__(self):
        # Load prompt template
        self._load_prompt_template()

    def _load_prompt_template(self):
        """Load prompt template from prompt.txt file"""
        try:
            self.prompt_template = load_prompt('prompt.txt')
            logger.info("Prompt template loaded successfully from prompts/prompt.txt")
        except Exception as e:
            logger.error(f"Failed to load prompt template: {e}")
            # Fallback prompt
            self.prompt_template = """Create an engaging X (Twitter) post based on this news article.

NEWS TITLE: {title}

NEWS CONTENT:
{content}

Create a compelling X post that:
- Hooks the reader immediately
- Summarizes the key point concisely
- Adds value or insight
- Encourages engagement
- Fits within 280 characters (or uses a thread if needed)
- Uses a conversational, human tone
- No hashtags unless absolutely essential

Return ONLY the post content, nothing else."""

    def fetch_news(self, feed_url: str, limit: int = 20) -> List[Dict]:
        """
        Fetch news from RSS feed

        Args:
            feed_url: RSS feed URL
            limit: Maximum number of items to return

        Returns:
            List of news items with title, link, description, published date
        """
        try:
            logger.info(f"Fetching news from: {feed_url}")

            # Parse RSS feed
            feed = feedparser.parse(feed_url)

            if feed.bozo:
                logger.warning(f"Feed parsing warning: {feed.bozo_exception}")

            news_items = []
            for entry in feed.entries[:limit]:
                item = {
                    'title': entry.get('title', 'No title'),
                    'link': entry.get('link', ''),
                    'description': entry.get('description', entry.get('summary', '')),
                    'published': entry.get('published', entry.get('pubDate', '')),
                    'source': feed.feed.get('title', 'Unknown'),
                    'image': None
                }

                # Extract image/thumbnail - feedparser normalizes different RSS formats
                # Try media:thumbnail first (BBC, Wired, Forbes)
                if hasattr(entry, 'media_thumbnail') and len(entry.media_thumbnail) > 0:
                    item['image'] = entry.media_thumbnail[0].get('url')
                # Try media:content (CNN, some others)
                elif hasattr(entry, 'media_content') and len(entry.media_content) > 0:
                    item['image'] = entry.media_content[0].get('url')
                # Try enclosures
                elif hasattr(entry, 'enclosures') and len(entry.enclosures) > 0:
                    if entry.enclosures[0].get('type', '').startswith('image'):
                        item['image'] = entry.enclosures[0].get('href')

                # Clean HTML from description and truncate to 200 chars
                if item['description']:
                    soup = BeautifulSoup(item['description'], 'html.parser')
                    clean_text = soup.get_text().strip()
                    item['description'] = clean_text[:200] + '...' if len(clean_text) > 200 else clean_text

                news_items.append(item)

            logger.info(f"Fetched {len(news_items)} news items")
            return news_items

        except Exception as e:
            logger.error(f"Error fetching news: {e}", exc_info=True)
            raise

    def _fetch_article_content(self, url: str) -> str:
        """
        Fetch and extract main content from news article

        Args:
            url: Article URL

        Returns:
            Extracted article content
        """
        try:
            # Add headers to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()

            # Try to find main content
            # Common article content selectors
            article = soup.find('article') or soup.find('div', class_='article-body') or soup.find('div', class_='story-body')

            if article:
                text = article.get_text()
            else:
                # Fallback to body
                text = soup.body.get_text() if soup.body else soup.get_text()

            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            # Limit length
            max_length = 3000
            if len(text) > max_length:
                text = text[:max_length] + "..."

            return text

        except Exception as e:
            logger.error(f"Error fetching article content: {e}")
            return ""

    def generate_x_post(self, news_url: str, news_title: str, user_id: str) -> str:
        """
        Generate X post from news article

        Args:
            news_url: News article URL
            news_title: News article title
            user_id: User ID for AI provider

        Returns:
            Generated X post content
        """
        try:
            logger.info(f"Generating X post for article: {news_title}")

            # Fetch article content
            article_content = self._fetch_article_content(news_url)

            if not article_content:
                article_content = news_title

            # Prepare prompt
            prompt = self.prompt_template.format(
                title=news_title,
                content=article_content
            )

            # Get AI provider with script name
            ai_provider = get_ai_provider(
                script_name='news_tracker/news_service',
                user_subscription=None  # Uses workspace owner's subscription
            )

            # Generate post using create_completion with messages format
            response = ai_provider.create_completion(
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500
            )

            # Extract content and token usage from response
            post_content = response.get('content', '').strip()

            logger.info("X post generated successfully")

            # Return both content and token usage for credit deduction
            return {
                'content': post_content,
                'token_usage': response.get('usage', {}),
                'model': response.get('model'),
                'provider_enum': response.get('provider_enum')
            }

        except Exception as e:
            logger.error(f"Error generating X post: {e}", exc_info=True)
            raise
