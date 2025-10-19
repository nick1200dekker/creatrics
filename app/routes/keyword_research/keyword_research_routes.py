"""
Keyword Research Routes
Handles YouTube keyword research with autocomplete and competition analysis
"""
from flask import render_template, request, jsonify
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, require_permission
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
        elif relevance_percentage < 50:
            keyword_quality = 'mixed'
            quality_warning = f'{relevance_percentage}% relevance. Try making the keyword more specific to improve match quality.'
            # Apply moderate penalty for mixed relevance
            opportunity_score = max(0, opportunity_score - 15)

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
                elif relevance_percentage < 50:
                    keyword_quality = 'mixed'
                    quality_warning = f'{relevance_percentage}% relevance. Try making the keyword more specific to improve match quality.'
                    # Apply moderate penalty for mixed relevance
                    opportunity_score = max(0, opportunity_score - 15)

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

        # Build prompt with real data if available
        if youtube_data and youtube_data['videos']:
            # Format ALL video samples for the prompt
            video_samples = []
            for v in youtube_data['videos']:
                views_text = f"{int(v['views']):,}" if v['views'] else "N/A"
                video_samples.append(f"- \"{v['title']}\" ({views_text} views, {v['published']})")

            video_samples_text = "\n".join(video_samples)
            total_videos = len(youtube_data['videos'])
            pages = youtube_data.get('pages_fetched', 1)

            prompt = f"""Today's date: {current_date}

Analyze this YouTube content topic: "{topic}"

Here are ALL REAL top-performing videos for this topic (from last month, {total_videos} videos across {pages} pages):
{video_samples_text}

Based on this REAL data, identify:
1. What domain/niche does this belong to? (gaming, fitness, tech, cooking, education, etc.)
2. What content style works best? (tutorial, entertainment, review, news, guide, etc.)
3. What audience level? (beginner, intermediate, advanced, or mixed)
4. What are 3-5 popular content angles based on these actual video titles?
5. Notice any time-sensitive trends? (e.g., "15 hours ago" videos vs "6 days ago")

Return ONLY valid JSON in this exact format:
{{
    "domain": "specific domain name",
    "content_style": "primary style",
    "audience_level": "level",
    "content_angles": ["angle1", "angle2", "angle3"]
}}"""
        else:
            # Fallback if no YouTube data available
            prompt = f"""Today's date: {current_date}

Analyze this YouTube content topic: "{topic}"

Identify:
1. What domain/niche does this belong to? (gaming, fitness, tech, cooking, education, etc.)
2. What content style works best? (tutorial, entertainment, review, news, guide, etc.)
3. What audience level? (beginner, intermediate, advanced, or mixed)
4. What are 3-5 popular content angles for this topic?

Return ONLY valid JSON in this exact format:
{{
    "domain": "specific domain name",
    "content_style": "primary style",
    "audience_level": "level",
    "content_angles": ["angle1", "angle2", "angle3"]
}}"""

        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": "You are a YouTube content strategy expert analyzing REAL video data. Return only valid JSON."},
                {"role": "user", "content": prompt}
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


