from flask import Blueprint

bp = Blueprint('account_settings', __name__)

from app.routes.account_settings import routes
