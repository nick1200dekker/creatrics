from flask import Blueprint

bp = Blueprint('competitors', __name__)

from . import competitors_routes