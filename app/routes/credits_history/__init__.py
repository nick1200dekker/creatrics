from flask import Blueprint

bp = Blueprint('credits_history', __name__)

from . import credits_history_routes