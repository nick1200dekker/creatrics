from flask import Blueprint

bp = Blueprint('analytics', __name__)

from . import analytics_routes