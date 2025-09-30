from flask import render_template
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from . import bp

@bp.route('/')
@auth_required
@require_permission('tiktok_analytics')
def analytics():
    """TikTok Analytics - Track performance & understand what's working"""
    return render_template('tiktok/analytics.html',
                         title='TikTok Analytics',
                         description='Track performance & understand what\'s working')