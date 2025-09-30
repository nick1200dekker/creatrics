from flask import render_template
from app.system.auth.middleware import auth_required
from . import tiktok_bp

# Hook Generator Route
@tiktok_bp.route('/hook-generator')
@auth_required
def hook_generator():
    """Hook Generator - Write viral hooks to grab attention in the first 3 seconds"""
    return render_template('tiktok/hook_generator.html',
                         title='Hook Generator',
                         description='Write viral hooks to grab attention in the first 3 seconds')

# Titles & Hashtags Route
@tiktok_bp.route('/titles-hashtags')
@auth_required
def titles_hashtags():
    """Titles & Hashtags - Create captions with trending keywords & hashtags"""
    return render_template('tiktok/titles_hashtags.html',
                         title='Titles & Hashtags',
                         description='Create captions with trending keywords & hashtags')

# Trending Sounds Route
@tiktok_bp.route('/trending-sounds')
@auth_required
def trending_sounds():
    """Trending Sounds - Discover the hottest sounds in your niche"""
    return render_template('tiktok/trending_sounds.html',
                         title='Trending Sounds',
                         description='Discover the hottest sounds in your niche')

# Trend Finder Route
@tiktok_bp.route('/trend-finder')
@auth_required
def trend_finder():
    """Trend Finder - Spot challenges & content styles that are taking off"""
    return render_template('tiktok/trend_finder.html',
                         title='Trend Finder',
                         description='Spot challenges & content styles that are taking off')

# Analytics Route
@tiktok_bp.route('/analytics')
@auth_required
def analytics():
    """Analytics - Track performance and follower growth"""
    return render_template('tiktok/analytics.html',
                         title='Analytics',
                         description='Track performance and follower growth')