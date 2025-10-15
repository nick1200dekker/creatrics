from flask import Blueprint

bp = Blueprint('tiktok_competitors', __name__, url_prefix='/tiktok/competitors')

from . import tiktok_competitors_routes
