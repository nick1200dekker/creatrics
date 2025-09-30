from flask import Blueprint

bp = Blueprint('hook_generator', __name__, url_prefix='/tiktok/hook-generator')

from . import hook_generator_routes