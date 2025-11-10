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

        # SEQUENTIAL API CALLS - Fetch pages one by one using cursor from previous response
        all_videos = []
        search_id = "0"
        cursor = 0
        has_more = True
        max_pages = 5  # Limit to 5 pages to avoid too many API calls

        page_count = 0

        while has_more and page_count < max_pages:
            params = {
                "keyword": keyword,
                "cursor": cursor,
                "search_id": search_id
            }

            logger.info(f"Fetching page {page_count + 1} for '{keyword}' ({mode} mode) - cursor: {cursor}")

            try:
                response = requests.get(endpoint, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if data.get('status_code') == 0:
                    # Extract videos based on mode
                    if mode == 'video':
                        item_list = data.get('item_list', [])
                        if item_list:
                            all_videos.extend(item_list)
                            logger.info(f"Page {page_count + 1}: Got {len(item_list)} videos")

                        # Get cursor and search_id for next request
                        cursor = data.get('cursor', cursor)
                        search_id = data.get('search_id', search_id)
                        has_more = data.get('has_more', False)
                    else:
                        page_data = data.get('data', [])
                        if page_data:
                            all_videos.extend(page_data)
                            logger.info(f"Page {page_count + 1}: Got {len(page_data)} videos")

                        # Get search_id from log_pb (for general search)
                        log_pb = data.get('log_pb', {})
                        impr_id = log_pb.get('impr_id')
                        if impr_id:
                            search_id = impr_id

                        # Get cursor for next page
                        cursor = data.get('cursor', cursor)
                        has_more = data.get('has_more', False)

                    page_count += 1

                    # If no items returned, stop
                    if (mode == 'video' and not item_list) or (mode != 'video' and not page_data):
                        logger.info(f"No more videos returned, stopping at page {page_count}")
                        break
                else:
                    logger.warning(f"API returned status_code: {data.get('status_code')}")
                    break

            except Exception as e:
                logger.error(f"Error fetching page {page_count + 1}: {e}")
                break

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
