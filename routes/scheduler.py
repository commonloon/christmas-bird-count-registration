# Updated by Claude AI on 2025-10-04
"""
Scheduler routes for automated email triggers.

These routes are designed to be called by Google Cloud Scheduler for automated email delivery.
They are protected by requiring specific headers that Cloud Scheduler includes.
"""

from flask import Blueprint, jsonify, request, current_app
from functools import wraps
import logging

logger = logging.getLogger(__name__)

scheduler_bp = Blueprint('scheduler', __name__)


def require_cloud_scheduler(f):
    """Decorator to verify requests come from Cloud Scheduler."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Cloud Scheduler sends requests with specific headers
        # Verify the request comes from Cloud Scheduler for security

        # Check for Cloud Scheduler user agent
        user_agent = request.headers.get('User-Agent', '')

        # Cloud Scheduler uses "Google-Cloud-Scheduler" in the user agent
        if 'Google-Cloud-Scheduler' in user_agent:
            logger.info(f"Scheduler request authenticated from Cloud Scheduler")
            return f(*args, **kwargs)

        # Also check for X-CloudScheduler custom header (can be set in Cloud Scheduler job)
        custom_header = request.headers.get('X-CloudScheduler', '')
        if custom_header == 'true':
            logger.info(f"Scheduler request authenticated via X-CloudScheduler header")
            return f(*args, **kwargs)

        # For development/testing, allow if TEST_MODE is enabled
        import os
        if os.environ.get('TEST_MODE', 'false').lower() == 'true':
            logger.warning("Allowing scheduler request in TEST_MODE without Cloud Scheduler headers")
            return f(*args, **kwargs)

        # Reject unauthorized requests
        logger.warning(f"Unauthorized scheduler request from {request.remote_addr} - User-Agent: {user_agent}")
        return jsonify({'error': 'Unauthorized - Cloud Scheduler access required'}), 403

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
