from flask import render_template
from . import bp
from app.system.auth.middleware import auth_required

@bp.route('/competitors')
@auth_required
def competitors():
    """Competitors analysis page"""
    return render_template('competitors/index.html')