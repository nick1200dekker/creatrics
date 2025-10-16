"""
TikTok Trend Finder Routes
Finds top 100 gaming keywords from new_on_board, filters with AI, and analyzes each
"""
from flask import render_template, request, jsonify
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import require_permission
from . import bp
import logging
import os
import requests
from app.scripts.tiktok_keyword_research.tiktok_trend_analyzer import TikTokTrendAnalyzer
from app.system.ai_provider.ai_provider import get_ai_provider
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# RapidAPI configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
TIKTOK_CREATIVE_API_HOST = 'tiktok-creative-center-api.p.rapidapi.com'
TIKTOK_API_HOST = 'tiktok-api23.p.rapidapi.com'

@bp.route('/')
@auth_required
@require_permission('tiktok_trend_finder')
def tiktok_trend_finder():
    """TikTok Trend Finder - Find and analyze gaming trends"""
    return render_template('tiktok/trend_finder.html',
                         title='TikTok Trend Finder',
                         description='Find and analyze gaming trends')


@bp.route('/api/analyze', methods=['POST'])
@auth_required
@require_permission('tiktok_trend_finder')
def analyze_trends():
    """
    Main endpoint: Fetch top 100 keywords, filter with AI, use TikTok Keyword Research system
    Steps:
    1. Fetch 5 pages of trending hashtags (20 per page = 100 total)
    2. Use AI to filter gaming-related keywords
    3. Process 5 keywords in parallel at a time
    4. Return table with keyword, Total Score, Hot Score, Engagement Score
    """
    try:
        logger.info("Starting TikTok Trend Finder analysis")

        # STEP 1: Fetch top 100 new_on_board hashtags (5 pages)
        all_hashtags = []
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": TIKTOK_CREATIVE_API_HOST
        }

        for page in range(1, 6):  # Pages 1-5
            querystring = {
                "page": str(page),
                "limit": "20",
                "period": "7",
                "filter_by": "new_on_board",
                "industry_id": "25000000000"  # Games industry
            }

            logger.info(f"Fetching page {page} of trending hashtags")
            response = requests.get(
                f"https://{TIKTOK_CREATIVE_API_HOST}/api/trending/hashtag",
                headers=headers,
                params=querystring,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            if data.get('code') == 0 and 'data' in data and 'list' in data['data']:
                hashtags = data['data']['list']
                all_hashtags.extend([h['hashtag_name'] for h in hashtags])
                logger.info(f"Page {page}: Fetched {len(hashtags)} hashtags")
            else:
                logger.warning(f"Page {page}: Invalid response format")

        logger.info(f"Total hashtags fetched: {len(all_hashtags)}")

        if not all_hashtags:
            return jsonify({
                'success': False,
                'error': 'No hashtags found'
            }), 400

        # STEP 2: Filter gaming-related keywords using AI
        logger.info("Filtering gaming-related keywords with AI")
        gaming_keywords = filter_gaming_keywords_ai(all_hashtags)
        logger.info(f"AI filtered to {len(gaming_keywords)} gaming keywords")

        if not gaming_keywords:
            return jsonify({
                'success': False,
                'error': 'No gaming keywords found after AI filtering'
            }), 400

        # STEP 3: Process keywords in parallel (5 at a time)
        results = []

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_keyword = {
                executor.submit(analyze_single_keyword, keyword): keyword
                for keyword in gaming_keywords
            }

            # Process completed tasks
            for future in as_completed(future_to_keyword):
                keyword = future_to_keyword[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        logger.info(f"Completed '{keyword}': Total Score = {result['total_score']}")
                except Exception as e:
                    logger.error(f"Error analyzing keyword '{keyword}': {e}")

        # Sort by total_score descending
        results.sort(key=lambda x: x['total_score'], reverse=True)

        logger.info(f"Analysis complete. Analyzed {len(results)} keywords")

        return jsonify({
            'success': True,
            'total_keywords_fetched': len(all_hashtags),
            'gaming_keywords_found': len(gaming_keywords),
            'keywords_analyzed': len(results),
            'results': results
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch data from TikTok API'}), 500
    except Exception as e:
        logger.error(f"Error in trend finder analysis: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def analyze_single_keyword(keyword: str) -> dict:
    """
    Analyze a single keyword using the TikTok Keyword Research system
    Returns dict with scores or None if failed
    """
    try:
        logger.info(f"Analyzing keyword: {keyword}")

        analyzer = TikTokTrendAnalyzer()
        tiktok_headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": TIKTOK_API_HOST
        }

        # Fetch 5 pages using the general/top endpoint
        all_videos = []
        search_id = "0"
        cursor = 0
        max_pages = 5

        for page_num in range(max_pages):
            params = {
                "keyword": keyword,
                "cursor": cursor,
                "search_id": search_id
            }

            response = requests.get(
                f"https://{TIKTOK_API_HOST}/api/search/general",
                headers=tiktok_headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()

            tiktok_data = response.json()

            if tiktok_data.get('status_code') != 0:
                break

            # For general/top mode, data is in 'data' array
            page_data = tiktok_data.get('data', [])
            if page_data:
                all_videos.extend(page_data)

            # Get search_id and cursor for next page
            log_pb = tiktok_data.get('log_pb', {})
            impr_id = log_pb.get('impr_id')
            if impr_id and page_num == 0:
                search_id = impr_id

            # Get next cursor from response
            has_more = tiktok_data.get('has_more', False)
            next_cursor = tiktok_data.get('cursor')
            if next_cursor is not None:
                cursor = next_cursor
            else:
                cursor += 1

            if not has_more and page_num > 0:
                break

        # Analyze with the same algorithm as TikTok Keyword Research
        if all_videos:
            analysis_result = analyzer.analyze_videos(all_videos, sort_by='views')

            return {
                'keyword': keyword,
                'total_score': analysis_result.get('total_score', 0),
                'hot_score': analysis_result.get('hot_score', 0),
                'engagement_score': analysis_result.get('engagement_score', 0),
                'video_count': analysis_result.get('total_videos', 0),
                'avg_views': analysis_result.get('avg_views', 0)
            }
        else:
            logger.warning(f"No videos found for keyword: {keyword}")
            return None

    except Exception as e:
        logger.error(f"Error in analyze_single_keyword for '{keyword}': {e}")
        return None


def filter_gaming_keywords_ai(keywords: list) -> list:
    """
    Use AI to filter gaming-related keywords from the list
    Uses the unified AI provider system (same as YouTube Keyword Research)
    """
    try:
        # Create prompt for AI
        keywords_text = "\n".join(keywords)
        prompt = f"""You are analyzing TikTok hashtag keywords to identify which ones are gaming-related.

Here is the list of keywords:
{keywords_text}

Instructions:
- Only return keywords that are directly related to gaming (video games, game titles, gaming culture, gaming creators, esports, etc.)
- Do NOT change or modify the keywords in any way
- Return ONLY the gaming-related keywords, one per line
- Do NOT include explanations, numbering, or any other text
- If a keyword is not gaming-related, exclude it from your response

Gaming-related keywords:"""

        # Use unified AI provider system (same as YouTube Keyword Research)
        ai_provider = get_ai_provider()

        logger.info(f"Using {ai_provider.provider.value} for AI filtering")

        # Create completion using unified interface
        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": "You are a gaming content expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        # Parse response - split by newlines and filter empty
        response_text = response.get('content', '')
        gaming_keywords = [k.strip() for k in response_text.split('\n') if k.strip()]

        # Validate keywords are from original list (no modifications)
        valid_keywords = [k for k in gaming_keywords if k in keywords]

        logger.info(f"AI filtered: {len(keywords)} -> {len(valid_keywords)} gaming keywords")

        return valid_keywords

    except Exception as e:
        logger.error(f"Error filtering with AI: {e}")
        # Fallback: return all keywords if AI fails
        logger.warning("AI filtering failed, returning all keywords as fallback")
        return keywords
