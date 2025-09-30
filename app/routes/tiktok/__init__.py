from flask import Blueprint

tiktok_bp = Blueprint('tiktok', __name__, url_prefix='/tiktok')

from . import tiktok_routes