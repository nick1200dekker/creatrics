#!/usr/bin/env python3
"""
Manual script to update the default Reply Guy list with image URL extraction
Run this to re-analyze the content_creators list and extract image URLs
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize Firebase before importing the service
import firebase_admin
from firebase_admin import credentials

# Initialize Firebase if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase-credentials.json')
    firebase_admin.initialize_app(cred)

from app.scripts.reply_guy.reply_guy_service import ReplyGuyService
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Update the default content_creators list"""
    try:
        logger.info("Starting default list update...")

        service = ReplyGuyService()

        # Run analysis for the default content_creators list
        # This will re-fetch tweets and extract image URLs
        result = service.run_analysis(
            user_id='system',  # System user for default lists
            list_id='content_creators',
            list_type='default',
            time_range='24h'
        )

        if result:
            logger.info(f"✅ Successfully updated default list: {result}")
            logger.info("Image URLs should now be extracted for tweets with media")
        else:
            logger.error("❌ Failed to update default list")

    except Exception as e:
        logger.error(f"Error updating default list: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
