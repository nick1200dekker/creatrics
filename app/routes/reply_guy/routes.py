from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required

@bp.route('/')
@auth_required
def index():
    """Reply Guy tool - Coming Soon page"""
    return render_template('reply_guy/index.html')
