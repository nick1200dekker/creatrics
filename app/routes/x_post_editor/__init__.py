from flask import Blueprint

bp = Blueprint('x_post_editor', __name__, url_prefix='/x_post_editor')

from . import x_post_editor_routes