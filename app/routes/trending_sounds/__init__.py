from flask import Blueprint

bp = Blueprint('trending_sounds', __name__, url_prefix='/tiktok/trending-sounds')

from . import trending_sounds_routes