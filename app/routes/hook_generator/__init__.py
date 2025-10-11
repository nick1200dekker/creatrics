from flask import Blueprint

# Create blueprint without URL prefix so API routes work at /api/...
bp = Blueprint('hook_generator', __name__)

from . import hook_generator_routes