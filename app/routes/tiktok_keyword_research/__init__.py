from flask import Blueprint

bp = Blueprint('tiktok_keyword_research', __name__, url_prefix='/tiktok-keyword-research')

from . import tiktok_keyword_research_routes