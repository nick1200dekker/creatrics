from flask import Blueprint

bp = Blueprint('x_post_editor', __name__)

from . import x_post_editor_routes