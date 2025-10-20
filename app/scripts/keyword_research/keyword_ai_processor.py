"""
Keyword Research AI Processor
Handles AI operations for topic context detection, keyword generation, and insights
"""
import logging
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)

# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

# RapidAPI configuration
import os
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
RAPIDAPI_HOST = 'yt-api.p.rapidapi.com'


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


def fetch_youtube_data_for_topic(topic: str, max_pages: int = 5) -> dict:
    """
    Fetch real YouTube search results for a topic to analyze trending content
    Fetches multiple pages for more comprehensive data
    Returns video titles, views, publish dates, and metadata
    """
    try:
        url = "https://yt-api.p.rapidapi.com/search"
        headers = {
            'X-RapidAPI-Key': RAPIDAPI_KEY,
            'X-RapidAPI-Host': RAPIDAPI_HOST
        }

        all_videos = []
        continuation_token = None
        estimated_results = 0

        # Fetch up to max_pages of results
        for page in range(max_pages):
            params = {
                'query': topic,
                'upload_date': 'month',  # Last month's content
                'sort_by': 'relevance'
            }

            # Add continuation token for subsequent pages
            if continuation_token:
                params['token'] = continuation_token

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch YouTube data page {page+1} for '{topic}': {response.status_code}")
                break

            data = response.json()
            videos = data.get('data', [])

            if not videos:
                break

            # Store estimated results from first page
            if page == 0:
                estimated_results = data.get('estimatedResults', 0)

            # Extract videos from this page
            for video in videos:
                if video.get('type') in ['video', 'shorts']:
                    all_videos.append({
                        'title': video.get('title', ''),
                        'views': video.get('viewCount', 0),
                        'published': video.get('publishedTimeText', ''),
                        'type': video.get('type', 'video'),
                        'channel': video.get('channelTitle', '')
                    })

            # Get continuation token for next page
            continuation_token = data.get('continuation')
            if not continuation_token:
                break

            # Small delay to avoid rate limits
            time.sleep(0.2)

        logger.info(f"Fetched {len(all_videos)} videos across {page+1} pages for topic '{topic}'")

        return {
            'estimated_results': estimated_results,
            'videos': all_videos,
            'pages_fetched': page + 1
        }

    except Exception as e:
        logger.error(f"Error fetching YouTube data for topic '{topic}': {e}")
        return None


def detect_topic_context(topic: str) -> dict:
    """
    Use AI to detect the domain and content style of a topic
    Uses REAL YouTube data to inform the analysis
    """
    try:
        ai_provider = get_ai_provider()

        # Get current date for context
        current_date = datetime.now().strftime("%B %d, %Y")

        # Fetch real YouTube data for this topic
        youtube_data = fetch_youtube_data_for_topic(topic)

        # Build real data section if available
        real_data_section = ""
        if youtube_data and youtube_data['videos']:
            # Format ALL video samples for the prompt
            video_samples = []
            for v in youtube_data['videos']:
                views_text = f"{int(v['views']):,}" if v['views'] else "N/A"
                video_samples.append(f"- \"{v['title']}\" ({views_text} views, {v['published']})")

            video_samples_text = "\n".join(video_samples)
            total_videos = len(youtube_data['videos'])
            pages = youtube_data.get('pages_fetched', 1)

            real_data_section = f"""
Here are ALL REAL top-performing videos for this topic (from last month, {total_videos} videos across {pages} pages):
{video_samples_text}"""

        # Load prompts from files
        system_prompt = load_prompt('keyword_ai_processor_prompts.txt', 'DETECT_TOPIC_CONTEXT_SYSTEM')
        user_prompt_template = load_prompt('keyword_ai_processor_prompts.txt', 'DETECT_TOPIC_CONTEXT_USER')
        user_prompt = user_prompt_template.format(
            current_date=current_date,
            topic=topic,
            real_data_section=real_data_section
        )

        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        # Parse JSON response
        content = response['content'].strip()

        # Extract JSON if wrapped in markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        context = json.loads(content)
        logger.info(f"Detected context for '{topic}': {context}")

        # Add token usage for credit tracking
        context['_token_usage'] = {
            'input_tokens': response.get('usage', {}).get('input_tokens', 0),
            'output_tokens': response.get('usage', {}).get('output_tokens', 0),
            'model': ai_provider.default_model
        }

        return context

    except Exception as e:
        logger.error(f"Error detecting topic context: {e}")
        # Return default context
        return {
            "domain": "general",
            "content_style": "mixed",
            "audience_level": "mixed",
            "content_angles": ["tutorials", "tips", "reviews"],
            "_token_usage": None
        }


