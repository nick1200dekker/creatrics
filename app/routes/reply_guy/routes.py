from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission

@bp.route('/')
@auth_required
@require_permission('reply_guy')
def index():
    """Reply Guy tool - Coming Soon page"""
    return render_template('reply_guy/index.html')
