from flask import Blueprint

bp = Blueprint('thumbnail', __name__)

from . import thumbnail_routes