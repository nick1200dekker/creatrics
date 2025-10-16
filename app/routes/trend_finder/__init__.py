from flask import Blueprint

bp = Blueprint('trend_finder', __name__, url_prefix='/trend-finder')

from . import routes