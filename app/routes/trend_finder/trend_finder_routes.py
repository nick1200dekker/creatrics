from flask import render_template
from app.system.auth.middleware import auth_required
from . import bp

@bp.route('/')
@auth_required
def trend_finder():
    """Trend Finder - Spot challenges & content styles that are taking off"""
    return render_template('tiktok/trend_finder.html',
                         title='Trend Finder',
                         description='Spot challenges & content styles that are taking off')