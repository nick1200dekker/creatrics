from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required

@bp.route('/')
@auth_required
def index():
    """Niche tool - Coming Soon page"""
    return render_template('niche/index.html')
