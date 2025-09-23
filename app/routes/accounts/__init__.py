# Make accounts a proper package
from app.routes.accounts.routes import bp

# Import the YouTube blueprint 
from app.routes.accounts.youtube import bp as youtube_bp