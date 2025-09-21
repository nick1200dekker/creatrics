from flask import Blueprint

bp = Blueprint('content_calendar', __name__)

from . import content_calendar_routes