# /app/routes/news_tracker/routes.py
from flask import Blueprint, render_template, request, jsonify, g
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.news_tracker.news_service import NewsService
from app.scripts.news_tracker.feed_service import FeedService
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('news_tracker', __name__, url_prefix='/news-tracker')

# Available RSS feeds
RSS_FEEDS = [
    # General News
    {'name': 'BBC News', 'url': 'https://feeds.bbci.co.uk/news/rss.xml'},
    {'name': 'Reuters World', 'url': 'http://feeds.reuters.com/Reuters/worldNews'},
    {'name': 'The Guardian', 'url': 'https://www.theguardian.com/world/rss'},
    {'name': 'CNN Top Stories', 'url': 'http://rss.cnn.com/rss/cnn_topstories.rss'},
    {'name': 'Associated Press', 'url': 'https://apnews.com/index.rss'},
    {'name': 'NPR News', 'url': 'https://feeds.npr.org/1001/rss.xml'},
    {'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},

    # Tech & Business
    {'name': 'TechCrunch', 'url': 'https://techcrunch.com/feed/'},
    {'name': 'The Verge', 'url': 'https://www.theverge.com/rss/index.xml'},
    {'name': 'Hacker News', 'url': 'https://news.ycombinator.com/rss'},
    {'name': 'Ars Technica', 'url': 'https://feeds.arstechnica.com/arstechnica/index'},
    {'name': 'Wired', 'url': 'https://www.wired.com/feed/rss'},
    {'name': 'Engadget', 'url': 'https://www.engadget.com/rss.xml'},
    {'name': 'MIT Technology Review', 'url': 'https://www.technologyreview.com/feed/'},
    {'name': 'VentureBeat', 'url': 'https://venturebeat.com/feed/'},
    {'name': 'Bloomberg Technology', 'url': 'https://feeds.bloomberg.com/technology/news.rss'},
    {'name': 'Forbes Technology', 'url': 'https://www.forbes.com/technology/feed/'},

    # Finance & Crypto
    {'name': 'CoinDesk', 'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/'},
    {'name': 'Cointelegraph', 'url': 'https://cointelegraph.com/rss'},
    {'name': 'The Block Crypto', 'url': 'https://www.theblock.co/rss.xml'},
    {'name': 'Decrypt', 'url': 'https://decrypt.co/feed'},
    {'name': 'Yahoo Finance', 'url': 'https://finance.yahoo.com/news/rssindex'},
    {'name': 'MarketWatch', 'url': 'http://feeds.marketwatch.com/marketwatch/topstories/'},

    # Science & Space
    {'name': 'NASA', 'url': 'https://www.nasa.gov/rss/dyn/breaking_news.rss'},
    {'name': 'Science Daily', 'url': 'https://www.sciencedaily.com/rss/all.xml'},
    {'name': 'Scientific American', 'url': 'http://rss.sciam.com/ScientificAmerican-Global'},
    {'name': 'Space.com', 'url': 'https://www.space.com/feeds/all'},
    {'name': 'Phys.org', 'url': 'https://phys.org/rss-feed/'},

    # Gaming & Entertainment
    {'name': 'IGN', 'url': 'http://feeds.ign.com/ign/all'},
    {'name': 'GameSpot', 'url': 'https://www.gamespot.com/feeds/mashup'},
    {'name': 'Polygon', 'url': 'https://www.polygon.com/rss/index.xml'},
    {'name': 'Kotaku', 'url': 'https://kotaku.com/rss'},
    {'name': 'PC Gamer', 'url': 'https://www.pcgamer.com/rss/'},
    {'name': 'The Hollywood Reporter', 'url': 'https://www.hollywoodreporter.com/feed/'},
    {'name': 'Variety', 'url': 'https://variety.com/feed/'},

    # Sports
    {'name': 'ESPN', 'url': 'https://www.espn.com/espn/rss/news'},
    {'name': 'BBC Sport', 'url': 'http://feeds.bbci.co.uk/sport/rss.xml'},
    {'name': 'The Athletic', 'url': 'https://theathletic.com/feed/'},

    # Lifestyle & Health
    {'name': 'WebMD', 'url': 'https://www.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC'},
    {'name': 'Healthline', 'url': 'https://www.healthline.com/feeds/rss'},
    {'name': 'Medical News Today', 'url': 'https://www.medicalnewstoday.com/feeds/rss'},

    # Environment
    {'name': 'Climate Home News', 'url': 'https://www.climatechangenews.com/feed/'},
    {'name': 'Inside Climate News', 'url': 'https://insideclimatenews.org/feed/'},
]

@bp.route('/')
@auth_required
@require_permission('news_tracker')
def index():
    """News Tracker main page"""
    return render_template('news_tracker/index.html')

@bp.route('/api/feeds', methods=['GET'])
@auth_required
@require_permission('news_tracker')
def get_feeds():
    """Get list of available RSS feeds"""
    return jsonify({
        'success': True,
        'feeds': RSS_FEEDS
    })

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
        news_summary = data.get('summary', '')

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
        result = news_service.generate_x_post(news_url, news_title, news_summary, user_id)

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
        logger.info(f"Fetching category feed for: {category} (limit: {limit})")

        feed_service = FeedService()
        articles = feed_service.get_category_feed(category, limit)

        logger.info(f"Found {len(articles)} articles for category: {category}")

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
