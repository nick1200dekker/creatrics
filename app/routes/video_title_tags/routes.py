from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.credits.credits_manager import CreditsManager
from app.scripts.video_title.video_title import VideoTitleGenerator
from app.scripts.video_tags.video_tags import VideoTagsGenerator
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-title-tags')
@auth_required
@require_permission('video_title')
def video_title_tags():
    """Video title and tags generator page"""
    return render_template('video_title_tags/index.html')

# Note: The API endpoints still use the original routes from video_title and video_tags
# This allows the consolidated UI to work with existing backend logic
