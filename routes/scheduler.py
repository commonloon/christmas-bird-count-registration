# Updated by Claude AI on 2026-08-29
"""
Scheduler routes for automated email triggers.

These routes are designed to be called by FullHost's Task Scheduler for automated email
delivery. They are protected by a shared-secret bearer token (SCHEDULER_SECRET env var)
rather than OIDC, since this is no longer running on Google infrastructure.

Note: FullHost's exact Task Scheduler calling convention (HTTP hit vs. an in-container
command) hasn't been confirmed yet - this HTTP-based approach may need revisiting once
that's checked against the real dashboard.
"""

from flask import Blueprint, jsonify, request, current_app, session
from functools import wraps
import hmac
import logging
import os

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint('scheduler', __name__)


def require_cloud_scheduler(f):
    """Decorator to verify requests come from the Task Scheduler via a shared secret."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In TEST_MODE, allow admin-authenticated requests
        # This enables the admin dashboard test buttons to work
        if os.environ.get('TEST_MODE', 'false').lower() == 'true':
            # Check if this is an admin-authenticated session (dashboard button)
            from config.admins import get_admin_emails
            if session.get('user_email') in get_admin_emails():
                logger.info("Allowing scheduler request from authenticated admin in TEST_MODE")
                return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.warning(f"No valid Authorization header from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized - bearer token required'}), 403

        token = auth_header.split('Bearer ')[1]
        expected_secret = os.environ.get('SCHEDULER_SECRET', '')

        if not expected_secret:
            logger.error("SCHEDULER_SECRET is not configured - refusing all scheduler requests")
            return jsonify({'error': 'Scheduler not configured'}), 500

        if hmac.compare_digest(token, expected_secret):
            logger.info("Authenticated scheduler request")
            return f(*args, **kwargs)

        logger.warning(f"Invalid scheduler token from {request.remote_addr}")
        return jsonify({'error': 'Unauthorized'}), 403

    return decorated_function


@scheduler_bp.route('/trigger-team-updates', methods=['POST', 'GET'])
@require_cloud_scheduler
def trigger_team_updates():
    """
    Trigger twice-daily team update emails.
    Called by Cloud Scheduler at 10am and 4pm Pacific time.

    Returns JSON with results of email generation.
    """
    try:
        from test.email_generator import generate_team_update_emails

        logger.info("Cloud Scheduler triggered: team update emails")
        results = generate_team_update_emails(current_app)

        logger.info(f"Team updates completed: {results['emails_sent']} emails sent to {results['areas_processed']} areas")

        return jsonify({
            'success': True,
            'emails_sent': results['emails_sent'],
            'areas_processed': results['areas_processed'],
            'errors': results.get('errors', [])
        }), 200

    except Exception as e:
        logger.error(f"Error in trigger_team_updates: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_bp.route('/trigger-weekly-summaries', methods=['POST', 'GET'])
@require_cloud_scheduler
def trigger_weekly_summaries():
    """
    Trigger weekly summary emails for areas with no changes.
    Called by Cloud Scheduler on Fridays at 11pm Pacific time.

    Returns JSON with results of email generation.
    """
    try:
        from test.email_generator import generate_weekly_summary_emails

        logger.info("Cloud Scheduler triggered: weekly summary emails")
        results = generate_weekly_summary_emails(current_app)

        logger.info(f"Weekly summaries completed: {results['emails_sent']} emails sent to {results['areas_processed']} areas")

        return jsonify({
            'success': True,
            'emails_sent': results['emails_sent'],
            'areas_processed': results['areas_processed'],
            'errors': results.get('errors', [])
        }), 200

    except Exception as e:
        logger.error(f"Error in trigger_weekly_summaries: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_bp.route('/trigger-admin-digest', methods=['POST', 'GET'])
@require_cloud_scheduler
def trigger_admin_digest():
    """
    Trigger daily admin digest email.
    Called by Cloud Scheduler daily at 9am Pacific time.

    Returns JSON with results of email generation.
    """
    try:
        from test.email_generator import generate_admin_digest_email

        logger.info("Cloud Scheduler triggered: admin digest email")
        results = generate_admin_digest_email(current_app)

        if results['unassigned_count'] > 0:
            logger.info(f"Admin digest completed: {results['emails_sent']} email sent for {results['unassigned_count']} unassigned participants")
        else:
            logger.info("Admin digest: No unassigned participants, no email sent")

        return jsonify({
            'success': True,
            'emails_sent': results['emails_sent'],
            'unassigned_count': results['unassigned_count'],
            'errors': results.get('errors', [])
        }), 200

    except Exception as e:
        logger.error(f"Error in trigger_admin_digest: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduler_bp.route('/health', methods=['GET'])
def scheduler_health():
    """Health check endpoint for scheduler routes."""
    return jsonify({
        'status': 'healthy',
        'service': 'email-scheduler'
    }), 200
