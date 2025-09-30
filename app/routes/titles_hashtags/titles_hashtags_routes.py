from flask import render_template
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from . import bp

@bp.route('/')
@auth_required
@require_permission('titles_hashtags')
def titles_hashtags():
    """Titles & Hashtags - Create captions with trending keywords & hashtags"""
    return render_template('tiktok/titles_hashtags.html',
                         title='Titles & Hashtags',
                         description='Create captions with trending keywords & hashtags')