def generate_keywords_with_ai(topic: str, context: dict, count: int = 100) -> list:
    """
    Generate keyword variations using AI based on topic, context, and REAL YouTube data
    Returns list of keyword strings
    """
    try:
        ai_provider = get_ai_provider()

        # Get current date for context
        current_date = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year

        # Fetch real YouTube data for this topic
        youtube_data = fetch_youtube_data_for_topic(topic)

        # Build context-aware prompt
        angles_text = ", ".join(context.get('content_angles', []))

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

        prompt = f"""You are a YouTube SEO specialist analyzing which SEARCH TERMS people typed to find these videos.

Topic: "{topic}"
Date: {current_date}
{real_data_section}

OUR GOAL: Find hot keywords with LOW-MEDIUM COMPETITION for our content.

KEY INSIGHT:
Video TITLES are clickbait to get clicks. Your job: figure out what SEARCH TERMS people typed to find these videos.

YOUR TASK:
Analyze what topics get views, then generate {count} search keywords with good search volume and manageable competition.

Ask yourself:
- What are these videos actually ABOUT?
- What would I type to FIND content like this?
- Which topics appear most = high demand?

Output {count} SHORT searchable keywords as JSON array:
["keyword 1", "keyword 2", ...]"""

        # Log the full prompt for debugging
        logger.info(f"========== AI KEYWORD GENERATION PROMPT for '{topic}' ==========")
        logger.info(prompt)
        logger.info(f"========== END PROMPT ==========")

        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": f"You are a YouTube SEO expert analyzing REAL video performance data. Today is {current_date}. Return only a valid JSON array of keyword strings. No explanations."},
                {"role": "user", "content": prompt}
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

        keyword_terms = set(keyword.lower().split())

        for video in videos[:20]:
            try:
                total_analyzed += 1
                title = video.get('title', '').lower()

                # Check relevance
                if any(term in title for term in keyword_terms):
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
        elif relevance_percentage < 50:
            keyword_quality = 'fair'
            quality_warning = f'{relevance_percentage}% relevance'
            opportunity_score = max(0, opportunity_score - 15)

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

        prompt = f"""Analyze these YouTube keyword opportunities for "{topic}":

TOP 10 KEYWORDS:
{summary_text}

Create 3 sections (use ## headers):

## Top 3 Keyword Opportunities
List the 3 best keywords with score and ONE sentence why each is good.

## Best Content Angles
ONE paragraph describing what content types work best (tutorials, gameplay, reviews, etc).

## Timing Recommendations
ONE paragraph about when to create this content.

Keep it SHORT and actionable. Max 200 words total."""

        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": f"You are a YouTube content strategy expert. Today is {current_date}. Provide concise, actionable insights in markdown format using ## for section headers."},
                {"role": "user", "content": prompt}
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


@bp.route('/api/ai-keyword-explore', methods=['POST'])
@auth_required
@require_permission('keyword_research')
def ai_keyword_explore():
    """
    AI-powered keyword exploration endpoint with credit management
    Generates and analyzes up to 50 keywords for a given topic
    """
    try:
        data = request.json
        topic = data.get('topic', '').strip()
        keyword_count = min(int(data.get('count', 50)), 50)  # Default and max 50

        if not topic:
            return jsonify({'success': False, 'error': 'Topic is required'}), 400

        user_id = get_workspace_user_id()
        credits_manager = CreditsManager()

        logger.info(f"AI keyword explore requested for topic: '{topic}' with {keyword_count} keywords")

        # Estimate cost (3 AI calls: context detection + keyword generation + insights)
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=topic * 50,  # Rough estimate for 50 keywords
            model_name=None  # Use default model
        )
        # Multiply by 3 for the 3 AI operations
        estimated_credits = cost_estimate['final_cost'] * 3

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
        context = detect_topic_context(topic)

        # Step 2: Generate keywords with AI
        keyword_result = generate_keywords_with_ai(topic, context, keyword_count)
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

        # Deduct credits if we have token usage
        if total_input_tokens > 0:
            ai_provider = get_ai_provider()
            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=ai_provider.default_model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                description=f"AI Keyword Research - {topic} ({keyword_count} keywords)",
                feature_id="ai_keyword_research"
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")

        # Clean up internal token usage from context before returning
        context_copy = {k: v for k, v in context.items() if not k.startswith('_')}

        return jsonify({
            'success': True,
            'topic': topic,
            'detected_context': context_copy,
            'keywords_generated': len(keywords),
            'keywords_analyzed': len(results),
            'keywords_failed': failed,
            'results': results,
            'insights': insights['insights_text'],
            'top_recommendations': insights['top_recommendations']
        })

    except Exception as e:
        logger.error(f"Error in AI keyword explore: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
