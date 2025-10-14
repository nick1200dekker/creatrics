"""
Keyword Research Routes
Handles YouTube keyword research with autocomplete and competition analysis
"""
from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
import logging
import os
import requests
import statistics
from datetime import datetime

logger = logging.getLogger(__name__)

# RapidAPI configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '16c9c09b8bmsh0f0d3ec2999f27ep115961jsn5f75604e8050')
RAPIDAPI_HOST = 'yt-api.p.rapidapi.com'

@bp.route('/')
@auth_required
@require_permission('keyword_research')
def keyword_research():
    """Keyword Research main page"""
    return render_template('keyword_research/index.html')

@bp.route('/api/autocomplete', methods=['POST'])
@auth_required
@require_permission('keyword_research')
def get_autocomplete():
    """Get YouTube autocomplete suggestions for a keyword"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()

        if not query:
            return jsonify({'success': False, 'error': 'Query is required'}), 400

        # Get autocomplete suggestions
        url = f"https://{RAPIDAPI_HOST}/suggest_queries"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        params = {
            "query": query,
            "geo": "US"
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        suggestions = data.get('suggestions', [])

        logger.info(f"Got {len(suggestions)} autocomplete suggestions for '{query}'")

        return jsonify({
            'success': True,
            'query': query,
            'suggestions': suggestions
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching autocomplete: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch suggestions'}), 500
    except Exception as e:
        logger.error(f"Error in autocomplete: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/analyze', methods=['POST'])
@auth_required
@require_permission('keyword_research')
def analyze_keyword():
    """Analyze a keyword with competition metrics"""
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()

        if not keyword:
            return jsonify({'success': False, 'error': 'Keyword is required'}), 400

        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

        # Get total results count (all time)
        all_time_url = f"https://{RAPIDAPI_HOST}/search"
        all_time_params = {"query": keyword}

        all_time_response = requests.get(all_time_url, headers=headers, params=all_time_params, timeout=30)
        all_time_response.raise_for_status()
        all_time_data = all_time_response.json()

        total_videos = int(all_time_data.get('estimatedResults', 0))

        # Get autocomplete suggestions count
        autocomplete_url = f"https://{RAPIDAPI_HOST}/suggest_queries"
        autocomplete_params = {"query": keyword, "geo": "US"}

        try:
            autocomplete_response = requests.get(autocomplete_url, headers=headers, params=autocomplete_params, timeout=10)
            autocomplete_data = autocomplete_response.json()
            suggestion_count = len(autocomplete_data.get('suggestions', []))
        except:
            suggestion_count = 0

        # Get RECENT videos (last 30 days) for better search volume estimation
        recent_url = f"https://{RAPIDAPI_HOST}/search"
        recent_params = {
            "query": keyword,
            "upload_date": "month"  # Last 30 days
        }

        try:
            recent_response = requests.get(recent_url, headers=headers, params=recent_params, timeout=30)
            recent_data = recent_response.json()
            recent_videos = recent_data.get('data', [])
        except:
            recent_videos = []

        # Analyze recent video performance for search interest
        recent_view_counts = []
        high_performing_videos = 0  # Videos with 50K+ views in last 30 days

        for video in recent_videos[:20]:
            if video.get('type') in ['video', 'shorts']:
                # Get view count
                view_text = video.get('viewCount')
                if view_text:
                    try:
                        views = int(view_text)
                        recent_view_counts.append(views)

                        # Count high-performing recent videos
                        if views > 50000:  # 50K+ views in last 30 days = real interest
                            high_performing_videos += 1
                    except (ValueError, TypeError):
                        continue

        # Calculate metrics
        avg_recent_views = int(statistics.mean(recent_view_counts)) if recent_view_counts else 0
        recent_video_count = len(recent_view_counts)

        # Determine competition level
        if total_videos < 50000:
            competition_level = 'low'
            competition_score = 80
        elif total_videos < 500000:
            competition_level = 'medium'
            competition_score = 50
        else:
            competition_level = 'high'
            competition_score = 20

        # Determine search interest based on RECENT video performance (more reliable)
        # High views on recent content = people are actively searching

        # Base score on recent video performance
        if avg_recent_views > 100000:  # 100K+ avg views on recent videos
            interest_level = 'high'
            interest_score = 80
        elif avg_recent_views > 30000:  # 30K-100K avg views
            interest_level = 'medium'
            interest_score = 55
        elif avg_recent_views > 5000:   # 5K-30K avg views
            interest_level = 'low'
            interest_score = 30
        else:                            # < 5K avg views
            interest_level = 'very_low'
            interest_score = 10

        # Boost if multiple videos are performing well (confirms sustained interest)
        if high_performing_videos >= 5:
            interest_score = min(100, interest_score + 20)
        elif high_performing_videos >= 3:
            interest_score = min(100, interest_score + 10)

        # Small boost for autocomplete suggestions (secondary indicator)
        if suggestion_count >= 13:
            interest_score = min(100, interest_score + 5)
        elif suggestion_count >= 8:
            interest_score = min(100, interest_score + 3)

        # Calculate opportunity score
        # Good opportunity = High interest + Low competition
        opportunity_score = int((interest_score * 0.6) + (competition_score * 0.4))

        result = {
            'keyword': keyword,
            'total_videos': total_videos,
            'suggestion_count': suggestion_count,
            'avg_recent_views': avg_recent_views,
            'recent_video_count': recent_video_count,
            'high_performing_videos': high_performing_videos,
            'opportunity_score': opportunity_score,
            'competition_level': competition_level,
            'interest_level': interest_level,
            'analyzed_at': datetime.now().isoformat()
        }

        logger.info(f"Analyzed keyword '{keyword}': score={opportunity_score}, competition={competition_level}")

        return jsonify({
            'success': True,
            'data': result
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error analyzing keyword: {e}")
        return jsonify({'success': False, 'error': 'Failed to analyze keyword'}), 500
    except Exception as e:
        logger.error(f"Error in keyword analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/batch-analyze', methods=['POST'])
@auth_required
@require_permission('keyword_research')
def batch_analyze():
    """Analyze multiple keywords at once using full algorithm"""
    try:
        data = request.get_json()
        keywords = data.get('keywords', [])

        if not keywords or len(keywords) == 0:
            return jsonify({'success': False, 'error': 'Keywords list is required'}), 400

        if len(keywords) > 20:
            return jsonify({'success': False, 'error': 'Maximum 20 keywords allowed'}), 400

        results = []

        for keyword in keywords:
            try:
                headers = {
                    "x-rapidapi-key": RAPIDAPI_KEY,
                    "x-rapidapi-host": RAPIDAPI_HOST,
                }

                # Get search results with video data
                url = f"https://{RAPIDAPI_HOST}/search"
                params = {"query": keyword}

                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                result_data = response.json()

                total_videos = int(result_data.get('estimatedResults', 0))
                videos = result_data.get('data', [])

                # Get autocomplete suggestions count
                autocomplete_url = f"https://{RAPIDAPI_HOST}/suggest_queries"
                autocomplete_params = {"query": keyword, "geo": "US"}

                try:
                    autocomplete_response = requests.get(autocomplete_url, headers=headers, params=autocomplete_params, timeout=10)
                    autocomplete_data = autocomplete_response.json()
                    suggestion_count = len(autocomplete_data.get('suggestions', []))
                except:
                    suggestion_count = 0

                # Filter for recent videos (last 30 days) from the returned data
                from datetime import datetime, timedelta
                thirty_days_ago = datetime.now() - timedelta(days=30)

                recent_view_counts = []
                high_performing_videos = 0

                for video in videos[:20]:
                    if video.get('type') in ['video', 'shorts']:
                        # Check if video is recent (published in last 30 days)
                        publish_date_str = video.get('publishDate') or video.get('publishedAt', '')
                        if publish_date_str:
                            try:
                                # Parse date (format: 2025-10-11 or 2025-10-11T00:00:00Z)
                                publish_date = datetime.fromisoformat(publish_date_str.replace('Z', '+00:00'))

                                # Only analyze recent videos
                                if publish_date >= thirty_days_ago:
                                    view_text = video.get('viewCount')
                                    if view_text:
                                        try:
                                            views = int(view_text)
                                            recent_view_counts.append(views)

                                            if views > 50000:
                                                high_performing_videos += 1
                                        except (ValueError, TypeError):
                                            continue
                            except:
                                continue

                # Calculate metrics
                avg_recent_views = int(statistics.mean(recent_view_counts)) if recent_view_counts else 0

                # Determine competition level
                if total_videos < 50000:
                    competition_level = 'low'
                    competition_score = 80
                elif total_videos < 500000:
                    competition_level = 'medium'
                    competition_score = 50
                else:
                    competition_level = 'high'
                    competition_score = 20

                # Determine search interest based on recent video performance
                if avg_recent_views > 100000:
                    interest_level = 'high'
                    interest_score = 80
                elif avg_recent_views > 30000:
                    interest_level = 'medium'
                    interest_score = 55
                elif avg_recent_views > 5000:
                    interest_level = 'low'
                    interest_score = 30
                else:
                    interest_level = 'very_low'
                    interest_score = 10

                # Boost for high-performing videos
                if high_performing_videos >= 5:
                    interest_score = min(100, interest_score + 20)
                elif high_performing_videos >= 3:
                    interest_score = min(100, interest_score + 10)

                # Small boost for autocomplete suggestions
                if suggestion_count >= 13:
                    interest_score = min(100, interest_score + 5)
                elif suggestion_count >= 8:
                    interest_score = min(100, interest_score + 3)

                # Calculate opportunity score
                opportunity_score = int((interest_score * 0.6) + (competition_score * 0.4))

                results.append({
                    'keyword': keyword,
                    'total_videos': total_videos,
                    'opportunity_score': opportunity_score,
                    'competition_level': competition_level,
                    'interest_level': interest_level
                })

            except Exception as e:
                logger.warning(f"Failed to analyze '{keyword}': {e}")
                continue

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
