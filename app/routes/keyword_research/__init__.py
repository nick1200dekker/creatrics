"""
Keyword Research Blueprint
"""
from flask import Blueprint

bp = Blueprint('keyword_research', __name__, url_prefix='/keyword-research')

from . import keyword_research_routes
