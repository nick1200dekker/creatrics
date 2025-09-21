from flask import Blueprint

bp = Blueprint('brain_dump', __name__)

from . import brain_dump_routes