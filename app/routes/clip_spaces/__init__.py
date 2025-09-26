from flask import Blueprint

bp = Blueprint('clip_spaces', __name__, url_prefix='/clip-spaces')

from app.routes.clip_spaces import routes