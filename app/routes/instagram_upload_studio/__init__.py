from flask import Blueprint

bp = Blueprint('instagram_upload_studio', __name__, url_prefix='/instagram-upload-studio')

from app.routes.instagram_upload_studio import routes
