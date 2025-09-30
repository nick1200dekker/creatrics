from flask import Blueprint

bp = Blueprint('trend_finder', __name__, url_prefix='/tiktok/trend-finder')

from . import trend_finder_routes