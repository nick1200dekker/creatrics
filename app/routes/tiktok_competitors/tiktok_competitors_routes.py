from flask import render_template
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from . import bp

@bp.route('/')
@auth_required
@require_permission('tiktok_competitors')
def tiktok_competitors():
    """TikTok Competitors - Analyze competitor accounts and content strategies"""
    return render_template('tiktok/competitors.html',
                         title='TikTok Competitors',
                         description='Analyze competitor accounts and content strategies')
