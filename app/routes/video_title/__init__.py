from flask import Blueprint

bp = Blueprint('video_title', __name__)

from . import video_title_routes