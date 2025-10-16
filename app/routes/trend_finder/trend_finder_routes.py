"""
TikTok Trend Finder Routes
Analyzes TikTok search results to identify trending keywords based on viral potential
"""
from flask import render_template, request, jsonify
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
from . import bp
import logging
import os
import requests
from app.scripts.trend_finder.tiktok_trend_analyzer import TikTokTrendAnalyzer

logger = logging.getLogger(__name__)

# RapidAPI configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
TIKTOK_API_HOST = 'tiktok-api23.p.rapidapi.com'

@bp.route('/')
@auth_required
@require_permission('trend_finder')
def trend_finder():
    """Trend Finder - Spot challenges & content styles that are taking off"""
    return render_template('tiktok/trend_finder.html',
                         title='Trend Finder',
                         description='Spot challenges & content styles that are taking off')


@bp.route('/api/search', methods=['POST'])
@auth_required
@require_permission('trend_finder')
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

        # Collect videos from multiple pages (5 pages)
        # Note: cursor value comes from API response, not just incrementing numbers
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

            logger.info(f"Fetching TikTok {mode} results for '{keyword}' (page: {page_num}, cursor: {cursor}, search_id: {search_id})")

            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            tiktok_data = response.json()

            if tiktok_data.get('status_code') != 0:
                logger.warning(f"TikTok API error on page {page_num}")
                break  # Stop pagination on error

            # Extract data based on mode
            if mode == 'video':
                # For video mode, extract from item_list
                item_list = tiktok_data.get('item_list', [])
                if item_list:
                    # Log first and last video IDs to check for duplicates
                    first_id = item_list[0].get('id') if item_list else None
                    last_id = item_list[-1].get('id') if len(item_list) > 1 else None
                    logger.info(f"Cursor {cursor}: Got {len(item_list)} videos (first: {first_id}, last: {last_id})")
                    all_videos.extend(item_list)
                else:
                    logger.info(f"Cursor {cursor}: No videos in item_list")
                # Get search_id and cursor for next page
                if page_num == 0:
                    search_id = tiktok_data.get('search_id', search_id)
                    logger.info(f"Video mode - Got search_id: {search_id}")

                # Get next cursor from response
                has_more = tiktok_data.get('has_more', False)
                next_cursor = tiktok_data.get('cursor')
                if next_cursor is not None:
                    cursor = next_cursor
                    logger.info(f"Video mode - Next cursor: {cursor}, has_more: {has_more}")
                else:
                    cursor += 1
                    logger.info(f"Video mode - Incrementing cursor to: {cursor}")

                if not has_more and page_num > 0:
                    logger.info(f"Video mode - No more results, stopping at page {page_num}")
                    break
            else:
                # For general/top mode, data is in 'data' array
                page_data = tiktok_data.get('data', [])
                if page_data:
                    # Extract video IDs and log to check for duplicates
                    video_ids = []
                    for item in page_data:
                        if 'item' in item:
                            video_ids.append(item['item'].get('id'))
                        else:
                            video_ids.append(item.get('id'))

                    first_id = video_ids[0] if video_ids else None
                    last_id = video_ids[-1] if len(video_ids) > 1 else None
                    logger.info(f"Cursor {cursor}: Got {len(page_data)} videos (first: {first_id}, last: {last_id})")
                    all_videos.extend(page_data)
                else:
                    logger.info(f"Cursor {cursor}: No videos in data array")

                # Get search_id and cursor for next page
                log_pb = tiktok_data.get('log_pb', {})
                impr_id = log_pb.get('impr_id')
                if impr_id and page_num == 0:
                    search_id = impr_id
                    logger.info(f"Top mode - Got search_id: {search_id}")

                # Get next cursor from response
                has_more = tiktok_data.get('has_more', False)
                next_cursor = tiktok_data.get('cursor')
                if next_cursor is not None:
                    cursor = next_cursor
                    logger.info(f"Top mode - Next cursor: {cursor}, has_more: {has_more}")
                else:
                    # Increment cursor if not in response
                    cursor += 1
                    logger.info(f"Top mode - Incrementing cursor to: {cursor}")

                if not has_more and page_num > 0:
                    logger.info(f"Top mode - No more results, stopping at page {page_num}")
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
