from flask import Blueprint

bp = Blueprint('video_tags', __name__)

from . import video_tags_routes