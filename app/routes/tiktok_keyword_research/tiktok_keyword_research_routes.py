"""
TikTok Keyword Research Routes
Analyzes TikTok search results to identify trending keywords based on viral potential
"""
from flask import render_template, request, jsonify
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from . import bp
import logging
import os
import requests
from app.scripts.tiktok_keyword_research.tiktok_trend_analyzer import TikTokTrendAnalyzer

logger = logging.getLogger(__name__)

# RapidAPI configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
TIKTOK_API_HOST = 'tiktok-api23.p.rapidapi.com'

@bp.route('/')
@auth_required
@require_permission('tiktok_keyword_research')
def tiktok_keyword_research():
    """TikTok Keyword Research - Analyze keywords and viral potential"""
    return render_template('tiktok/keyword_research.html',
                         title='TikTok Keyword Research',
                         description='Analyze keywords and viral potential')


@bp.route('/api/search', methods=['POST'])
@auth_required
@require_permission('tiktok_keyword_research')
def search_trends():
    """
    Search TikTok for a keyword and analyze trending videos
    Returns analyzed videos with viral potential scores
    Supports pagination with cursor 0, 1, 2
    """
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()
        mode = data.get('mode', 'top')  # 'top' or 'video'
        sort = data.get('sort', 'views')  # 'views' or 'date'

        if not keyword:
            return jsonify({'success': False, 'error': 'Keyword is required'}), 400

        # Determine endpoint based on mode
        if mode == 'video':
            endpoint = f"https://{TIKTOK_API_HOST}/api/search/video"
        else:
            endpoint = f"https://{TIKTOK_API_HOST}/api/search/general"

        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": TIKTOK_API_HOST
        }

        # PARALLEL API CALLS - Fetch first page to get search_id, then fetch remaining 4 pages in parallel
        all_videos = []
        search_id = "0"

        # First request to get search_id
        first_params = {
            "keyword": keyword,
            "cursor": 0,
            "search_id": "0"
        }

        logger.info(f"Fetching first page for '{keyword}' ({mode} mode)")
        first_response = requests.get(endpoint, headers=headers, params=first_params, timeout=30)
        first_response.raise_for_status()
        first_data = first_response.json()

        if first_data.get('status_code') == 0:
            # Process first page
            if mode == 'video':
                item_list = first_data.get('item_list', [])
                if item_list:
                    all_videos.extend(item_list)
                search_id = first_data.get('search_id', search_id)
            else:
                page_data = first_data.get('data', [])
                if page_data:
                    all_videos.extend(page_data)
                log_pb = first_data.get('log_pb', {})
                impr_id = log_pb.get('impr_id')
                if impr_id:
                    search_id = impr_id

            logger.info(f"Got search_id: {search_id}")

            # Fetch remaining 4 pages in PARALLEL
            import asyncio
            import httpx

            async def fetch_remaining_pages():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    tasks = []
                    for page_num in range(1, 5):
                        params = {
                            "keyword": keyword,
                            "cursor": page_num,
                            "search_id": search_id
                        }
                        tasks.append(client.get(endpoint, headers=headers, params=params))
                    return await asyncio.gather(*tasks, return_exceptions=True)

            logger.info("Fetching 4 more pages in parallel")
            responses = asyncio.run(fetch_remaining_pages())

            # Process parallel responses
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                try:
                    data = resp.json()
                    if data.get('status_code') == 0:
                        if mode == 'video':
                            item_list = data.get('item_list', [])
                            if item_list:
                                all_videos.extend(item_list)
                        else:
                            page_data = data.get('data', [])
                            if page_data:
                                all_videos.extend(page_data)
                except:
                    continue

        if not all_videos:
            return jsonify({
                'success': True,
                'keyword': keyword,
                'mode': mode,
                'result': {
                    'analyzed_videos': [],
                    'total_videos': 0,
                    'trend_summary': 'No videos found for this keyword'
                }
            })

        # Initialize analyzer
        analyzer = TikTokTrendAnalyzer()

        # Log raw video count before analysis
        logger.info(f"Raw videos fetched: {len(all_videos)}")

        # Analyze videos (includes deduplication and filtering)
        analysis_result = analyzer.analyze_videos(all_videos, sort_by=sort)

        logger.info(f"After deduplication and filtering: {analysis_result['total_videos']} videos for '{keyword}' ({mode} mode, sort: {sort})")

        return jsonify({
            'success': True,
            'keyword': keyword,
            'mode': mode,
            'result': analysis_result
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching TikTok data for '{keyword}': {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch TikTok data'}), 500
    except Exception as e:
        logger.error(f"Error analyzing trends for '{keyword}': {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
