from flask import Blueprint

bp = Blueprint('reply_guy', __name__, url_prefix='/reply_guy')

from . import routes
