from flask import Blueprint

bp = Blueprint('tiktok_analytics', __name__, url_prefix='/tiktok/analytics')

from . import tiktok_analytics_routes