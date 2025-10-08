import os
import sys
import logging
from flask import Flask, render_template, request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure basic logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more info
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Create app-specific logger
app_logger = logging.getLogger('creaver')
app_logger.setLevel(logging.DEBUG)  # Change to DEBUG

# Create Flask app
app = Flask(__name__, 
           template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates'),
           static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static'))

# Set a secret key for session management
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    # Only allow fallback in development
    if os.environ.get('FLASK_ENV') == 'production':
        app_logger.error("SECRET_KEY environment variable is required in production")
        raise ValueError("SECRET_KEY must be set in production environment")
    
    # Development fallback - generate a random key for this session
    import secrets
    secret_key = secrets.token_hex(32)
    app_logger.warning("Using generated secret key for development - sessions will not persist across restarts")

app.config['SECRET_KEY'] = secret_key

# Make Supabase URL and key available to all templates
@app.context_processor
def inject_supabase_credentials():
    from app.config import get_config
    config = get_config()
    credentials = {
        'supabase_url': config.get('supabase_url', ''),
        'supabase_key': config.get('supabase_anon_key', '')
    }
    return credentials
    
# Make subscription plan available to all templates
@app.context_processor
def inject_user_data():
    from flask import g
    from app.system.auth.permissions import get_active_workspace_data, check_workspace_permission
    context = {}

    # Default plan
    context['subscription_plan'] = 'Free Plan'
    context['workspace_info'] = None
    context['can_access_teams'] = False

    # If authenticated, get actual plan
    if hasattr(g, 'user') and g.user:
        try:
            # First try to get from Firebase directly
            from app.system.services.firebase_service import UserService
            user_id = g.user.get('id')
            if user_id:
                user_data = UserService.get_user(user_id)
                if user_data and 'subscription_plan' in user_data:
                    context['subscription_plan'] = user_data['subscription_plan']
                    app_logger.info(f"Context processor: using plan '{context['subscription_plan']}' from Firebase")

                # Get workspace information
                workspace_data = get_active_workspace_data()
                if workspace_data:
                    context['workspace_info'] = workspace_data
                    # Use workspace's subscription plan if not owner
                    if not workspace_data.get('is_owner'):
                        context['subscription_plan'] = workspace_data.get('subscription_plan', 'Free Plan')

                # Add permission checking function to context
                context['check_permission'] = check_workspace_permission
                context['can_access_teams'] = True  # All authenticated users can access teams
        except Exception as e:
            app_logger.warning(f"Error in user_data context processor: {e}")

    return context

# Import auth middleware
from app.system.auth.middleware import auth_middleware

# Add authentication middleware
@app.before_request
def before_request_middleware():
    return auth_middleware()

# Import consolidated blueprints
from app.routes.core.core_routes import bp as core_bp
from app.routes.home.home_routes import bp as home_bp
from app.routes.payment import bp as payment_bp

# Import content creator blueprints
from app.routes.thumbnail import bp as thumbnail_bp
from app.routes.video_title import bp as video_title_bp
from app.routes.video_tags import bp as video_tags_bp
from app.routes.video_description import bp as video_description_bp
from app.routes.video_script import bp as video_script_bp
from app.routes.competitors import bp as competitors_bp
from app.routes.analyze_video import bp as analyze_video_bp
from app.routes.brain_dump import bp as brain_dump_bp
from app.routes.mind_map import mind_map_bp
from app.routes.content_wiki import bp as content_wiki_bp
from app.routes.content_calendar import bp as content_calendar_bp
from app.routes.analytics import bp as analytics_bp
from app.routes.accounts import bp as accounts_bp
from app.routes.accounts.youtube import bp as youtube_bp

# Import X (Twitter) blueprints
from app.routes.x_post_editor import bp as x_post_editor_bp
from app.routes.reply_guy import bp as reply_guy_bp
from app.routes.clip_spaces import bp as clip_spaces_bp
from app.routes.niche import bp as niche_bp
from app.routes.credits_history import bp as credits_history_bp

# Import TikTok blueprints
from app.routes.hook_generator import bp as hook_generator_bp
from app.routes.titles_hashtags import bp as titles_hashtags_bp
from app.routes.trending_sounds import bp as trending_sounds_bp
from app.routes.trend_finder import bp as trend_finder_bp
from app.routes.tiktok_analytics import bp as tiktok_analytics_bp

# Import Teams blueprint
from app.routes.teams import teams_bp

# Import Cron blueprint
from app.routes.cron import bp as cron_bp

# Register blueprints
app.register_blueprint(core_bp)
app.register_blueprint(home_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(thumbnail_bp)
app.register_blueprint(video_title_bp)
app.register_blueprint(video_tags_bp)
app.register_blueprint(video_description_bp)
app.register_blueprint(video_script_bp)
app.register_blueprint(competitors_bp)
app.register_blueprint(analyze_video_bp)
app.register_blueprint(brain_dump_bp)
app.register_blueprint(mind_map_bp)
app.register_blueprint(content_wiki_bp)
app.register_blueprint(content_calendar_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(youtube_bp)
app.register_blueprint(x_post_editor_bp)
app.register_blueprint(reply_guy_bp)
app.register_blueprint(clip_spaces_bp)
app.register_blueprint(niche_bp)
app.register_blueprint(credits_history_bp)
app.register_blueprint(hook_generator_bp)
app.register_blueprint(titles_hashtags_bp)
app.register_blueprint(trending_sounds_bp)
app.register_blueprint(trend_finder_bp)
app.register_blueprint(tiktok_analytics_bp)
app.register_blueprint(teams_bp)

# Register Cron blueprint
app.register_blueprint(cron_bp)

# Routes for SEO files at root URL
@app.route('/sitemap.xml')
def sitemap_xml():
    app_logger.info("Serving sitemap.xml from root URL")
    return app.send_static_file('sitemap.xml')

@app.route('/robots.txt')
def robots_txt():
    app_logger.info("Serving robots.txt from root URL")
    return app.send_static_file('robots.txt')

@app.route('/favicon.ico')
def favicon():
    app_logger.info("Serving favicon.ico from root URL")
    return app.send_static_file('favicons/favicon.ico')

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    app_logger.warning(f"404 error: {request.path}")
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    app_logger.error(f"500 error: {str(e)}")
    return render_template('errors/500.html'), 500

# Add request logging
@app.before_request
def log_request():
    app_logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
    # Log auth header for debugging (redact token for security)
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token_part = auth_header.split(' ')[1] if len(auth_header.split(' ')) > 1 else 'NO_TOKEN'
        if len(token_part) > 10:
            redacted_token = token_part[:5] + '...' + token_part[-5:]
            app_logger.debug(f"Auth header present with token: {redacted_token}")
        else:
            app_logger.debug("Auth header present with invalid token format")
    else:
        app_logger.debug("No auth header present in request")

if __name__ == '__main__':
    app_logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))