from flask import render_template
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission

@bp.route('/competitors')
@auth_required
@require_permission('competitors')
def competitors():
    """Competitors analysis page"""
    return render_template('competitors/index.html')