import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import app from run.py
from run import app

# This is what Gunicorn uses
application = app

if __name__ == "__main__":
    app.run()