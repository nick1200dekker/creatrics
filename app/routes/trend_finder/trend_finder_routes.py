from flask import render_template
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from . import bp

@bp.route('/')
@auth_required
@require_permission('trend_finder')
def trend_finder():
    """Trend Finder - Spot challenges & content styles that are taking off"""
    return render_template('tiktok/trend_finder.html',
                         title='Trend Finder',
                         description='Spot challenges & content styles that are taking off')