import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailService:
    """Handles sending wellness alerts via SMTP."""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = os.getenv("SMTP_PORT", 587)
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")

    def send_trusted_contact_alert(self, user_name: str, contact_email: str):
        message_body = f"""Hello,

This is an automated message from MoodJournal.

Your trusted contact, {user_name}, has been experiencing consistently low emotional moods for the past 15 days. This notification is being sent because you were selected as their trusted support contact.

Please consider checking in with them and offering support if appropriate.

This alert is not a medical diagnosis and is only intended as a wellness support feature.

— MindJournal Support System
"""
        
        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = contact_email
        msg['Subject'] = f"Wellness Alert: {user_name}"
        msg.attach(MIMEText(message_body, 'plain'))

        if not self.smtp_user or not self.smtp_pass:
            return False, "SMTP credentials missing in .env"

        try:
            # REAL SMTP SENDING
            server = smtplib.SMTP(self.smtp_host, int(self.smtp_port))
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)
            server.quit()
            return True, None
        except Exception as e:
            print(f"[SMTP ERROR] {e}")
            return False, str(e)
