from flask import render_template
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission

@bp.route('/content-wiki')
@auth_required
@require_permission('content_wiki')
def content_wiki():
    """Content Wiki knowledge base page"""
    return render_template('content_wiki/index.html')