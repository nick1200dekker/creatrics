"""
YouTube Keyword Research System
Extracts main topics from content and gets real YouTube autocomplete suggestions
"""

import os
import re
import requests
import logging
from pathlib import Path
from typing import Dict, List


# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

def load_prompt(filename: str, section: str = None) -> str:
    """Load a prompt from text file, optionally extracting a specific section"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # If no section specified, return full content
        if not section:
            return content.strip()

        # Extract specific section
        section_marker = f"############# {section} #############"
        if section_marker not in content:
            logger.error(f"Section '{section}' not found in {filename}")
            raise ValueError(f"Section '{section}' not found")

        # Find the start of this section
        start_idx = content.find(section_marker)
        if start_idx == -1:
            raise ValueError(f"Section '{section}' not found")

        # Skip past the section marker and newline
        content_start = start_idx + len(section_marker)
        if content_start < len(content) and content[content_start] == '\n':
            content_start += 1

        # Find the next section marker (if any)
        next_section = content.find("\n#############", content_start)

        if next_section == -1:
            # This is the last section
            section_content = content[content_start:]
        else:
            # Extract until next section
            section_content = content[content_start:next_section]

        return section_content.strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}, section {section}: {e}")
        raise
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
        from datetime import datetime

        # Ultra-compact prompt to minimize tokens
        content_preview = content[:500]
        now = datetime.now()
        current_year = now.year

        system_prompt_template = load_prompt('keyword_researcher_prompts.txt', 'EXTRACT_TOPICS_SYSTEM')
        system_prompt = system_prompt_template.format(current_year=current_year)

        user_prompt_template = load_prompt('keyword_researcher_prompts.txt', 'EXTRACT_TOPICS_USER')
        prompt = user_prompt_template.format(
            current_year=current_year,
            content_preview=content_preview
        )

        try:
            # ASYNC AI call - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=7000,
                    temperature=0.7
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

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

            logger.info(f"Extracted topics: {cleaned_topics}")
            return cleaned_topics[:3]

        except Exception as e:
            logger.error(f"Error extracting topics with AI: {e}")
            # Fallback: use first few words of content
            words = content.split()[:3]
            main = ' '.join(words)
            fallback_topics = [main, f"{main} best", f"{main} beginner"]
            logger.info(f"Using fallback topics: {fallback_topics}")
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

            response = requests.get(url, headers=headers, params=params, timeout=10)

            # Check for rate limit or auth errors
            if response.status_code == 429:
                logger.warning(f"Rate limit hit for '{query}'")
                return []
            elif response.status_code == 401:
                logger.warning(f"API authentication failed for '{query}'")
                return []

            response.raise_for_status()

            data = response.json()
            suggestions = data.get('suggestions', [])

            logger.info(f"Got {len(suggestions)} suggestions for '{query}'")
            return suggestions  # Return all suggestions from API

        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch autocomplete for '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting autocomplete for '{query}': {e}")
            return []

    def research_keywords(self, content: str, ai_provider) -> Dict:
        """
        Complete keyword research flow:
        1. AI extracts 3 topics (minimal tokens)
        2. Get autocomplete for each topic (free API)
        3. Return structured data
        """
        logger.info("Starting YouTube keyword research...")

        # Step 1: AI extracts 3 topics (uses ~50-100 tokens)
        topics = self.extract_topics_with_ai(content, ai_provider)

        # Step 2: PARALLEL API CALLS - Get autocomplete suggestions for all 3 topics at once
        keyword_data = {
            'main_topic': topics[0],
            'topics': topics,
            'suggestions': {}
        }

        # Fetch all 3 autocomplete suggestions in parallel
        import asyncio
        import httpx

        async def fetch_all_autocomplete():
            async with httpx.AsyncClient(timeout=10.0) as client:
                tasks = []
                url = f"https://{self.rapidapi_host}/suggest_queries"
                headers = {
                    "x-rapidapi-key": self.rapidapi_key,
                    "x-rapidapi-host": self.rapidapi_host,
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                }

                for topic in topics:
                    params = {"query": topic, "geo": "US"}
                    tasks.append(client.get(url, headers=headers, params=params))

                return await asyncio.gather(*tasks, return_exceptions=True)

        responses = asyncio.run(fetch_all_autocomplete())

        # Process responses
        for i, (topic, resp) in enumerate(zip(topics, responses)):
            if isinstance(resp, Exception):
                logger.warning(f"Could not fetch autocomplete for '{topic}': {resp}")
                keyword_data['suggestions'][topic] = []
                continue

            try:
                if resp.status_code == 200:
                    data = resp.json()
                    suggestions = data.get('suggestions', [])
                    keyword_data['suggestions'][topic] = suggestions
                    logger.info(f"Got {len(suggestions)} suggestions for '{topic}'")
                else:
                    logger.warning(f"API returned {resp.status_code} for '{topic}'")
                    keyword_data['suggestions'][topic] = []
            except Exception as e:
                logger.warning(f"Error processing autocomplete for '{topic}': {e}")
                keyword_data['suggestions'][topic] = []

        total_keywords = sum(len(s) for s in keyword_data['suggestions'].values())
        logger.info(f"Keyword research complete: {total_keywords} keywords found for {len(topics)} topics")

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

        return text

    def get_all_keywords_flat(self, keyword_data: Dict) -> List[str]:
        """Get flat list of all researched keywords for tags"""
        keywords = []
        for topic, suggestions in keyword_data.get('suggestions', {}).items():
            keywords.extend(suggestions)
        return keywords[:20]  # Top 20 unique keywords
