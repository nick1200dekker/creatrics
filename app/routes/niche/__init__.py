from flask import Blueprint

bp = Blueprint('niche', __name__, url_prefix='/niche')

from . import routes
