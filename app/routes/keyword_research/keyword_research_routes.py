"""
Keyword Research Routes
Handles YouTube keyword research with autocomplete and competition analysis
"""
from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission, get_user_subscription
from app.system.credits.credits_manager import CreditsManager
import logging
import os
import requests
import statistics
import json
from datetime import datetime
from app.system.ai_provider.ai_provider import get_ai_provider
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from firebase_admin import firestore

logger = logging.getLogger(__name__)

# Initialize Firestore
db = firestore.client()

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

        # Handle estimatedResults which might be a string
        try:
            total_videos = int(all_time_data.get('estimatedResults', 0)) if all_time_data.get('estimatedResults') else 0
        except (ValueError, TypeError):
            total_videos = 0

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

        # Keyword relevance detection
        # Extract meaningful terms from keyword (ignore stop words)
        stop_words = {'vs', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keyword_terms = [term.lower() for term in keyword.split() if term.lower() not in stop_words and len(term) > 2]

        matching_titles = 0
        total_analyzed = 0

        for video in recent_videos[:20]:
            if video.get('type') in ['video', 'shorts']:
                # Check title relevance for quality score
                title = video.get('title', '').lower()
                if title:
                    total_analyzed += 1
                    # Count if title contains at least 50% of keyword terms
                    matches = sum(1 for term in keyword_terms if term in title)
                    if len(keyword_terms) > 0 and matches >= len(keyword_terms) * 0.5:
                        matching_titles += 1

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

        # Calculate relevance percentage
        relevance_percentage = int((matching_titles / total_analyzed * 100)) if total_analyzed > 0 else 0

        # Calculate metrics with outlier detection
        avg_recent_views = int(statistics.mean(recent_view_counts)) if recent_view_counts else 0
        median_recent_views = int(statistics.median(recent_view_counts)) if recent_view_counts else 0
        recent_video_count = len(recent_view_counts)

        # Detect outliers: if top video has 10x+ more views than median, it's likely official/viral content
        outlier_detected = False
        outlier_warning = None
        if recent_view_counts and len(recent_view_counts) >= 3:
            max_views = max(recent_view_counts)
            if median_recent_views > 0 and max_views > median_recent_views * 10:
                outlier_detected = True
                outlier_warning = f"Outlier detected: Top video has {max_views:,} views while median is {median_recent_views:,}. Using median for more accurate creator opportunity."

        # Use median instead of mean for more accurate representation (not skewed by outliers)
        views_for_scoring = median_recent_views

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
        # Using MEDIAN views to avoid outlier skew from official/viral content

        # Base score on recent video performance
        if views_for_scoring > 100000:  # 100K+ median views on recent videos
            interest_level = 'high'
            interest_score = 80
        elif views_for_scoring > 30000:  # 30K-100K median views
            interest_level = 'medium'
            interest_score = 55
        elif views_for_scoring > 5000:   # 5K-30K median views
            interest_level = 'low'
            interest_score = 30
        else:                            # < 5K median views
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

        # Determine keyword quality based on relevance and apply penalty
        keyword_quality = 'good'
        quality_warning = None

        if relevance_percentage < 40:
            keyword_quality = 'poor'
            quality_warning = f'{relevance_percentage}% relevance. Try using a more specific keyword to get better results.'
            # Apply heavy penalty for poor relevance
            opportunity_score = max(0, opportunity_score - 30)
        elif relevance_percentage < 60:
            keyword_quality = 'mixed'
            quality_warning = f'{relevance_percentage}% relevance. Try making the keyword more specific to improve match quality.'
            # Apply moderate penalty for mixed relevance
            opportunity_score = max(0, opportunity_score - 20)
        elif relevance_percentage < 70:
            keyword_quality = 'fair'
            quality_warning = f'{relevance_percentage}% relevance. Consider using a more targeted keyword.'
            # Apply light penalty for fair relevance
            opportunity_score = max(0, opportunity_score - 10)

        result = {
            'keyword': keyword,
            'total_videos': total_videos,
            'suggestion_count': suggestion_count,
            'avg_recent_views': avg_recent_views,
            'median_recent_views': median_recent_views,
            'views_used_for_scoring': views_for_scoring,
            'relevance_percentage': relevance_percentage,
            'keyword_quality': keyword_quality,
            'quality_warning': quality_warning,
            'outlier_detected': outlier_detected,
            'outlier_warning': outlier_warning,
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
        logger.error(f"Error analyzing keyword '{keyword}': {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to analyze keyword. Please try again.'}), 500
    except Exception as e:
        logger.error(f"Error in keyword analysis for '{keyword}': {e}", exc_info=True)
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

                # Keyword relevance detection
                stop_words = {'vs', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
                keyword_terms = [term.lower() for term in keyword.split() if term.lower() not in stop_words and len(term) > 2]
                matching_titles = 0
                total_analyzed = 0

                for video in videos[:20]:
                    if video.get('type') in ['video', 'shorts']:
                        # Check title relevance for quality score
                        title = video.get('title', '').lower()
                        if title:
                            total_analyzed += 1
                            # Count if title contains at least 50% of keyword terms
                            matches = sum(1 for term in keyword_terms if term in title)
                            if len(keyword_terms) > 0 and matches >= len(keyword_terms) * 0.5:
                                matching_titles += 1

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

                # Calculate relevance percentage
                relevance_percentage = int((matching_titles / total_analyzed * 100)) if total_analyzed > 0 else 0

                # Calculate metrics with outlier detection
                avg_recent_views = int(statistics.mean(recent_view_counts)) if recent_view_counts else 0
                median_recent_views = int(statistics.median(recent_view_counts)) if recent_view_counts else 0

                # Detect outliers: if top video has 10x+ more views than median, it's likely official/viral content
                outlier_detected = False
                outlier_warning = None
                if recent_view_counts and len(recent_view_counts) >= 3:
                    max_views = max(recent_view_counts)
                    if median_recent_views > 0 and max_views > median_recent_views * 10:
                        outlier_detected = True
                        outlier_warning = f"Outlier detected: Top video has {max_views:,} views while median is {median_recent_views:,}. Using median for more accurate creator opportunity."

                # Use median instead of mean for more accurate representation (not skewed by outliers)
                views_for_scoring = median_recent_views

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
                # Using MEDIAN views to avoid outlier skew from official/viral content
                if views_for_scoring > 100000:
                    interest_level = 'high'
                    interest_score = 80
                elif views_for_scoring > 30000:
                    interest_level = 'medium'
                    interest_score = 55
                elif views_for_scoring > 5000:
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

                # Determine keyword quality based on relevance and apply penalty
                keyword_quality = 'good'
                quality_warning = None

                if relevance_percentage < 40:
                    keyword_quality = 'poor'
                    quality_warning = f'{relevance_percentage}% relevance. Try using a more specific keyword to get better results.'
                    # Apply heavy penalty for poor relevance
                    opportunity_score = max(0, opportunity_score - 30)
                elif relevance_percentage < 60:
                    keyword_quality = 'mixed'
                    quality_warning = f'{relevance_percentage}% relevance. Try making the keyword more specific to improve match quality.'
                    # Apply moderate penalty for mixed relevance
                    opportunity_score = max(0, opportunity_score - 20)
                elif relevance_percentage < 70:
                    keyword_quality = 'fair'
                    quality_warning = f'{relevance_percentage}% relevance. Consider using a more targeted keyword.'
                    # Apply light penalty for fair relevance
                    opportunity_score = max(0, opportunity_score - 10)

                results.append({
                    'keyword': keyword,
                    'total_videos': total_videos,
                    'opportunity_score': opportunity_score,
                    'competition_level': competition_level,
                    'interest_level': interest_level,
                    'relevance_percentage': relevance_percentage,
                    'keyword_quality': keyword_quality,
                    'quality_warning': quality_warning,
                    'outlier_detected': outlier_detected,
                    'outlier_warning': outlier_warning,
                    'median_recent_views': median_recent_views,
                    'avg_recent_views': avg_recent_views
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


# ============================================================================
# AI-POWERED KEYWORD EXPLORATION
# ============================================================================


def analyze_single_keyword_parallel(keyword: str) -> dict:
    """
    Analyze a single keyword - used for parallel processing
    Uses same logic as manual mode but optimized for parallel execution
    """
    try:
        url = "https://yt-api.p.rapidapi.com/search"
        headers = {
            'X-RapidAPI-Key': RAPIDAPI_KEY,
            'X-RapidAPI-Host': RAPIDAPI_HOST
        }

        # First call: Get all-time results for competition metric
        all_time_params = {'query': keyword}
        all_time_response = requests.get(url, headers=headers, params=all_time_params, timeout=10)

        if all_time_response.status_code != 200:
            logger.warning(f"Failed to fetch all-time data for '{keyword}': {all_time_response.status_code}")
            return None

        all_time_data = all_time_response.json()

        # Get total videos (competition metric)
        try:
            total_videos = int(all_time_data.get('estimatedResults', 0)) if all_time_data.get('estimatedResults') else 0
        except (ValueError, TypeError):
            total_videos = 0

        # Second call: Get recent videos (last 30 days) for interest metric
        recent_params = {
            'query': keyword,
            'upload_date': 'month'  # Last 30 days
        }
        response = requests.get(url, headers=headers, params=recent_params, timeout=10)

        if response.status_code != 200:
            logger.warning(f"Failed to fetch recent data for '{keyword}': {response.status_code}")
            return None

        data = response.json()

        if not data.get('data'):
            logger.warning(f"No recent data returned for '{keyword}'")
            return None

        # Extract recent video data
        videos = data.get('data', [])

        # Skip shorts listings (they're not actual videos)
        videos = [v for v in videos if v.get('type') in ['video', 'shorts']]

        if not videos:
            logger.warning(f"No actual videos found for '{keyword}'")
            return None

        # Calculate metrics (simplified version of main analysis)
        recent_view_counts = []
        matching_titles = 0
        total_analyzed = 0
        high_performing_videos = 0

        # Extract meaningful terms (ignore stop words) - same logic as main analyze
        stop_words = {'vs', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keyword_terms = [term.lower() for term in keyword.split() if term.lower() not in stop_words and len(term) > 2]

        for video in videos[:20]:
            try:
                total_analyzed += 1
                title = video.get('title', '').lower()

                # Check relevance - title must contain at least 50% of keyword terms
                if title:
                    matches = sum(1 for term in keyword_terms if term in title)
                    if len(keyword_terms) > 0 and matches >= len(keyword_terms) * 0.5:
                        matching_titles += 1

                # Get views - ensure proper type conversion
                try:
                    view_count = int(video.get('viewCount', 0)) if video.get('viewCount') else 0
                except (ValueError, TypeError):
                    view_count = 0

                # All videos are recent (filtered by upload_date='month' in API params)
                if view_count > 0:
                    recent_view_counts.append(view_count)
                    if view_count > 50000:
                        high_performing_videos += 1

            except Exception as e:
                continue

        # If no recent videos, return None (keyword might be too specific or no content)
        if not recent_view_counts or total_analyzed == 0:
            logger.warning(f"No recent videos found for '{keyword}' (analyzed {total_analyzed} videos)")
            return None

        # Calculate metrics
        avg_recent_views = int(statistics.mean(recent_view_counts))
        median_recent_views = int(statistics.median(recent_view_counts))
        relevance_percentage = int((matching_titles / total_analyzed * 100)) if total_analyzed > 0 else 0

        # Outlier detection
        outlier_detected = False
        outlier_warning = None
        if len(recent_view_counts) >= 3:
            max_views = max(recent_view_counts)
            if median_recent_views > 0 and max_views > median_recent_views * 10:
                outlier_detected = True
                outlier_warning = f"Outlier detected"

        views_for_scoring = median_recent_views

        # Competition scoring
        if total_videos < 50000:
            competition_level = 'low'
            competition_score = 80
        elif total_videos < 500000:
            competition_level = 'medium'
            competition_score = 50
        else:
            competition_level = 'high'
            competition_score = 20

        # Interest scoring
        if views_for_scoring > 100000:
            interest_level = 'high'
            interest_score = 80
        elif views_for_scoring > 30000:
            interest_level = 'medium'
            interest_score = 55
        elif views_for_scoring > 5000:
            interest_level = 'low'
            interest_score = 30
        else:
            interest_level = 'very_low'
            interest_score = 10

        # Boost for multiple high performers (confirms sustained interest)
        if high_performing_videos >= 5:
            interest_score = min(100, interest_score + 20)
        elif high_performing_videos >= 3:
            interest_score = min(100, interest_score + 10)

        # Calculate opportunity score (same formula as manual mode)
        # Good opportunity = High interest + Low competition
        opportunity_score = int((interest_score * 0.6) + (competition_score * 0.4))

        # Quality warnings
        keyword_quality = 'good'
        quality_warning = None

        if relevance_percentage < 40:
            keyword_quality = 'poor'
            quality_warning = f'{relevance_percentage}% relevance - keyword may be too broad or ambiguous'
            opportunity_score = max(0, opportunity_score - 30)
        elif relevance_percentage < 60:
            keyword_quality = 'mixed'
            quality_warning = f'{relevance_percentage}% relevance'
            opportunity_score = max(0, opportunity_score - 20)
        elif relevance_percentage < 70:
            keyword_quality = 'fair'
            quality_warning = f'{relevance_percentage}% relevance'
            opportunity_score = max(0, opportunity_score - 10)

        return {
            'keyword': keyword,
            'total_videos': total_videos,
            'opportunity_score': opportunity_score,
            'competition_level': competition_level,
            'interest_level': interest_level,
            'relevance_percentage': relevance_percentage,
            'keyword_quality': keyword_quality,
            'quality_warning': quality_warning,
            'outlier_detected': outlier_detected,
            'outlier_warning': outlier_warning,
            'median_recent_views': median_recent_views,
            'avg_recent_views': avg_recent_views
        }

    except Exception as e:
        logger.error(f"Error analyzing keyword '{keyword}': {e}")
        return None




@bp.route('/api/ai-keyword-explore', methods=['POST'])
@auth_required
@require_permission('keyword_research')
def ai_keyword_explore():
    """
    AI-powered keyword exploration endpoint with credit management
    Generates and analyzes up to 50 keywords for a given topic
    """
    try:
        # Import AI processor from scripts
        from app.scripts.keyword_research.keyword_ai_processor import (
            detect_topic_context,
            generate_keywords_with_ai,
            generate_ai_insights
        )

        data = request.json
        topic = data.get('topic', '').strip()
        keyword_count = min(int(data.get('count', 50)), 50)  # Default and max 50

        if not topic:
            return jsonify({'success': False, 'error': 'Topic is required'}), 400

        user_id = get_workspace_user_id()
        credits_manager = CreditsManager()
        user_subscription = get_user_subscription()

        logger.info(f"AI keyword explore requested for topic: '{topic}' with {keyword_count} keywords")

        # Estimate cost more accurately (3 AI calls typically use ~7000 input + ~700 output tokens)
        # Context detection: ~3000 input, ~80 output
        # Keyword generation: ~3000 input, ~450 output
        # Insights generation: ~1000 input, ~170 output
        # Total: ~7000 input, ~700 output
        estimated_input_tokens = 7000
        estimated_output_tokens = 700

        # Get the AI provider to calculate actual cost
        ai_provider = get_ai_provider()
        config = ai_provider.config  # Config is stored as instance variable

        # Calculate estimated cost in credits (1 credit = $0.01)
        input_cost = estimated_input_tokens * config.get('input_cost_per_token', 0.000001)
        output_cost = estimated_output_tokens * config.get('output_cost_per_token', 0.00001)
        estimated_credits = (input_cost + output_cost) * 100  # Convert to credits

        logger.info(f"Estimated credits needed: {estimated_credits:.2f} (based on ~{estimated_input_tokens} input + {estimated_output_tokens} output tokens)")

        # Check credits BEFORE making any AI calls
        credit_check = credits_manager.check_sufficient_credits(user_id, estimated_credits)
        if not credit_check.get('sufficient', False):
            logger.warning(f"Insufficient credits for user {user_id}. Required: {estimated_credits:.2f}, Available: {credit_check['current_credits']:.2f}")
            return jsonify({
                'success': False,
                'error': f"Insufficient credits. Required: ~{estimated_credits:.2f}, Available: {credit_check['current_credits']:.2f}",
                'error_type': 'insufficient_credits',
                'current_credits': credit_check['current_credits'],
                'required_credits': estimated_credits
            }), 402

        # Step 1: Detect topic context
        context = detect_topic_context(topic, user_subscription)

        # Step 2: Generate keywords with AI
        keyword_result = generate_keywords_with_ai(topic, context, keyword_count, user_subscription)
        keywords = keyword_result.get('keywords', [])

        if not keywords:
            return jsonify({
                'success': False,
                'error': 'Failed to generate keywords'
            }), 500

        logger.info(f"Generated {len(keywords)} keywords, starting parallel analysis...")

        # Step 3: Analyze keywords in parallel (10 concurrent threads)
        results = []
        failed = 0

        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks
            future_to_keyword = {
                executor.submit(analyze_single_keyword_parallel, kw): kw
                for kw in keywords
            }

            # Process results as they complete
            for future in as_completed(future_to_keyword):
                keyword = future_to_keyword[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Failed to analyze '{keyword}': {e}")
                    failed += 1

                # Small delay to avoid rate limits
                time.sleep(0.1)

        logger.info(f"Analysis complete: {len(results)} successful, {failed} failed")

        # Sort by opportunity score
        results.sort(key=lambda x: x['opportunity_score'], reverse=True)

        # Step 4: Generate AI insights
        insights = generate_ai_insights(results, topic, context)

        # Step 5: Deduct credits for all 3 AI operations
        total_input_tokens = 0
        total_output_tokens = 0

        # Context detection tokens
        if context.get('_token_usage'):
            ctx_in = context['_token_usage']['input_tokens']
            ctx_out = context['_token_usage']['output_tokens']
            total_input_tokens += ctx_in
            total_output_tokens += ctx_out
            logger.info(f"Context detection tokens: {ctx_in} in / {ctx_out} out")

        # Keyword generation tokens
        if keyword_result.get('token_usage'):
            kw_in = keyword_result['token_usage']['input_tokens']
            kw_out = keyword_result['token_usage']['output_tokens']
            total_input_tokens += kw_in
            total_output_tokens += kw_out
            logger.info(f"Keyword generation tokens: {kw_in} in / {kw_out} out")

        # Insights generation tokens
        if insights.get('token_usage'):
            ins_in = insights['token_usage']['input_tokens']
            ins_out = insights['token_usage']['output_tokens']
            total_input_tokens += ins_in
            total_output_tokens += ins_out
            logger.info(f"Insights generation tokens: {ins_in} in / {ins_out} out")

        logger.info(f"TOTAL tokens for all 3 API calls: {total_input_tokens} in / {total_output_tokens} out")

        # Deduct credits - MUST succeed or we don't return results
        if total_input_tokens > 0:
            # Get provider_enum from the first available API response (they all use the same provider)
            provider_enum = None
            if context.get('_token_usage', {}).get('provider_enum'):
                provider_enum = context['_token_usage']['provider_enum']
            elif keyword_result.get('token_usage', {}).get('provider_enum'):
                provider_enum = keyword_result['token_usage']['provider_enum']
            elif insights.get('token_usage', {}).get('provider_enum'):
                provider_enum = insights['token_usage']['provider_enum']

            ai_provider = get_ai_provider()
            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=ai_provider.default_model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                description=f"AI Keyword Research - {topic} ({keyword_count} keywords)",
                feature_id="ai_keyword_research",
                provider_enum=provider_enum  # Use actual provider from API responses
            )

            if not deduction_result['success']:
                # CRITICAL: If deduction fails, DO NOT return results
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                return jsonify({
                    'success': False,
                    'error': f"Credit deduction failed: {deduction_result.get('message')}",
                    'error_type': 'credit_deduction_failed'
                }), 402

        # Clean up internal token usage from context before returning
        context_copy = {k: v for k, v in context.items() if not k.startswith('_')}

        response_data = {
            'success': True,
            'topic': topic,
            'detected_context': context_copy,
            'keywords_generated': len(keywords),
            'keywords_analyzed': len(results),
            'keywords_failed': failed,
            'results': results,
            'insights': insights['insights_text'],
            'top_recommendations': insights['top_recommendations']
        }

        # Save to Firebase for later retrieval
        try:
            research_ref = db.collection('users').document(user_id).collection('keyword_research').document('latest')
            research_data = {
                'topic': topic,
                'keyword_count': len(results),
                'results': response_data,  # Save complete response
                'created_at': datetime.now()
            }
            research_ref.set(research_data)
            logger.info(f"Saved latest keyword research for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving keyword research: {e}")
            # Don't fail the request if save fails

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in AI keyword explore: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/refine-keywords', methods=['POST'])
@auth_required
@require_permission('keyword_research')
def refine_keywords():
    """
    Refine keywords by keeping high-performing ones (>=75) and generating new ones
    """
    try:
        from app.scripts.keyword_research.keyword_ai_processor import (
            detect_topic_context,
            generate_keywords_with_ai,
            generate_ai_insights
        )

        data = request.json
        topic = data.get('topic', '').strip()
        high_performing = data.get('high_performing', [])
        low_performing = data.get('low_performing', [])
        keyword_count = int(data.get('count', 50))

        if not topic:
            return jsonify({'success': False, 'error': 'Topic is required'}), 400

        user_id = get_workspace_user_id()
        credits_manager = CreditsManager()
        user_subscription = get_user_subscription()

        logger.info(f"Refine keywords requested for topic: '{topic}'. Keeping {len(high_performing)} high-performing keywords, generating {keyword_count} new ones")

        # Estimate cost (same as ai-keyword-explore)
        estimated_input_tokens = 7000
        estimated_output_tokens = 700

        ai_provider = get_ai_provider()
        config = ai_provider.config

        input_cost = estimated_input_tokens * config.get('input_cost_per_token', 0.000001)
        output_cost = estimated_output_tokens * config.get('output_cost_per_token', 0.00001)
        estimated_credits = (input_cost + output_cost) * 100

        # Check credits
        credit_check = credits_manager.check_sufficient_credits(user_id, estimated_credits)
        if not credit_check.get('sufficient', False):
            return jsonify({
                'success': False,
                'error': f"Insufficient credits. Required: ~{estimated_credits:.2f}, Available: {credit_check['current_credits']:.2f}",
                'error_type': 'insufficient_credits',
                'current_credits': credit_check['current_credits'],
                'required_credits': estimated_credits
            }), 402

        # Step 1: Detect topic context
        context = detect_topic_context(topic, user_subscription)

        # Step 2: Generate NEW keywords with AI (with context about what to avoid)
        # Build a list of existing keywords to avoid duplicates
        existing_keywords = [kw['keyword'] for kw in high_performing + low_performing]

        # Build sections for high and low performing keywords with relevance scores
        high_perf_section = ""
        if high_performing:
            high_perf_list = chr(10).join('- ' + kw['keyword'] + f" (score: {kw['opportunity_score']}, relevance: {kw.get('relevance_percentage', 0)}%)" for kw in high_performing[:15])
            high_perf_section = f"""Previous research found these HIGH-PERFORMING keywords (score >=75):
{high_perf_list}

These keywords performed well! Notice their high relevance scores - generate similar variations but NOT duplicates."""

        low_perf_section = ""
        if low_performing:
            low_perf_list = chr(10).join('- ' + kw['keyword'] + f" (score: {kw['opportunity_score']}, relevance: {kw.get('relevance_percentage', 0)}%)" for kw in low_performing[:15])
            low_perf_section = f"""

These keywords had LOWER performance:
{low_perf_list}

Learn from why these didn't perform well. Check if low relevance (<70%) was the issue - if so, the keyword is too broad/vague."""

        # Add context about existing keywords for the AI
        refinement_prompt = f"""
⚠️ KEYWORD REFINEMENT MODE ⚠️

EXISTING KEYWORDS TO AVOID (do NOT generate duplicates):
{', '.join(existing_keywords[:50])}

{high_perf_section}{low_perf_section}

CRITICAL: UNDERSTANDING RELEVANCE SCORE
The "relevance score" measures how well YouTube search results match the keyword. When we search for a keyword but find videos that don't contain the keyword terms in their titles, it means:
- There is NO real search interest for that specific keyword
- YouTube is showing alternative/related content instead
- The keyword is too broad, vague, or has low actual demand

Keywords with LOW relevance (<70%) get penalized:
- <40% relevance: -30 points (heavy penalty)
- 40-60% relevance: -20 points (moderate penalty)
- 60-70% relevance: -10 points (light penalty)

This is why high-performing keywords typically have BOTH good competition/interest scores AND high relevance (70%+).

YOUR TASK FOR REFINEMENT:
1. Generate COMPLETELY NEW keywords (not in the list above)
2. Learn patterns from high-performing keywords (what made them successful? - likely good relevance + low competition)
3. Avoid patterns from low-performing keywords (what made them fail? - often poor relevance or too competitive)
4. Focus on SPECIFIC, TARGETED keywords that will have high relevance (not broad/vague terms)
5. Prefer keywords that clearly describe actual search intent rather than generic phrases
"""

        keyword_result = generate_keywords_with_ai(topic, context, keyword_count, user_subscription, refinement_context=refinement_prompt)
        new_keywords = keyword_result.get('keywords', [])

        if not new_keywords:
            return jsonify({
                'success': False,
                'error': 'Failed to generate new keywords'
            }), 500

        logger.info(f"Generated {len(new_keywords)} new keywords, starting parallel analysis...")

        # Step 3: Analyze NEW keywords in parallel
        new_results = []
        failed = 0

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_keyword = {
                executor.submit(analyze_single_keyword_parallel, kw): kw
                for kw in new_keywords
            }

            for future in as_completed(future_to_keyword):
                keyword = future_to_keyword[future]
                try:
                    result = future.result()
                    if result:
                        new_results.append(result)
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Failed to analyze '{keyword}': {e}")
                    failed += 1
                time.sleep(0.1)

        logger.info(f"Analysis complete: {len(new_results)} successful, {failed} failed")

        # Step 4: Combine ALL original keywords (both high and low performing) with new results
        # This keeps all 50 original keywords + 50 new ones = 100 total
        all_results = high_performing + low_performing + new_results

        # Sort by opportunity score
        all_results.sort(key=lambda x: x['opportunity_score'], reverse=True)

        # Step 5: Generate AI insights for combined results
        insights = generate_ai_insights(all_results, topic, context)

        # Step 6: Deduct credits
        total_input_tokens = 0
        total_output_tokens = 0

        if context.get('_token_usage'):
            total_input_tokens += context['_token_usage']['input_tokens']
            total_output_tokens += context['_token_usage']['output_tokens']

        if keyword_result.get('token_usage'):
            total_input_tokens += keyword_result['token_usage']['input_tokens']
            total_output_tokens += keyword_result['token_usage']['output_tokens']

        if insights.get('token_usage'):
            total_input_tokens += insights['token_usage']['input_tokens']
            total_output_tokens += insights['token_usage']['output_tokens']

        logger.info(f"TOTAL tokens for refinement: {total_input_tokens} in / {total_output_tokens} out")

        if total_input_tokens > 0:
            provider_enum = None
            if context.get('_token_usage', {}).get('provider_enum'):
                provider_enum = context['_token_usage']['provider_enum']

            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=ai_provider.default_model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                description=f"AI Keyword Refinement - {topic}",
                feature_id="ai_keyword_refinement",
                provider_enum=provider_enum
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                return jsonify({
                    'success': False,
                    'error': f"Credit deduction failed: {deduction_result.get('message')}",
                    'error_type': 'credit_deduction_failed'
                }), 402

        context_copy = {k: v for k, v in context.items() if not k.startswith('_')}

        response_data = {
            'success': True,
            'topic': topic,
            'detected_context': context_copy,
            'keywords_generated': len(new_keywords),
            'keywords_analyzed': len(all_results),
            'keywords_failed': failed,
            'results': all_results,
            'insights': insights['insights_text'],
            'top_recommendations': insights['top_recommendations']
        }

        # Save to Firebase
        try:
            research_ref = db.collection('users').document(user_id).collection('keyword_research').document('latest')
            research_data = {
                'topic': topic,
                'keyword_count': len(all_results),
                'results': response_data,
                'created_at': datetime.now()
            }
            research_ref.set(research_data)
            logger.info(f"Saved refined keyword research for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving keyword research: {e}")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in refine keywords: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/latest-research', methods=['GET'])
@auth_required
@require_permission('keyword_research')
def get_latest_research():
    """Get the latest saved keyword research"""
    try:
        user_id = get_workspace_user_id()

        # Get the latest research document
        research_ref = db.collection('users').document(user_id).collection('keyword_research').document('latest')
        research_doc = research_ref.get()

        if not research_doc.exists:
            return jsonify({
                'success': True,
                'has_research': False
            })

        research_data = research_doc.to_dict()

        # Convert timestamp
        if research_data.get('created_at'):
            research_data['created_at'] = research_data['created_at'].isoformat()

        return jsonify({
            'success': True,
            'has_research': True,
            'research': research_data
        })

    except Exception as e:
        logger.error(f"Error getting latest research: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
