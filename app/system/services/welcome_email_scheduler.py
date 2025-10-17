"""
Background scheduler for sending delayed welcome emails
"""
import threading
import time
from datetime import datetime
import logging
from .email_service import email_service

logger = logging.getLogger(__name__)


class WelcomeEmailScheduler:
    """Schedules welcome emails to be sent after a delay"""

    def __init__(self):
        self.scheduled_emails = {}
        self.lock = threading.Lock()

    def schedule_welcome_email(self, user_email, user_name=None, delay_seconds=600):
        """
        Schedule a welcome email to be sent after a delay

        Args:
            user_email: User's email address
            user_name: User's name (optional)
            delay_seconds: Delay in seconds (default 600 = 10 minutes)
        """
        def send_delayed_email():
            time.sleep(delay_seconds)

            # Check if email was cancelled
            with self.lock:
                if user_email not in self.scheduled_emails:
                    logger.info(f"Welcome email for {user_email} was cancelled")
                    return

                # Remove from scheduled list
                del self.scheduled_emails[user_email]

            # Send the email
            logger.info(f"Sending scheduled welcome email to {user_email}")
            email_service.send_welcome_email(user_email, user_name)

        # Start background thread
        thread = threading.Thread(target=send_delayed_email, daemon=True)

        with self.lock:
            # Cancel any existing scheduled email for this user
            if user_email in self.scheduled_emails:
                logger.info(f"Replacing existing scheduled email for {user_email}")

            self.scheduled_emails[user_email] = {
                'thread': thread,
                'scheduled_at': datetime.now(),
                'name': user_name
            }

        thread.start()
        logger.info(f"Scheduled welcome email for {user_email} in {delay_seconds} seconds")

    def cancel_scheduled_email(self, user_email):
        """
        Cancel a scheduled welcome email (e.g., if user hasn't confirmed email)

        Args:
            user_email: User's email address
        """
        with self.lock:
            if user_email in self.scheduled_emails:
                del self.scheduled_emails[user_email]
                logger.info(f"Cancelled scheduled welcome email for {user_email}")
                return True
            return False


# Global scheduler instance
welcome_scheduler = WelcomeEmailScheduler()
