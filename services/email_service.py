# Updated by Claude AI on 2025-10-22
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging
from config.email_settings import get_email_config, get_available_providers
from config.organization import TEST_RECIPIENT, get_organization_variables

logger = logging.getLogger(__name__)


class EmailService:
    """Provider-agnostic email service with test mode support."""

    def __init__(self):
        self.config = get_email_config()
        self.test_recipient = TEST_RECIPIENT

        if self.config is None:
            logger.error("Email service not configured - missing credentials")
            logger.info(f"Available providers: {[p['name'] for p in get_available_providers()]}")
            self.smtp_server = None
            self.smtp_port = None
            self.smtp_username = None
            self.smtp_password = None
            self.from_email = None
            self.test_mode = True
        else:
            self.smtp_server = self.config['smtp_server']
            self.smtp_port = self.config['smtp_port']
            self.smtp_username = self.config['smtp_username']
            self.smtp_password = self.config['smtp_password']
            self.from_email = self.config['from_email']
            self.test_mode = self.config['test_mode']
            self.use_tls = self.config['use_tls']

            if self.test_mode:
                logger.info(f"Email service initialized in TEST MODE using {self.config['provider_description']} - all emails redirect to {self.test_recipient}")
            else:
                logger.info(f"Email service initialized in PRODUCTION MODE using {self.config['provider_description']}")

    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.config is not None

    def send_email(self, to_addresses: List[str], subject: str, body: str,
                   html_body: str = None) -> bool:
        """Send email with test mode support."""
        if not self.is_configured():
            logger.error("Cannot send email - service not configured")
            return False

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
            logger.error("Email credentials not configured")
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

            # Send email using configured provider settings
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {', '.join(to_addresses)} via {self.config['provider_name']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email via {self.config['provider_name']}: {e}")
            return False

    def send_unassigned_digest(self, admin_emails: List[str],
                               unassigned_participants: List[Dict]) -> bool:
        """Send daily digest of unassigned participants to admins."""
        if not unassigned_participants:
            return True  # No unassigned participants, nothing to send

        # Get organization variables from config
        org_vars = get_organization_variables()

        subject = f"CBC Registration: {len(unassigned_participants)} Unassigned Participants"

        body = f"""
{org_vars['count_event_name']} - Daily Digest

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
{org_vars['admin_url']}

This is an automated daily digest. You will receive this email each day until all participants are assigned.
        """

        return self.send_email(admin_emails, subject, body)

    def send_area_leader_update(self, leader_emails: List[str], area_code: str,
                                added_participants: List[Dict],
                                removed_participants: List[Dict]) -> bool:
        """Send area leader notification about team changes."""
        if not added_participants and not removed_participants:
            return True  # No changes to report

        # Get organization variables from config
        org_vars = get_organization_variables()

        subject = f"CBC Area {area_code} Team Update"

        body = f"""
Dear Area {area_code} Leader,

Your {org_vars['count_event_name']} team has been updated:

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

        body += f"""
Please reach out to new team members to welcome them and provide count day details.

For the complete current team roster, visit: {org_vars['leader_url']}

This is an automated notification from the CBC registration system.
        """

        return self.send_email(leader_emails, subject, body)

    def send_registration_confirmation(self, participant_data: dict, assigned_area: str) -> bool:
        """Send HTML registration confirmation email to participant."""
        from flask import current_app, render_template
        from config.email_settings import get_email_branding, is_test_server
        from config.areas import get_area_info
        from models.participant import ParticipantModel
        from services.datetime_utils import convert_to_display_timezone

        current_year = datetime.now().year
        utc_now = datetime.now(timezone.utc)
        registration_date, display_timezone = convert_to_display_timezone(utc_now)

        # Get area information
        if assigned_area != 'UNASSIGNED':
            area_info = get_area_info(assigned_area)

            # Get area leaders
            try:
                db, _ = self._get_db_client()
                participant_model = ParticipantModel(db, current_year)
                area_leaders = participant_model.get_leaders_by_area(assigned_area)
            except Exception as e:
                logger.error(f"Error getting area leaders: {e}")
                area_leaders = []
        else:
            area_info = None
            area_leaders = []

        # Get organization variables from config
        org_vars = get_organization_variables()

        # Prepare email context
        email_context = {
            'count_event_name': f'{current_year} {org_vars["count_event_name"]}',
            'registration_date': registration_date,
            'display_timezone': display_timezone,
            'assigned_area': assigned_area,
            'area_info': area_info,
            'area_leaders': area_leaders,
            'first_name': participant_data.get('first_name'),
            'last_name': participant_data.get('last_name'),
            'email': participant_data.get('email'),
            'phone': participant_data.get('phone'),
            'participation_type': participant_data.get('participation_type'),
            'skill_level': participant_data.get('skill_level'),
            'experience': participant_data.get('experience'),
            'has_binoculars': participant_data.get('has_binoculars', False),
            'spotting_scope': participant_data.get('spotting_scope', False),
            'interested_in_leadership': participant_data.get('interested_in_leadership', False),
            'interested_in_scribe': participant_data.get('interested_in_scribe', False),
            'notes_to_organizers': participant_data.get('notes_to_organizers'),
            'organization_name': org_vars['organization_name'],
            'count_contact': org_vars['count_contact'],
            'organization_contact': org_vars['organization_contact'],
            'count_info_url': org_vars['count_info_url'],
            'test_mode': is_test_server(),
            'branding': get_email_branding()
        }

        # Render HTML template
        try:
            with current_app.app_context():
                html_content = render_template('emails/registration_confirmation.html', **email_context)
        except Exception as e:
            logger.error(f"Error rendering registration confirmation template: {e}")
            # Fallback to simple text email
            html_content = None

        subject = f"{current_year} {org_vars['count_event_name']} Registration Confirmation"
        participant_email = participant_data.get('email')

        return self.send_email([participant_email], subject, '', html_content)

    def _get_db_client(self):
        """Get Firestore database client."""
        from config.database import get_firestore_client
        return get_firestore_client()


# Global email service instance
email_service = EmailService()