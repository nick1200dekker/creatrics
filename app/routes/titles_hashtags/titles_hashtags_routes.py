from flask import render_template
from app.system.auth.middleware import auth_required
from . import bp

@bp.route('/')
@auth_required
def titles_hashtags():
    """Titles & Hashtags - Create captions with trending keywords & hashtags"""
    return render_template('tiktok/titles_hashtags.html',
                         title='Titles & Hashtags',
                         description='Create captions with trending keywords & hashtags')