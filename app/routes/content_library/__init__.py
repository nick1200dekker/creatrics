from flask import Blueprint

bp = Blueprint('content_library', __name__, url_prefix='/api/content-library')

from app.routes.content_library import routes
