"""TikTok Trend Finder Blueprint"""
from flask import Blueprint

bp = Blueprint("tiktok_trend_finder", __name__, url_prefix="/tiktok-trend-finder")

from . import tiktok_trend_finder_routes
