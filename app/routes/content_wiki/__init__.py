from flask import Blueprint

bp = Blueprint('content_wiki', __name__)

from . import content_wiki_routes