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

        # Get autocomplete suggestions count as search interest indicator
        autocomplete_url = f"https://{RAPIDAPI_HOST}/suggest_queries"
        autocomplete_params = {"query": keyword, "geo": "US"}

        try:
            autocomplete_response = requests.get(autocomplete_url, headers=headers, params=autocomplete_params, timeout=10)
            autocomplete_data = autocomplete_response.json()
            suggestion_count = len(autocomplete_data.get('suggestions', []))
        except:
            suggestion_count = 0

        # Calculate average views from recent videos (last 20) for interest indication
        top_videos = all_time_data.get('data', [])[:20]
        view_counts = []

        for video in top_videos:
            if video.get('type') in ['video', 'shorts']:
                view_text = video.get('viewCount')
                if view_text:
                    try:
                        view_counts.append(int(view_text))
                    except (ValueError, TypeError):
                        continue

        avg_views = int(statistics.mean(view_counts)) if view_counts else 0

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

        # Determine search interest level based on suggestions and views
        # More suggestions = more people searching for related terms
        if suggestion_count >= 13:
            interest_level = 'high'
            interest_score = 80
        elif suggestion_count >= 8:
            interest_level = 'medium'
            interest_score = 50
        elif suggestion_count >= 5:
            interest_level = 'low'
            interest_score = 25
        else:
            interest_level = 'very_low'
            interest_score = 5

        # Boost interest score if videos have good views
        if avg_views > 100000:
            interest_score = min(100, interest_score + 15)
        elif avg_views > 10000:
            interest_score = min(100, interest_score + 10)

        # Calculate opportunity score
        # Good opportunity = High interest + Low competition
        opportunity_score = int((interest_score * 0.6) + (competition_score * 0.4))

        result = {
            'keyword': keyword,
            'total_videos': total_videos,
            'suggestion_count': suggestion_count,
            'avg_views': avg_views,
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
    """Analyze multiple keywords at once"""
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
                # Call analyze_keyword logic for each
                headers = {
                    "x-rapidapi-key": RAPIDAPI_KEY,
                    "x-rapidapi-host": RAPIDAPI_HOST,
                }

                # Get basic metrics (faster, just estimatedResults)
                url = f"https://{RAPIDAPI_HOST}/search"
                params = {"query": keyword}

                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                result_data = response.json()

                total_videos = int(result_data.get('estimatedResults', 0))

                # Simple opportunity score based on competition
                if total_videos < 50000:
                    opportunity_score = 80
                    competition_level = 'low'
                elif total_videos < 500000:
                    opportunity_score = 50
                    competition_level = 'medium'
                else:
                    opportunity_score = 25
                    competition_level = 'high'

                results.append({
                    'keyword': keyword,
                    'total_videos': total_videos,
                    'opportunity_score': opportunity_score,
                    'competition_level': competition_level
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
