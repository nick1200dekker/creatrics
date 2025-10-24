# /app/routes/news_tracker/routes.py
from flask import Blueprint, render_template, request, jsonify, g
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.news_tracker.news_service import NewsService
from app.scripts.news_radar.feed_service import FeedService
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('news_tracker', __name__, url_prefix='/news-tracker')

@bp.route('/')
@auth_required
@require_permission('news_tracker')
def index():
    """News Tracker main page"""
    return render_template('news_tracker.html')

@bp.route('/api/fetch-news', methods=['POST'])
@auth_required
@require_permission('news_tracker')
def fetch_news():
    """Fetch news from RSS feeds"""
    try:
        data = request.get_json()
        feed_url = data.get('feed_url', 'https://feeds.bbci.co.uk/news/rss.xml')

        news_service = NewsService()
        news_items = news_service.fetch_news(feed_url)

        return jsonify({
            'success': True,
            'news': news_items
        })
    except Exception as e:
        logger.error(f"Error fetching news: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/generate-post', methods=['POST'])
@auth_required
@require_permission('news_tracker')
def generate_post():
    """Generate X post from news article"""
    try:
        data = request.get_json()
        news_url = data.get('url')
        news_title = data.get('title')

        # Get workspace user ID (handles both personal and team workspaces)
        user_id = get_workspace_user_id()

        if not news_url or not news_title:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Initialize credits manager
        credits_manager = CreditsManager()

        # Estimate content for credit calculation
        estimated_content = f"{news_title}\n{news_url}"

        # Estimate cost
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=estimated_content,
            model_name=None  # Uses current AI provider model
        )

        # Check if user has sufficient credits
        required_credits = cost_estimate['final_cost']
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return jsonify({
                'success': False,
                'error': f'Insufficient credits. Required: {required_credits:.2f}, Available: {current_credits:.2f}',
                'error_type': 'insufficient_credits',
                'current_credits': current_credits,
                'required_credits': required_credits,
                'credits_required': True
            }), 402

        # Generate post
        news_service = NewsService()
        result = news_service.generate_x_post(news_url, news_title, user_id)

        # Extract post content and token usage
        post_content = result['content']
        token_usage = result['token_usage']

        # Deduct credits based on actual token usage
        try:
            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=result.get('model'),
                input_tokens=token_usage.get('input_tokens', 0),
                output_tokens=token_usage.get('output_tokens', 0),
                description='News Tracker - Generate X Post',
                provider_enum=result.get('provider_enum')
            )

            if not deduction_result.get('success', False):
                logger.error(f"Failed to deduct credits: {deduction_result.get('message')}")
                # Continue anyway - post was generated

            credits_used = deduction_result.get('credits_deducted', required_credits)
        except Exception as credit_error:
            logger.error(f"Error deducting credits: {str(credit_error)}")
            # Continue anyway - post was generated
            credits_used = required_credits

        return jsonify({
            'success': True,
            'post': post_content,
            'credits_used': credits_used
        })
    except Exception as e:
        logger.error(f"Error generating post: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/personalized-feed', methods=['GET'])
@auth_required
@require_permission('news_tracker')
def get_personalized_feed():
    """Get personalized 'For You' feed based on user's subscriptions"""
    try:
        user_id = get_workspace_user_id()
        limit = request.args.get('limit', 50, type=int)

        feed_service = FeedService()
        articles = feed_service.get_personalized_feed(user_id, limit)

        return jsonify({
            'success': True,
            'articles': articles
        })
    except Exception as e:
        logger.error(f"Error getting personalized feed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/category-feed/<category>', methods=['GET'])
@auth_required
@require_permission('news_tracker')
def get_category_feed(category):
    """Get articles for a specific category"""
    try:
        limit = request.args.get('limit', 50, type=int)

        feed_service = FeedService()
        articles = feed_service.get_category_feed(category, limit)

        return jsonify({
            'success': True,
            'category': category,
            'articles': articles
        })
    except Exception as e:
        logger.error(f"Error getting category feed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/categories', methods=['GET'])
@auth_required
@require_permission('news_tracker')
def get_categories():
    """Get all available categories"""
    try:
        feed_service = FeedService()
        categories = feed_service.get_all_categories()

        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Error getting categories: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/subscriptions', methods=['GET'])
@auth_required
@require_permission('news_tracker')
def get_subscriptions():
    """Get user's category subscriptions"""
    try:
        user_id = get_workspace_user_id()

        feed_service = FeedService()
        subscriptions = feed_service.get_user_subscriptions(user_id)

        return jsonify({
            'success': True,
            'subscriptions': subscriptions
        })
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/subscriptions', methods=['POST'])
@auth_required
@require_permission('news_tracker')
def update_subscriptions():
    """Update user's category subscriptions"""
    try:
        user_id = get_workspace_user_id()
        data = request.get_json()
        categories = data.get('categories', [])

        if not isinstance(categories, list):
            return jsonify({
                'success': False,
                'error': 'Categories must be an array'
            }), 400

        feed_service = FeedService()
        success = feed_service.update_user_subscriptions(user_id, categories)

        if success:
            return jsonify({
                'success': True,
                'message': 'Subscriptions updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update subscriptions'
            }), 500

    except Exception as e:
        logger.error(f"Error updating subscriptions: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
