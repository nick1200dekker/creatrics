from flask import render_template
from app.system.auth.middleware import auth_required
from . import bp

@bp.route('/')
@auth_required
def trending_sounds():
    """Trending Sounds - Discover the hottest sounds in your niche"""
    return render_template('tiktok/trending_sounds.html',
                         title='Trending Sounds',
                         description='Discover the hottest sounds in your niche')