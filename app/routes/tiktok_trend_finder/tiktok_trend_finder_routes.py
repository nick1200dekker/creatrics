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
from app.system.services.firebase_service import TikTokTrendFinderService
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# RapidAPI configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
TIKTOK_CREATIVE_API_HOST = 'tiktok-creative-center-api.p.rapidapi.com'
TIKTOK_API_HOST = 'tiktok-api23.p.rapidapi.com'

@bp.route('/')
@auth_required
@require_permission('tiktok_trend_finder')
def tiktok_trend_finder():
    """TikTok Trend Finder - Find and analyze trends"""
    return render_template('tiktok/trend_finder.html',
                         title='TikTok Trend Finder',
                         description='Find and analyze trends')


@bp.route('/api/cached', methods=['GET'])
@auth_required
@require_permission('tiktok_trend_finder')
def get_cached_analysis():
    """
    Get the latest cached analysis from database
    Available to all users
    """
    try:
        cached_data = TikTokTrendFinderService.get_latest_analysis()

        if cached_data:
            # Convert Firestore timestamp to ISO string if needed
            if 'updated_at' in cached_data and cached_data['updated_at']:
                try:
                    cached_data['updated_at'] = cached_data['updated_at'].isoformat()
                except:
                    pass

            return jsonify({
                'success': True,
                'cached': True,
                **cached_data
            })
        else:
            return jsonify({
                'success': True,
                'cached': False,
                'message': 'No cached analysis available'
            })

    except Exception as e:
        logger.error(f"Error getting cached analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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

        # STEP 1: Fetch top 100 hashtags with PARALLEL API calls (4 at once!)
        # 2 calls with new_on_board (pages 1-2, limit 50) + 2 calls without (pages 1-2, limit 50)
        all_hashtags = []
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": TIKTOK_CREATIVE_API_HOST
        }

        import asyncio
        import httpx

        async def fetch_all_hashtag_pages():
            async with httpx.AsyncClient(timeout=30.0) as client:
                tasks = []
                url = f"https://{TIKTOK_CREATIVE_API_HOST}/api/trending/hashtag"

                # Create 4 parallel requests
                for page in range(1, 3):
                    # With new_on_board filter
                    params_with_filter = {
                        "page": str(page),
                        "limit": "50",
                        "period": "30",
                        "country": "US",
                        "sort_by": "popular",
                        "filter_by": "new_on_board",
                        "industry_id": "25000000000"
                    }
                    tasks.append(client.get(url, headers=headers, params=params_with_filter))

                    # Without filter
                    params_no_filter = {
                        "page": str(page),
                        "limit": "50",
                        "period": "30",
                        "country": "US",
                        "sort_by": "popular",
                        "industry_id": "25000000000"
                    }
                    tasks.append(client.get(url, headers=headers, params=params_no_filter))

                return await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Fetching 4 hashtag pages in parallel")
        responses = asyncio.run(fetch_all_hashtag_pages())

        # Process all responses
        for idx, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.warning(f"Request {idx} failed: {resp}")
                continue
            try:
                data = resp.json()
                if data.get('code') == 0 and 'data' in data and 'list' in data['data']:
                    hashtags = data['data']['list']
                    all_hashtags.extend([h['hashtag_name'] for h in hashtags])
                    logger.info(f"Response {idx}: Fetched {len(hashtags)} hashtags")
            except Exception as e:
                logger.warning(f"Error processing response {idx}: {e}")

        # Remove duplicates while preserving order
        all_hashtags = list(dict.fromkeys(all_hashtags))
        logger.info(f"Total unique hashtags fetched: {len(all_hashtags)}")

        if not all_hashtags:
            return jsonify({
                'success': False,
                'error': 'No hashtags found'
            }), 400

        # STEP 2: Filter gaming-related keywords using AI
        logger.info("Filtering gaming-related keywords with AI")
        # Import AI processor from scripts
        from app.scripts.tiktok_trend_finder.tiktok_ai_processor import filter_gaming_keywords_ai
        gaming_keywords = filter_gaming_keywords_ai(all_hashtags)
        logger.info(f"AI filtered to {len(gaming_keywords)} gaming keywords")

        if not gaming_keywords:
            return jsonify({
                'success': False,
                'error': 'No gaming keywords found after AI filtering'
            }), 400

        # STEP 3: Process keywords in parallel (2 at a time to avoid rate limits)
        results = []

        # Use ThreadPoolExecutor with reduced workers to avoid rate limiting
        # RapidAPI has rate limits, so we process slower
        with ThreadPoolExecutor(max_workers=2) as executor:
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
                    # Small delay between completing tasks to respect rate limits
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error analyzing keyword '{keyword}': {e}")

        # Sort by total_score descending
        results.sort(key=lambda x: x['total_score'], reverse=True)

        logger.info(f"Analysis complete. Analyzed {len(results)} keywords")

        # Prepare response data
        analyzed_at = datetime.utcnow().isoformat()
        response_data = {
            'success': True,
            'total_keywords_fetched': len(all_hashtags),
            'gaming_keywords_found': len(gaming_keywords),
            'keywords_analyzed': len(results),
            'results': results,
            'analyzed_at': analyzed_at
        }

        # Save to database (global, available to all users)
        # Make a copy for DB that will have SERVER_TIMESTAMP added
        try:
            db_data = response_data.copy()
            TikTokTrendFinderService.save_analysis(db_data)
            logger.info("Saved analysis to database")
        except Exception as e:
            logger.error(f"Failed to save analysis to database: {e}")
            # Don't fail the request if save fails

        # Return response without Firestore Sentinel objects
        return jsonify(response_data)

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

        # PARALLEL API CALLS - Fetch first page to get search_id, then fetch remaining 4 pages in parallel
        all_videos = []
        search_id = "0"
        cursor = 0

        # First request to get search_id
        first_params = {
            "keyword": keyword,
            "cursor": 0,
            "search_id": "0"
        }

        first_response = requests.get(
            f"https://{TIKTOK_API_HOST}/api/search/general",
            headers=tiktok_headers,
            params=first_params,
            timeout=30
        )
        first_response.raise_for_status()
        first_data = first_response.json()

        if first_data.get('status_code') == 0:
            page_data = first_data.get('data', [])
            if page_data:
                all_videos.extend(page_data)

            # Get search_id for next requests
            log_pb = first_data.get('log_pb', {})
            impr_id = log_pb.get('impr_id')
            if impr_id:
                search_id = impr_id

            # Fetch remaining 4 pages in PARALLEL
            import asyncio
            import httpx

            async def fetch_remaining_pages():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    tasks = []
                    for page_num in range(1, 5):  # Pages 1-4 (0-indexed)
                        params = {
                            "keyword": keyword,
                            "cursor": page_num,
                            "search_id": search_id
                        }
                        tasks.append(client.get(
                            f"https://{TIKTOK_API_HOST}/api/search/general",
                            headers=tiktok_headers,
                            params=params
                        ))
                    return await asyncio.gather(*tasks, return_exceptions=True)

            responses = asyncio.run(fetch_remaining_pages())

            # Process parallel responses
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                try:
                    data = resp.json()
                    if data.get('status_code') == 0:
                        page_data = data.get('data', [])
                        if page_data:
                            all_videos.extend(page_data)
                except:
                    continue

        # Analyze with the same algorithm as TikTok Keyword Research
        if all_videos:
            analysis_result = analyzer.analyze_videos(all_videos, sort_by='views')

            # Filter out keywords with less than 35 videos analyzed
            video_count = analysis_result.get('total_videos', 0)
            if video_count < 35:
                logger.info(f"Skipping '{keyword}': Only {video_count} videos (minimum 35 required)")
                return None

            return {
                'keyword': keyword,
                'total_score': analysis_result.get('total_score', 0),
                'hot_score': analysis_result.get('hot_score', 0),
                'engagement_score': analysis_result.get('engagement_score', 0),
                'video_count': video_count,
                'avg_views': analysis_result.get('avg_views', 0)
            }
        else:
            logger.warning(f"No videos found for keyword: {keyword}")
            return None

    except Exception as e:
        logger.error(f"Error in analyze_single_keyword for '{keyword}': {e}")
        return None


# Note: filter_gaming_keywords_ai moved to app/scripts/tiktok_trend_finder/tiktok_ai_processor.py
