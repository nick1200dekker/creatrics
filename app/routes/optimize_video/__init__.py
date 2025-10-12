"""
Optimize Video Blueprint
"""
from flask import Blueprint

bp = Blueprint('optimize_video', __name__, url_prefix='/optimize-video')

from . import optimize_video_routes
