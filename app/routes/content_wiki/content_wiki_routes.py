from flask import render_template
from . import bp
from app.system.auth.middleware import auth_required

@bp.route('/content-wiki')
@auth_required
def content_wiki():
    """Content Wiki knowledge base page"""
    return render_template('content_wiki/index.html')