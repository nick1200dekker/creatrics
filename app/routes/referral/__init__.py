from flask import Blueprint

bp = Blueprint('referral', __name__, url_prefix='/referral')

from app.routes.referral import routes
