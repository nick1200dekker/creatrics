"""
News Tracker Service - Fetch news and generate X posts
"""
import os
import requests
import feedparser
import logging
import html
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone
from time import mktime
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
                # Clean title: strip HTML tags and decode entities
                raw_title = entry.get('title', 'No title')
                # Remove HTML tags like <em>, <strong>, etc.
                soup_title = BeautifulSoup(raw_title, 'html.parser')
                clean_title = soup_title.get_text()
                # Decode HTML entities (&#8216; → ')
                title = html.unescape(clean_title)

                # Parse published date - feedparser normalizes to published_parsed (time tuple)
                published_date = ''
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        # Convert time tuple to ISO format datetime string
                        dt = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                        published_date = dt.isoformat()
                    except Exception as e:
                        logger.debug(f"Error parsing published_parsed: {e}")
                        published_date = entry.get('published', entry.get('pubDate', ''))
                else:
                    # Fallback to raw string if parsed version not available
                    published_date = entry.get('published', entry.get('pubDate', ''))

                # Extract source - for Google News, use the actual publisher from <source> tag
                source = feed.feed.get('title', 'Unknown')
                if hasattr(entry, 'source') and entry.source:
                    # Google News includes actual publisher in <source> tag
                    if hasattr(entry.source, 'title'):
                        source = entry.source.title
                    elif isinstance(entry.source, dict) and 'title' in entry.source:
                        source = entry.source['title']

                # Extract description for AI processing (not stored/displayed)
                # Clean HTML from description and truncate to 200 chars
                description = entry.get('description', entry.get('summary', ''))
                if description:
                    soup = BeautifulSoup(description, 'html.parser')
                    clean_text = soup.get_text().strip()
                    # Decode HTML entities in description too
                    clean_text = html.unescape(clean_text)
                    description = clean_text[:200] + '...' if len(clean_text) > 200 else clean_text

                # Extract image/thumbnail from RSS feed
                image_url = None

                # Method 1: Check for media:content or media:thumbnail (common in RSS 2.0)
                if hasattr(entry, 'media_content') and entry.media_content:
                    image_url = entry.media_content[0].get('url', '')
                elif hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                    image_url = entry.media_thumbnail[0].get('url', '')

                # Method 2: Check for enclosure tag (podcasts/media)
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.get('type', '').startswith('image/'):
                            image_url = enclosure.get('href', '')
                            break

                # Method 3: Parse content field HTML for img tags (used by The Verge, etc.)
                if not image_url and hasattr(entry, 'content') and entry.content:
                    content_html = entry.content[0].get('value', '')
                    if content_html:
                        content_soup = BeautifulSoup(content_html, 'html.parser')
                        img_tag = content_soup.find('img')
                        if img_tag and img_tag.get('src'):
                            image_url = img_tag.get('src')

                # Method 4: Parse description HTML for img tags (fallback)
                if not image_url and description:
                    desc_soup = BeautifulSoup(entry.get('description', entry.get('summary', '')), 'html.parser')
                    img_tag = desc_soup.find('img')
                    if img_tag and img_tag.get('src'):
                        image_url = img_tag.get('src')

                item = {
                    'title': title,
                    'link': entry.get('link', ''),
                    'description': description,  # Only for AI processing, not stored
                    'published': published_date,
                    'source': source,
                    'image_url': image_url,  # Thumbnail from RSS feed
                }

                news_items.append(item)

            logger.info(f"Fetched {len(news_items)} news items")
            return news_items

        except Exception as e:
            logger.error(f"Error fetching news: {e}", exc_info=True)
            raise

    def generate_x_post(self, news_url: str, news_title: str, news_summary: str, user_id: str) -> str:
        """
        Generate X post from news article

        Args:
            news_url: News article URL
            news_title: News article title
            news_summary: AI-generated summary
            user_id: User ID for AI provider

        Returns:
            Generated X post content
        """
        try:
            logger.info(f"Generating X post for article: {news_title}")

            content = news_summary if news_summary else news_title

            # Prepare prompt
            prompt = self.prompt_template.format(
                title=news_title,
                content=content
            )

            # Get AI provider with script name
            ai_provider = get_ai_provider(
                script_name='news_tracker/news_service',
                user_subscription=None  # Uses workspace owner's subscription
            )

            # Generate post using create_completion with messages format
            # ASYNC AI call - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=7000
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

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
