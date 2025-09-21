from flask import Blueprint

bp = Blueprint('video_description', __name__)

from . import video_description_routes