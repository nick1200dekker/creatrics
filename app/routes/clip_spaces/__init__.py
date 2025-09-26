from flask import Blueprint

bp = Blueprint('clip_spaces', __name__, url_prefix='/clip_spaces')

from . import routes
