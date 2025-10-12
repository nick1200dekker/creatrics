"""
YouTube Keyword Research System
Extracts main topics from content and gets real YouTube autocomplete suggestions
"""

import os
import re
import requests
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class KeywordResearcher:
    """
    Researches YouTube keywords by:
    1. Using AI to extract 3 main topics from content (minimal tokens)
    2. Getting YouTube autocomplete suggestions for each topic (free API)
    3. Returning structured keyword data for optimization
    """

    def __init__(self):
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
        self.rapidapi_host = "yt-api.p.rapidapi.com"

    def extract_topics_with_ai(self, content: str, ai_provider) -> List[str]:
        """
        Use AI to extract 3 main search topics from content
        This is a TINY AI call - very few tokens
        """
        # Ultra-compact prompt to minimize tokens
        content_preview = content[:500]

        prompt = f"""Extract exactly 3 DIVERSE YouTube search terms from this content.

Content: {content_preview}

Return ONLY 3 search terms, one per line (NO numbering, NO bullet points):

Line 1: BROAD main topic ONLY (1-3 words maximum, just the core subject)
   Examples: "Clash Royale" NOT "Clash Royale Best Deck"
             "Pokemon TCG" NOT "Pokemon TCG Meta Decks"
             "iPhone 16" NOT "iPhone 16 Review"

Line 2: Main topic + ONE specific modifier (best/how to/tutorial/tips/vs/review)

Line 3: Main topic + DIFFERENT modifier (beginner/guide/explained/comparison/year)

Make lines 2 and 3 use DIFFERENT modifiers for diversity.

Correct Examples:
Clash Royale
Clash Royale Best Deck
Clash Royale Beginner Guide

Pokemon TCG
Pokemon TCG Meta Decks
Pokemon TCG Tutorial

iPhone 16
iPhone 16 Review
iPhone 16 vs iPhone 15

Wrong Examples (Line 1 is too specific):
❌ Clash Royale Best Deck (too specific, should be just "Clash Royale")
❌ Pokemon TCG Meta Decks (too specific, should be just "Pokemon TCG")
❌ iPhone 16 Review (too specific, should be just "iPhone 16")

Now extract 3 DIVERSE search terms:"""

        system_prompt = "You extract YouTube search keywords. Be concise."

        logger.info("=" * 80)
        logger.info("KEYWORD RESEARCH - STEP 1: AI Topic Extraction")
        logger.info("=" * 80)
        logger.info(f"INPUT TO AI (first 500 chars of content):")
        logger.info(f"{content_preview}")
        logger.info("-" * 80)
        logger.info(f"PROMPT SENT TO AI:")
        logger.info(f"{prompt}")
        logger.info("-" * 80)

        try:
            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,  # Only need 3 short lines
                temperature=0.7
            )

            # Handle different response formats
            if isinstance(response, dict):
                # Check for 'content' key with array
                if 'content' in response and isinstance(response['content'], list):
                    ai_response_text = response['content'][0]['text'].strip()
                # Check for direct text in 'content'
                elif 'content' in response and isinstance(response['content'], str):
                    ai_response_text = response['content'].strip()
                else:
                    ai_response_text = str(response).strip()
            else:
                ai_response_text = str(response).strip()

            logger.info(f"AI RESPONSE:")
            logger.info(f"{ai_response_text}")
            logger.info("-" * 80)

            # Parse the 3 lines
            topics = ai_response_text.split('\n')
            topics = [t.strip() for t in topics if t.strip()][:3]

            # Clean topics: remove any numbering, bullet points, or prefixes
            cleaned_topics = []
            for topic in topics:
                # Remove common prefixes like "1.", "1)", "•", "-", "Line 1:", etc.
                cleaned = re.sub(r'^[\d\.\)\-\•\*]+\s*', '', topic.strip())
                cleaned = re.sub(r'^Line\s*\d+:\s*', '', cleaned, flags=re.IGNORECASE)
                cleaned = cleaned.strip()
                if cleaned:
                    cleaned_topics.append(cleaned)

            # Ensure we have 3 topics
            while len(cleaned_topics) < 3:
                cleaned_topics.append(cleaned_topics[0] if cleaned_topics else "YouTube")

            logger.info(f"EXTRACTED TOPICS: {cleaned_topics}")
            logger.info("=" * 80)
            return cleaned_topics[:3]

        except Exception as e:
            logger.error(f"Error extracting topics with AI: {e}")
            # Fallback: use first few words of content
            words = content.split()[:3]
            main = ' '.join(words)
            fallback_topics = [main, f"{main} best", f"{main} beginner"]
            logger.info(f"FALLBACK TOPICS: {fallback_topics}")
            logger.info("=" * 80)
            return fallback_topics

    def get_autocomplete_suggestions(self, query: str, geo: str = "US") -> List[str]:
        """Get YouTube autocomplete suggestions for a search term"""
        try:
            url = f"https://{self.rapidapi_host}/suggest_queries"
            headers = {
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": self.rapidapi_host,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            params = {
                "query": query,
                "geo": geo
            }

            logger.info(f"Fetching YouTube autocomplete for: '{query}'")
            response = requests.get(url, headers=headers, params=params, timeout=10)

            # Check for rate limit or auth errors
            if response.status_code == 429:
                logger.warning(f"⚠️  Rate limit hit for '{query}' - skipping autocomplete for this topic")
                return []
            elif response.status_code == 401:
                logger.warning(f"⚠️  API authentication failed for '{query}' - check RapidAPI key")
                return []

            response.raise_for_status()

            data = response.json()
            suggestions = data.get('suggestions', [])

            logger.info(f"✓ Got {len(suggestions)} suggestions for '{query}': {suggestions[:5]}...")
            return suggestions[:10]  # Top 10

        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️  Could not fetch autocomplete for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error getting autocomplete for '{query}': {e}")
            return []

    def research_keywords(self, content: str, ai_provider) -> Dict:
        """
        Complete keyword research flow:
        1. AI extracts 3 topics (minimal tokens)
        2. Get autocomplete for each topic (free API)
        3. Return structured data
        """
        logger.info("\n" + "🔍 " + "=" * 78)
        logger.info("STARTING YOUTUBE KEYWORD RESEARCH")
        logger.info("=" * 80 + "\n")

        # Step 1: AI extracts 3 topics (uses ~50-100 tokens)
        topics = self.extract_topics_with_ai(content, ai_provider)

        # Step 2: Get autocomplete suggestions for each topic (FREE, no tokens)
        logger.info("\n" + "=" * 80)
        logger.info("KEYWORD RESEARCH - STEP 2: YouTube Autocomplete API")
        logger.info("=" * 80)

        keyword_data = {
            'main_topic': topics[0],
            'topics': topics,
            'suggestions': {}
        }

        for topic in topics:
            suggestions = self.get_autocomplete_suggestions(topic)
            keyword_data['suggestions'][topic] = suggestions

        total_keywords = sum(len(s) for s in keyword_data['suggestions'].values())

        logger.info("\n" + "=" * 80)
        logger.info("KEYWORD RESEARCH COMPLETE - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Main Topic: {keyword_data['main_topic']}")
        logger.info(f"Total Keywords Discovered: {total_keywords}")

        if total_keywords > 0:
            for topic, suggestions in keyword_data['suggestions'].items():
                if suggestions:
                    logger.info(f"\n'{topic}' -> {len(suggestions)} suggestions")
                    logger.info(f"  Top 5: {suggestions[:5]}")
        else:
            logger.warning("⚠️  No autocomplete data available (API limits or errors)")
            logger.info("💡 Will still use extracted topics for optimization")

        logger.info("=" * 80 + "\n")

        return keyword_data

    def format_for_prompt(self, keyword_data: Dict) -> str:
        """
        Format keyword research as compact text for AI prompts
        This gets added to title/description/tags generation prompts
        """
        if not keyword_data:
            return ""

        # Check if we have any suggestions
        has_suggestions = any(keyword_data.get('suggestions', {}).values())

        if has_suggestions:
            # Full keyword data with autocomplete suggestions
            text = f"KEYWORD RESEARCH (use these in your optimization):\n"
            text += f"Main Topic: {keyword_data['main_topic']}\n\n"
            text += "Popular YouTube Searches:\n"

            for topic, suggestions in keyword_data['suggestions'].items():
                if suggestions:
                    text += f"\n'{topic}':\n"
                    # Include all suggestions (we get 10 from API)
                    for i, suggestion in enumerate(suggestions, 1):
                        text += f"  {i}. {suggestion}\n"

            text += "\nIMPORTANT: Use these EXACT phrases that people actually search for.\n"
        else:
            # Only have extracted topics, no autocomplete data
            text = f"TOPIC FOCUS (optimize around these):\n"
            text += f"Main Topic: {keyword_data['main_topic']}\n"
            if keyword_data.get('topics'):
                text += "Related Topics:\n"
                for i, topic in enumerate(keyword_data['topics'], 1):
                    text += f"  {i}. {topic}\n"
            text += "\nIMPORTANT: Optimize content around these topics for discoverability.\n"

        logger.info("\n" + "=" * 80)
        logger.info("KEYWORD PROMPT BEING ADDED TO AI:")
        logger.info("=" * 80)
        logger.info(text)
        logger.info("=" * 80 + "\n")

        return text

    def get_all_keywords_flat(self, keyword_data: Dict) -> List[str]:
        """Get flat list of all researched keywords for tags"""
        keywords = []
        for topic, suggestions in keyword_data.get('suggestions', {}).items():
            keywords.extend(suggestions)
        return keywords[:20]  # Top 20 unique keywords