def generate_keywords_with_ai(topic: str, context: dict, count: int = 100) -> dict:
    """
    Generate keyword variations using AI based on topic, context, and REAL YouTube data
    Returns dict with keywords list and token_usage
    """
    try:
        ai_provider = get_ai_provider()

        # Get current date for context
        current_date = datetime.now().strftime("%B %d, %Y")

        # Fetch real YouTube data for this topic
        youtube_data = fetch_youtube_data_for_topic(topic)

        # Add real video data if available
        real_data_section = ""
        if youtube_data and youtube_data['videos']:
            total_videos = len(youtube_data['videos'])
            pages = youtube_data.get('pages_fetched', 1)

            # Show ALL videos with publish dates for comprehensive pattern analysis
            video_samples = []
            for v in youtube_data['videos']:
                views_text = f"{int(v['views']):,}" if v['views'] else "N/A"
                video_samples.append(f"- \"{v['title']}\" ({views_text} views, {v['published']})")

            video_samples_text = "\n".join(video_samples)
            real_data_section = f"""

HERE IS THE REAL DATA - Top performing videos for "{topic}" from the last month:
({total_videos} videos across {pages} pages)

{video_samples_text}"""

        # Load prompts from files
        system_prompt_template = load_prompt('keyword_ai_processor_prompts.txt', 'GENERATE_KEYWORDS_SYSTEM')
        system_prompt = system_prompt_template.format(current_date=current_date)

        user_prompt_template = load_prompt('keyword_ai_processor_prompts.txt', 'GENERATE_KEYWORDS_USER')
        user_prompt = user_prompt_template.format(
            topic=topic,
            current_date=current_date,
            real_data_section=real_data_section,
            count=count
        )

        # Log the full prompt for debugging
        logger.info(f"========== AI KEYWORD GENERATION PROMPT for '{topic}' ==========")
        logger.info(user_prompt)
        logger.info(f"========== END PROMPT ==========")

        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=4000
        )

        # Parse JSON response
        content = response['content'].strip()

        # Extract JSON if wrapped in markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        keywords = json.loads(content)

        # Validate it's a list of strings
        if not isinstance(keywords, list):
            raise ValueError("AI did not return a list")

        # Filter and clean keywords
        keywords = [k.strip().lower() for k in keywords if isinstance(k, str) and k.strip()]

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique_keywords.append(k)

        logger.info(f"Generated {len(unique_keywords)} unique keywords for '{topic}'")

        # Return keywords along with token usage
        return {
            'keywords': unique_keywords[:count],
            'token_usage': {
                'input_tokens': response.get('usage', {}).get('input_tokens', 0),
                'output_tokens': response.get('usage', {}).get('output_tokens', 0),
                'model': ai_provider.default_model
            }
        }

    except Exception as e:
        logger.error(f"Error generating keywords with AI: {e}")
        return {'keywords': [], 'token_usage': None}


def generate_ai_insights(results: list, topic: str, context: dict) -> dict:
    """
    Generate AI-powered insights from keyword analysis results
    """
    try:
        ai_provider = get_ai_provider()

        # Get current date for context
        current_date = datetime.now().strftime("%B %d, %Y")

        # Prepare summary of results
        top_keywords = sorted(results, key=lambda x: x['opportunity_score'], reverse=True)[:10]
        summary = []

        for kw in top_keywords:
            summary.append(f"- {kw['keyword']}: Score {kw['opportunity_score']}, {kw['competition_level']} comp, {kw['interest_level']} interest")

        summary_text = "\n".join(summary)

        # Load prompts from files
        system_prompt_template = load_prompt('keyword_ai_processor_prompts.txt', 'GENERATE_INSIGHTS_SYSTEM')
        system_prompt = system_prompt_template.format(current_date=current_date)

        user_prompt_template = load_prompt('keyword_ai_processor_prompts.txt', 'GENERATE_INSIGHTS_USER')
        user_prompt = user_prompt_template.format(
            topic=topic,
            summary_text=summary_text
        )

        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )

        # Handle different response formats
        insights_text = response.get('content') or response.get('message', {}).get('content', '')

        if not insights_text:
            logger.warning(f"AI provider returned empty insights. Response: {response}")
            insights_text = 'Unable to generate insights at this time.'

        return {
            'insights_text': insights_text,
            'top_recommendations': top_keywords[:5],
            'token_usage': {
                'input_tokens': response.get('usage', {}).get('input_tokens', 0),
                'output_tokens': response.get('usage', {}).get('output_tokens', 0),
                'model': ai_provider.default_model
            }
        }

    except Exception as e:
        logger.error(f"Error generating AI insights: {e}", exc_info=True)
        return {
            'insights_text': 'Unable to generate insights at this time.',
            'top_recommendations': sorted(results, key=lambda x: x['opportunity_score'], reverse=True)[:5] if results else [],
            'token_usage': None
        }
