from flask import render_template
from app.system.auth.middleware import auth_required
from . import bp

@bp.route('/')
@auth_required
def analytics():
    """TikTok Analytics - Track performance & understand what's working"""
    return render_template('tiktok/analytics.html',
                         title='TikTok Analytics',
                         description='Track performance & understand what\'s working')