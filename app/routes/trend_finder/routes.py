"""
TikTok Trend Finder Routes
Simple page showing trending sounds and content
"""
from flask import render_template
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import require_permission
from . import bp

@bp.route('/')
@auth_required
@require_permission('trend_finder')
def trend_finder():
    """Trend Finder - Discover trending sounds and content"""
    return render_template('tiktok/trend_finder.html',
                         title='Trend Finder',
                         description='Discover trending sounds and content')
