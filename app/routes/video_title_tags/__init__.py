from flask import Blueprint

bp = Blueprint('video_title_tags', __name__)

from . import routes
