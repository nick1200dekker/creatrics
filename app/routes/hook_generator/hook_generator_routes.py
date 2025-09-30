from flask import render_template
from app.system.auth.middleware import auth_required
from . import bp

@bp.route('/')
@auth_required
def hook_generator():
    """Hook Generator - Write viral hooks to grab attention in the first 3 seconds"""
    return render_template('tiktok/hook_generator.html',
                         title='Hook Generator',
                         description='Write viral hooks to grab attention in the first 3 seconds')