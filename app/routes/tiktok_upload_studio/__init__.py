"""
TikTok Upload Studio Blueprint
Handles TikTok OAuth connection and video uploading
"""

from flask import Blueprint

bp = Blueprint('tiktok_upload_studio', __name__, url_prefix='/tiktok-upload-studio')

from app.routes.tiktok_upload_studio import routes
