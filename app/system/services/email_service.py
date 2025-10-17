"""
Email service for sending transactional emails
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""

    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('SMTP_FROM_EMAIL', 'support@creatrics.com')
        self.from_name = os.getenv('SMTP_FROM_NAME', 'Creatrics')

    def send_email(self, to_email, subject, html_content, text_content=None):
        """
        Send an email via SMTP

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional, falls back to stripped HTML)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.smtp_username or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f'{self.from_name} <{self.from_email}>'
            msg['To'] = to_email

            # Add plain text part if provided
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)

            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def send_welcome_email(self, to_email, user_name=None):
        """
        Send welcome email to new user

        Args:
            to_email: User's email address
            user_name: User's name (optional)

        Returns:
            bool: True if sent successfully
        """
        try:
            # Render HTML template
            html_content = render_template(
                'emails/welcome.html',
                name=user_name or to_email.split('@')[0]
            )

            return self.send_email(
                to_email=to_email,
                subject='Welcome to Creatrics! 🎉',
                html_content=html_content
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False


# Global email service instance
email_service = EmailService()
