from flask import Blueprint

bp = Blueprint('titles_hashtags', __name__, url_prefix='/tiktok/titles-hashtags')

from . import titles_hashtags_routes