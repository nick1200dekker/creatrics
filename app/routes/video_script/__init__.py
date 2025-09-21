from flask import Blueprint

bp = Blueprint('video_script', __name__)

from . import video_script_routes