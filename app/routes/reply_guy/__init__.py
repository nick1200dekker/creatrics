from flask import Blueprint

bp = Blueprint('reply_guy', __name__, url_prefix='/reply-guy')

from . import routes