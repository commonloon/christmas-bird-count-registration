import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Email service with test mode support."""

    def __init__(self):
        self.test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
        self.test_recipient = 'birdcount@naturevancouver.ca'

        # SMTP configuration
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_username = os.environ.get('SMTP_USERNAME')
        self.smtp_password = os.environ.get('SMTP_PASSWORD')
        self.from_email = os.environ.get('FROM_EMAIL', 'birdcount@naturevancouver.ca')

        if self.test_mode:
            logger.info("Email service initialized in TEST MODE - all emails redirect to birdcount@naturevancouver.ca")
        else:
            logger.info("Email service initialized in PRODUCTION MODE")

    def send_email(self, to_addresses: List[str], subject: str, body: str,
                   html_body: str = None) -> bool:
        """Send email with test mode support."""
        try:
            if self.test_mode:
                return self._send_test_email(to_addresses, subject, body, html_body)
            else:
                return self._send_production_email(to_addresses, subject, body, html_body)
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _send_test_email(self, original_recipients: List[str], subject: str,
                         body: str, html_body: str = None) -> bool:
        """Send email in test mode - redirect to test recipient with modified content."""
        test_subject = f"[TEST - Would send to: {', '.join(original_recipients)}] {subject}"

        test_body = f"""
TEST MODE EMAIL
===============

INTENDED RECIPIENTS: {', '.join(original_recipients)}
ORIGINAL SUBJECT: {subject}
SENT AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ORIGINAL MESSAGE:
{'-' * 50}
{body}
        """

        test_html_body = None
        if html_body:
            test_html_body = f"""
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin-bottom: 20px;">
                <h3 style="color: #856404;">TEST MODE EMAIL</h3>
                <p><strong>Intended Recipients:</strong> {', '.join(original_recipients)}</p>
                <p><strong>Original Subject:</strong> {subject}</p>
                <p><strong>Sent At:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <div>
                <h4>Original Message:</h4>
                {html_body}
            </div>
            """

        return self._send_production_email([self.test_recipient], test_subject,
                                           test_body, test_html_body)

    def _send_production_email(self, to_addresses: List[str], subject: str,
                               body: str, html_body: str = None) -> bool:
        """Send email in production mode."""
        if not self.smtp_username or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = subject

            # Add plain text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)

            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {', '.join(to_addresses)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send production email: {e}")
            return False

    def send_unassigned_digest(self, admin_emails: List[str],
                               unassigned_participants: List[Dict]) -> bool:
        """Send daily digest of unassigned participants to admins."""
        if not unassigned_participants:
            return True  # No unassigned participants, nothing to send

        subject = f"CBC Registration: {len(unassigned_participants)} Unassigned Participants"

        body = f"""
Vancouver Christmas Bird Count - Daily Digest

There are {len(unassigned_participants)} participants who selected "Wherever I'm needed most" and need area assignment:

"""

        for i, participant in enumerate(unassigned_participants, 1):
            body += f"""
{i}. {participant.get('first_name', '')} {participant.get('last_name', '')}
   Email: {participant.get('email', '')}
   Phone: {participant.get('phone', 'Not provided')}
   Skill Level: {participant.get('skill_level', 'Not specified')}
   CBC Experience: {participant.get('experience', 'Not specified')}
   Leadership Interest: {'Yes' if participant.get('interested_in_leadership') else 'No'}
   Registered: {participant.get('created_at', 'Unknown').strftime('%Y-%m-%d %H:%M') if participant.get('created_at') else 'Unknown'}

"""

        body += f"""
Please log into the admin interface to assign these participants to areas:
https://cbc-registration.naturevancouver.ca/admin

This is an automated daily digest. You will receive this email each day until all participants are assigned.
        """

        return self.send_email(admin_emails, subject, body)

    def send_area_leader_update(self, leader_emails: List[str], area_code: str,
                                added_participants: List[Dict],
                                removed_participants: List[Dict]) -> bool:
        """Send area leader notification about team changes."""
        if not added_participants and not removed_participants:
            return True  # No changes to report

        subject = f"CBC Area {area_code} Team Update"

        body = f"""
Dear Area {area_code} Leader,

Your Christmas Bird Count team has been updated:

"""

        if added_participants:
            body += f"NEW TEAM MEMBERS ({len(added_participants)}):\n"
            for participant in added_participants:
                body += f"• {participant.get('first_name', '')} {participant.get('last_name', '')}\n"
                body += f"  Email: {participant.get('email', '')}\n"
                body += f"  Phone: {participant.get('phone', 'Not provided')}\n"
                body += f"  Skill: {participant.get('skill_level', 'Not specified')}\n"
                body += f"  Experience: {participant.get('experience', 'Not specified')}\n\n"

        if removed_participants:
            body += f"REMOVED TEAM MEMBERS ({len(removed_participants)}):\n"
            for removal in removed_participants:
                body += f"• {removal.get('participant_name', 'Unknown')}\n"
                if removal.get('reason'):
                    body += f"  Reason: {removal.get('reason')}\n"
                body += "\n"

        body += """
Please reach out to new team members to welcome them and provide count day details.

For the complete current team roster, visit: https://cbc-registration.naturevancouver.ca/leader

This is an automated notification from the CBC registration system.
        """

        return self.send_email(leader_emails, subject, body)

    def send_registration_confirmation(self, participant_email: str,
                                       participant_name: str, area_code: str) -> bool:
        """Send registration confirmation to participant."""
        subject = "Vancouver CBC Registration Confirmation"

        body = f"""
Dear {participant_name},

Thank you for registering for the Vancouver Christmas Bird Count!

REGISTRATION DETAILS:
• Name: {participant_name}
• Assigned Area: {area_code}
• Registration Date: {datetime.now().strftime('%Y-%m-%d')}

WHAT'S NEXT:
Your area leader will contact you with specific meeting details and count day information. Please check your email regularly for updates.

IMPORTANT REMINDERS:
• Bring warm, weather-appropriate clothing
• Binoculars are essential (contact us if you need to borrow a pair)
• The count typically begins early in the morning
• Please arrive at the designated meeting point on time

We look forward to seeing you on count day!

Best regards,
Nature Vancouver Christmas Bird Count Team

This is an automated confirmation. Please do not reply to this email.
        """

        return self.send_email([participant_email], subject, body)


# Global email service instance
email_service = EmailService()