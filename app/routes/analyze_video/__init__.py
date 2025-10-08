from flask import Blueprint

bp = Blueprint('analyze_video', __name__)

from . import analyze_video_routes
