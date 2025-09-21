from flask import render_template, g
from app.routes.account_settings import bp
from app.system.auth.middleware import auth_required

@bp.route('/account-settings')
@auth_required
def index():
    """Render the Account Settings page"""
    return render_template('account_settings/index.html')
