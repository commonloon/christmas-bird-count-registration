# Updated by Claude AI on 2025-10-24
#!/usr/bin/env python3
"""
Email Generation System for Vancouver CBC Registration

This module handles the generation and sending of automated emails:
1. Twice-daily team updates to area leaders
2. Weekly team summaries for ALL area leaders
3. Daily admin digest of unassigned participants

Implements race condition prevention and change detection logic.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from flask import render_template, current_app
from jinja2 import Template
import logging

from config.database import get_db_session
from config.organization import get_organization_variables
from models.db import EmailTimestamp, resolve_default_circle_slug
from config.admins import ADMIN_EMAILS
from config.email_settings import (
    is_test_server, get_admin_unassigned_url, get_leader_dashboard_url,
    get_email_branding
)
from models.participant import ParticipantModel
from models.removal_log import RemovalLogModel
from models.withdrawal_log import WithdrawalLogModel
from models.reassignment_log import ReassignmentLogModel
from models.circle import CircleAdminModel
from models.email_content import EmailContentModel
from services.email_service import email_service
from services.email_content_service import substitute_placeholders
from services.datetime_utils import convert_to_display_timezone

logger = logging.getLogger(__name__)


def _substitute_team_update_content(blocks, org_vars, area_code, date_str):
    """Substitute placeholders into an already-resolved team_update block set
    (EmailContentModel.resolve_all() called once per circle, outside the area
    loop - this just re-substitutes per area, no extra DB query). Returns
    (subject, greeting_intro_text, next_steps_text). Shared by the real send
    path and the admin email-content preview builder."""
    placeholder_values = {'date': date_str, 'count_event_name': org_vars['count_event_name'], 'area_code': area_code}
    subject = substitute_placeholders(blocks['subject'], placeholder_values)
    greeting_intro_text = substitute_placeholders(blocks['greeting_intro'], placeholder_values)
    next_steps_text = substitute_placeholders(blocks['next_steps_body'], placeholder_values)
    return subject, greeting_intro_text, next_steps_text


def _substitute_weekly_summary_content(blocks, org_vars, area_code, date_str):
    """Same as _substitute_team_update_content, for weekly_summary's two blocks."""
    placeholder_values = {'date': date_str, 'count_event_name': org_vars['count_event_name'], 'area_code': area_code}
    subject = substitute_placeholders(blocks['subject'], placeholder_values)
    next_steps_text = substitute_placeholders(blocks['next_steps_body'], placeholder_values)
    return subject, next_steps_text


def _substitute_admin_digest_content(blocks, org_vars, date_str):
    """Same as _substitute_team_update_content, for admin_digest's three blocks."""
    placeholder_values = {'date': date_str, 'count_event_name': org_vars['count_event_name']}
    subject = substitute_placeholders(blocks['subject'], placeholder_values)
    greeting_salutation_text = substitute_placeholders(blocks['greeting_salutation'], placeholder_values)
    recommended_actions_text = substitute_placeholders(blocks['recommended_actions_body'], placeholder_values)
    return subject, greeting_salutation_text, recommended_actions_text


def _push_circle_context(flask_app, circle_slug):
    """Push (and return, already-entered) a request context resolved to the given
    circle. Caller must pop it (e.g. in a finally block).

    These digest functions are triggered by the scheduler outside any real HTTP
    request, so every per-circle helper they rely on (ParticipantModel's
    circle_slug default via resolve_default_circle_slug(), config/organization.py's
    get_admin_url()/get_leader_url(), config/areas.py) has no request to read
    g.circle_slug from. Delegates to app.py's push_circle_context() (originally
    written here, moved there so services/email_service.py's preview builders
    could reuse the exact same logic - see that function's docstring).
    flask_app is unused (there's only ever one real Flask app instance) but kept
    as a parameter so existing call sites don't need to change.
    """
    import app as app_module
    return app_module.push_circle_context(circle_slug)


class EmailTimestampModel:
    """Handle email timestamp tracking to prevent race conditions."""

    def __init__(self, db_session, year: int = None, circle_slug: str = None):
        self.db = db_session
        self.year = year or datetime.now().year
        self.circle_slug = circle_slug or resolve_default_circle_slug()

    def get_last_email_sent(self, area_code: str, email_type: str) -> Optional[datetime]:
        """Get the last email sent timestamp for an area and email type."""
        try:
            row = self.db.query(EmailTimestamp).filter_by(
                circle_slug=self.circle_slug, year=self.year,
                area_code=area_code, email_type=email_type,
            ).first()
            return row.last_sent if row else None
        except Exception as e:
            logger.error(f"Error getting last email sent for {area_code}_{email_type}: {e}")
            return None

    def update_last_email_sent(self, area_code: str, email_type: str, timestamp: datetime) -> bool:
        """Update the last email sent timestamp for an area and email type."""
        try:
            row = self.db.query(EmailTimestamp).filter_by(
                circle_slug=self.circle_slug, year=self.year,
                area_code=area_code, email_type=email_type,
            ).first()
            if row:
                row.last_sent = timestamp
            else:
                self.db.add(EmailTimestamp(
                    circle_slug=self.circle_slug, year=self.year,
                    area_code=area_code, email_type=email_type, last_sent=timestamp,
                ))
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating last email sent for {area_code}_{email_type}: {e}")
            return False


def calculate_net_changes(all_reassignments: List[Dict], area_code: str) -> Tuple[List[Dict], List[Dict]]:
    """Calculate net changes for an area, handling multi-step reassignments.

    For each participant who was reassigned multiple times, this function traces their
    complete journey (original source → final destination) and filters out round-trips.

    Args:
        all_reassignments: List of all reassignment records since last email
        area_code: The area to filter by

    Returns:
        Tuple of (arrivals, departures) where each entry shows original_source→final_destination
        Round-trips (original == final) are excluded.
    """
    # Group reassignments by participant_id
    participant_moves = {}

    for reassignment in all_reassignments:
        participant_id = reassignment.get('participant_id')
        if not participant_id:
            continue

        if participant_id not in participant_moves:
            participant_moves[participant_id] = []
        participant_moves[participant_id].append(reassignment)

    arrivals = []
    departures = []

    # For each participant, calculate original source and final destination
    for participant_id, moves in participant_moves.items():
        # Sort by timestamp to get chronological order
        sorted_moves = sorted(moves, key=lambda x: x.get('changed_at', datetime.now(timezone.utc)))

        if not sorted_moves:
            continue

        # Original source is the old_area of the first move
        original_source = sorted_moves[0].get('old_area')
        # Final destination is the new_area of the last move
        final_destination = sorted_moves[-1].get('new_area')

        # Skip round-trips (original == final)
        if original_source == final_destination:
            logger.debug(f"Skipping round-trip for {participant_id}: {original_source} → {final_destination}")
            continue

        # Create a synthetic reassignment record showing original source to final destination
        # Use the last reassignment's data as base, but update old_area to original source
        final_reassignment = sorted_moves[-1].copy()
        final_reassignment['old_area'] = original_source
        # new_area is already correct (from the last move)

        # Determine if this is an arrival or departure relative to the area_code
        if final_destination == area_code:
            # Participant arrived at this area
            arrivals.append(final_reassignment)
        elif original_source == area_code:
            # Participant departed from this area
            departures.append(final_reassignment)

    return arrivals, departures


def calculate_net_withdrawal_reactivation_changes(
    participant_model: ParticipantModel,
    withdrawal_model: WithdrawalLogModel,
    area_code: str,
    since_timestamp: datetime
) -> Tuple[List[Dict], List[Dict]]:
    """Calculate net withdrawal/reactivation changes for an area.

    For participants who had multiple withdrawal/reactivation events, this calculates
    the NET state change (starting state vs ending state) and only reports that.

    Examples:
        - active → withdrawn → reactivated (net: no change, don't report)
        - active → withdrawn (net: withdrawn, report as withdrawn)
        - withdrawn → reactivated → withdrawn (net: withdrawn, report as withdrawn)

    Args:
        participant_model: Model to check current participant status
        withdrawal_model: Model to fetch withdrawal log entries
        area_code: The area to filter by
        since_timestamp: Only consider events after this timestamp

    Returns:
        Tuple of (net_withdrawals, net_reactivations) containing only participants
        with a net state change. Deleted participants are excluded (handled separately).
    """
    # Ensure timezone-aware
    if since_timestamp.tzinfo is None:
        since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)

    # Fetch withdrawal/reactivation log entries for this area since timestamp
    try:
        area_events = withdrawal_model.get_events_for_area_since(area_code, since_timestamp)
    except Exception as e:
        logger.error(f"Failed to get withdrawal events for area {area_code}: {e}")
        return [], []

    if not area_events:
        return [], []

    # Group events by participant_id
    from collections import defaultdict
    participant_events = defaultdict(list)
    for event in area_events:
        participant_id = event.get('participant_id')
        if participant_id:
            participant_events[participant_id].append(event)

    # Sort each participant's events by timestamp
    for participant_id in participant_events:
        participant_events[participant_id].sort(key=lambda x: x.get('recorded_at'))

    net_withdrawals = []
    net_reactivations = []

    # For each participant, calculate net change
    for participant_id, events in participant_events.items():
        # Get current participant status
        participant = participant_model.get_participant(participant_id)

        # If participant is deleted, skip (deletions handled by removal_log)
        if not participant:
            continue

        current_status = participant.get('status')

        # Determine starting status from first event
        first_event = events[0]
        if first_event.get('status') == 'withdrawn':
            starting_status = 'active'  # They were active before being withdrawn
        else:  # reactivated
            starting_status = 'withdrawn'  # They were withdrawn before being reactivated

        # Calculate net change: starting_status → current_status
        if starting_status == 'active' and current_status == 'withdrawn':
            # Net: withdrawn (report using last event for details)
            net_withdrawals.append(events[-1])
        elif starting_status == 'withdrawn' and current_status == 'active':
            # Net: reactivated (report using last event for details)
            net_reactivations.append(events[-1])
        # else: no net change (active→active or withdrawn→withdrawn), don't report

    return net_withdrawals, net_reactivations


def get_area_leaders_emails(participant_model: ParticipantModel, area_code: str) -> List[str]:
    """Get all email addresses for leaders of a specific area."""
    try:
        leaders = participant_model.get_leaders_by_area(area_code)
        emails = [leader['email'] for leader in leaders if leader.get('is_leader', False)]
        if is_test_server():
            logger.info(f"get_area_leaders_emails for area {area_code}: found {len(leaders)} leaders, returning {len(emails)} emails: {emails}")
        return emails
    except Exception as e:
        logger.error(f"Error getting leader emails for area {area_code}: {e}")
        return []


def calculate_skill_breakdown(participants: List[Dict]) -> Dict[str, int]:
    """Calculate skill level breakdown for participants."""
    breakdown = {}
    for participant in participants:
        skill = participant.get('skill_level', 'Not specified')
        breakdown[skill] = breakdown.get(skill, 0) + 1
    return breakdown


def calculate_experience_breakdown(participants: List[Dict]) -> Dict[str, int]:
    """Calculate CBC experience breakdown for participants."""
    breakdown = {}
    for participant in participants:
        exp = participant.get('experience', 'Not specified')
        breakdown[exp] = breakdown.get(exp, 0) + 1
    return breakdown


def get_participants_changes_since(participant_model: ParticipantModel, area_code: str,
                                   since_timestamp: datetime) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Get participants added, updated, and removed since the given timestamp.

    Returns:
        Tuple of (new_participants, updated_participants, removed_participants)
        - new_participants: created_at > since_timestamp
        - updated_participants: updated_at > since_timestamp AND created_at <= since_timestamp
        - removed_participants: from removal_log since timestamp
    """
    try:
        # Ensure since_timestamp is timezone-aware for comparison
        if since_timestamp.tzinfo is None:
            since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)

        # Get current participants for the area
        current_participants = participant_model.get_participants_by_area(area_code)

        # Classify participants: new vs updated
        new_participants = []
        updated_participants = []

        for participant in current_participants:
            created_at = participant.get('created_at')
            updated_at = participant.get('updated_at')

            # Ensure timestamps are timezone-aware for comparison
            if created_at and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if updated_at and updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)

            # Check if participant was recently assigned to this area
            assigned_at = participant.get('assigned_at')
            if assigned_at and assigned_at.tzinfo is None:
                assigned_at = assigned_at.replace(tzinfo=timezone.utc)

            # New participant: created after last email
            if created_at and created_at > since_timestamp:
                new_participants.append(participant)
            # Recently assigned to this area (from UNASSIGNED or different area)
            elif assigned_at and assigned_at > since_timestamp:
                new_participants.append(participant)
            # Updated participant: updated after last email but created before
            elif updated_at and updated_at > since_timestamp:
                if created_at and created_at <= since_timestamp:
                    # This is a participant info update (not a new registration or reassignment)
                    updated_participants.append(participant)

        # Get removed participants from removal log
        removal_model = RemovalLogModel(participant_model.db, participant_model.year)
        removed_participants = removal_model.get_removals_since(area_code, since_timestamp)

        return new_participants, updated_participants, removed_participants

    except Exception as e:
        logger.error(f"Error getting participant changes for area {area_code} since {since_timestamp}: {e}")
        return [], [], []


def generate_team_update_emails(app, circle_slug) -> Dict[str, Any]:
    """Generate twice-daily team update emails for areas with changes, for one circle."""
    ctx = None
    try:
        ctx = _push_circle_context(app, circle_slug)
        db = get_db_session()
        current_year = datetime.now().year
        utc_now = datetime.now(timezone.utc)  # Race condition prevention: pick timestamp first
        current_time, display_timezone = convert_to_display_timezone(utc_now)
        org_vars = get_organization_variables()
        content_blocks = EmailContentModel(db).resolve_all(circle_slug, 'team_update')

        participant_model = ParticipantModel(db, current_year)
        timestamp_model = EmailTimestampModel(db, current_year)

        results = {
            'emails_sent': 0,
            'areas_processed': 0,
            'errors': []
        }

        # Get all areas that have leaders
        all_leaders = participant_model.get_leaders()
        areas_with_leaders = set(leader['assigned_area_leader'] for leader in all_leaders if leader.get('is_leader', False))
        
        for area_code in areas_with_leaders:
            try:
                results['areas_processed'] += 1
                
                # Get last email sent timestamp
                last_email_sent = timestamp_model.get_last_email_sent(area_code, 'team_update')
                if not last_email_sent:
                    # First time sending - use 24 hours ago as baseline
                    last_email_sent = current_time - timedelta(days=1)

                # Get changes since last email
                new_participants, updated_participants, removed_participants = get_participants_changes_since(
                    participant_model, area_code, last_email_sent
                )

                # Get reassignments affecting this area (with net change calculation)
                reassignment_model = ReassignmentLogModel(db, current_year)
                all_reassignments = reassignment_model.get_reassignments_since(last_email_sent)
                arrivals, departures = calculate_net_changes(all_reassignments, area_code)

                # Get NET withdrawal/reactivation changes (filters out intermediate state changes)
                withdrawal_model = WithdrawalLogModel(db, current_year)
                withdrawn_participants_changes, reactivated_participants = calculate_net_withdrawal_reactivation_changes(
                    participant_model, withdrawal_model, area_code, last_email_sent
                )

                # Filter out participants from "updated" list if they were round-trip reassignments
                # A participant is a round-trip if they appear in all_reassignments but not in arrivals/departures
                reassigned_participant_ids = set()
                for reassignment in all_reassignments:
                    reassigned_participant_ids.add(reassignment.get('participant_id'))

                # Get net change participant IDs (those that aren't round-trips)
                net_change_participant_ids = set()
                for arrival in arrivals:
                    net_change_participant_ids.add(arrival.get('participant_id'))
                for departure in departures:
                    net_change_participant_ids.add(departure.get('participant_id'))

                # Remove updated participants that were reassigned but have no net change
                updated_participants = [
                    p for p in updated_participants
                    if p.get('id') not in (reassigned_participant_ids - net_change_participant_ids)
                ]

                # Only send email if there are changes (including net reassignments, withdrawals, and reactivations)
                if not new_participants and not updated_participants and not removed_participants and not arrivals and not departures and not withdrawn_participants_changes and not reactivated_participants:
                    logger.info(f"No changes for area {area_code}, skipping team update email")
                    continue
                
                # Get leader emails and names
                leader_emails = get_area_leaders_emails(participant_model, area_code)
                if not leader_emails:
                    logger.warning(f"No leader emails found for area {area_code}")
                    continue

                # Get leader names for display
                leaders = participant_model.get_leaders_by_area(area_code)
                leader_names = [f"{leader.get('first_name', '')} {leader.get('last_name', '')}".strip()
                              for leader in leaders if leader.get('is_leader', False)]
                
                # Get current team roster (active and withdrawn)
                current_team = participant_model.get_participants_by_area(area_code)
                withdrawn_participants = participant_model.get_withdrawn_participants_by_area(area_code)
                current_team = current_team + withdrawn_participants

                subject, greeting_intro_text, next_steps_text = _substitute_team_update_content(
                    content_blocks, org_vars, area_code, current_time.strftime('%Y-%m-%d'))

                # Prepare email context
                email_context = {
                    'area_code': area_code,
                    'leader_names': leader_names,
                    'new_participants': new_participants,
                    'updated_participants': updated_participants,
                    'removed_participants': removed_participants,
                    'arrivals': arrivals,
                    'departures': departures,
                    'withdrawn_participants': withdrawn_participants_changes,
                    'reactivated_participants': reactivated_participants,
                    'current_team': current_team,
                    'current_date': current_time,
                    'display_timezone': display_timezone,
                    'leader_dashboard_url': get_leader_dashboard_url(),
                    'test_mode': is_test_server(),
                    'branding': get_email_branding(),
                    'count_event_name': org_vars['count_event_name'],
                    'greeting_intro_text': greeting_intro_text,
                    'next_steps_text': next_steps_text,
                }

                # Render email template
                try:
                    with app.app_context():
                        html_content = render_template('emails/team_update.html', **email_context)
                except Exception as template_error:
                    logger.error(f"Template rendering error for area {area_code}: {template_error}")
                    # Fallback to basic text email
                    html_content = None

                # Send email
                if email_service.send_email(leader_emails, subject, '', html_content,
                                             from_email=org_vars['from_email'],
                                             test_recipient=org_vars['test_recipient']):
                    # Update timestamp AFTER successful send
                    timestamp_model.update_last_email_sent(area_code, 'team_update', current_time)
                    results['emails_sent'] += 1
                    logger.info(f"Team update email sent for area {area_code} to {len(leader_emails)} leaders")
                else:
                    results['errors'].append(f"Failed to send team update email for area {area_code}")
                    
            except Exception as e:
                error_msg = f"Error processing team update for area {area_code}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        logger.info(f"Team update emails completed: {results['emails_sent']} sent, {results['areas_processed']} areas processed")
        return results

    except Exception as e:
        logger.error(f"Critical error in generate_team_update_emails: {e}")
        return {'emails_sent': 0, 'areas_processed': 0, 'errors': [str(e)]}
    finally:
        if ctx:
            ctx.pop()


def generate_weekly_summary_emails(app, circle_slug) -> Dict[str, Any]:
    """Generate weekly summary emails for ALL area leaders."""
    ctx = None
    try:
        ctx = _push_circle_context(app, circle_slug)
        db = get_db_session()
        current_year = datetime.now().year
        utc_now = datetime.now(timezone.utc)
        current_time, display_timezone = convert_to_display_timezone(utc_now)
        org_vars = get_organization_variables()
        content_blocks = EmailContentModel(db).resolve_all(circle_slug, 'weekly_summary')

        participant_model = ParticipantModel(db, current_year)
        timestamp_model = EmailTimestampModel(db, current_year)

        results = {
            'emails_sent': 0,
            'areas_processed': 0,
            'errors': []
        }

        # Get all areas that have leaders
        all_leaders = participant_model.get_leaders()
        areas_with_leaders = set(leader['assigned_area_leader'] for leader in all_leaders if leader.get('is_leader', False))

        for area_code in areas_with_leaders:
            try:
                results['areas_processed'] += 1

                # Get last weekly summary timestamp (not team update timestamp)
                last_weekly_summary = timestamp_model.get_last_email_sent(area_code, 'weekly_summary')
                if last_weekly_summary is None:
                    # Default to one week ago if no previous weekly summary
                    last_weekly_summary = current_time - timedelta(days=7)

                # Check for changes since last weekly summary
                new_participants, updated_participants, removed_participants = get_participants_changes_since(
                    participant_model, area_code, last_weekly_summary
                )

                # Get reassignments affecting this area (with net change calculation)
                reassignment_model = ReassignmentLogModel(db, current_year)
                all_reassignments = reassignment_model.get_reassignments_since(last_weekly_summary)
                arrivals, departures = calculate_net_changes(all_reassignments, area_code)

                # Get NET withdrawal/reactivation changes (filters out intermediate state changes)
                withdrawal_model = WithdrawalLogModel(db, current_year)
                withdrawn_participants_changes, reactivated_participants = calculate_net_withdrawal_reactivation_changes(
                    participant_model, withdrawal_model, area_code, last_weekly_summary
                )

                # Filter out participants from "updated" list if they were round-trip reassignments
                reassigned_participant_ids = set()
                for reassignment in all_reassignments:
                    reassigned_participant_ids.add(reassignment.get('participant_id'))

                # Get net change participant IDs (those that aren't round-trips)
                net_change_participant_ids = set()
                for arrival in arrivals:
                    net_change_participant_ids.add(arrival.get('participant_id'))
                for departure in departures:
                    net_change_participant_ids.add(departure.get('participant_id'))

                # Remove updated participants that were reassigned but have no net change
                updated_participants = [
                    p for p in updated_participants
                    if p.get('id') not in (reassigned_participant_ids - net_change_participant_ids)
                ]

                has_changes = bool(new_participants or updated_participants or removed_participants or arrivals or departures or withdrawn_participants_changes or reactivated_participants)

                # Send weekly summary to ALL leaders regardless of changes
                # Get leader emails and names
                leader_emails = get_area_leaders_emails(participant_model, area_code)
                if not leader_emails:
                    logger.warning(f"No leader emails found for area {area_code}")
                    continue

                leaders = participant_model.get_leaders_by_area(area_code)
                leader_names = [f"{leader.get('first_name', '')} {leader.get('last_name', '')}".strip()
                              for leader in leaders if leader.get('is_leader', False)]

                # Get current team and statistics (active and withdrawn)
                current_team = participant_model.get_participants_by_area(area_code)
                withdrawn_participants = participant_model.get_withdrawn_participants_by_area(area_code)
                current_team = current_team + withdrawn_participants
                skill_breakdown = calculate_skill_breakdown(current_team)
                experience_breakdown = calculate_experience_breakdown(current_team)
                leadership_interest_count = sum(1 for p in current_team if p.get('interested_in_leadership'))
                
                subject, next_steps_text = _substitute_weekly_summary_content(
                    content_blocks, org_vars, area_code, current_time.strftime('%Y-%m-%d'))

                # Prepare email context
                email_context = {
                    'area_code': area_code,
                    'leader_names': leader_names,
                    'new_participants': new_participants,
                    'updated_participants': updated_participants,
                    'removed_participants': removed_participants,
                    'arrivals': arrivals,
                    'departures': departures,
                    'withdrawn_participants': withdrawn_participants_changes,
                    'reactivated_participants': reactivated_participants,
                    'current_team': current_team,
                    'has_changes': has_changes,
                    'skill_breakdown': skill_breakdown,
                    'experience_breakdown': experience_breakdown,
                    'leadership_interest_count': leadership_interest_count,
                    'current_date': current_time,
                    'display_timezone': display_timezone,
                    'leader_dashboard_url': get_leader_dashboard_url(),
                    'test_mode': is_test_server(),
                    'branding': get_email_branding(),
                    'count_event_name': org_vars['count_event_name'],
                    'next_steps_text': next_steps_text,
                }

                # Render email template
                try:
                    with app.app_context():
                        html_content = render_template('emails/weekly_summary.html', **email_context)
                except Exception as template_error:
                    logger.error(f"Template rendering error for weekly summary {area_code}: {template_error}")
                    # Fallback to basic text email
                    html_content = None

                # Send email
                if email_service.send_email(leader_emails, subject, '', html_content,
                                             from_email=org_vars['from_email'],
                                             test_recipient=org_vars['test_recipient']):
                    # Update timestamp AFTER successful send
                    timestamp_model.update_last_email_sent(area_code, 'weekly_summary', current_time)
                    results['emails_sent'] += 1
                    logger.info(f"Weekly summary email sent for area {area_code} to {len(leader_emails)} leaders")
                else:
                    results['errors'].append(f"Failed to send weekly summary email for area {area_code}")
                    
            except Exception as e:
                error_msg = f"Error processing weekly summary for area {area_code}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        logger.info(f"Weekly summary emails completed: {results['emails_sent']} sent, {results['areas_processed']} areas processed")
        return results

    except Exception as e:
        logger.error(f"Critical error in generate_weekly_summary_emails: {e}")
        return {'emails_sent': 0, 'areas_processed': 0, 'errors': [str(e)]}
    finally:
        if ctx:
            ctx.pop()


def generate_admin_digest_email(app, circle_slug) -> Dict[str, Any]:
    """Generate daily admin digest with unassigned participants, for one circle."""
    ctx = None
    try:
        ctx = _push_circle_context(app, circle_slug)
        db = get_db_session()
        current_year = datetime.now().year
        utc_now = datetime.now(timezone.utc)
        current_time, display_timezone = convert_to_display_timezone(utc_now)
        utc_for_calcs = utc_now  # Keep UTC version for calculations

        participant_model = ParticipantModel(db, current_year)
        
        results = {
            'emails_sent': 0,
            'unassigned_count': 0,
            'errors': []
        }
        
        # Get unassigned participants
        unassigned_participants = participant_model.get_unassigned_participants()
        results['unassigned_count'] = len(unassigned_participants)
        
        if not unassigned_participants:
            logger.info("No unassigned participants, skipping admin digest email")
            return results
        
        # Calculate statistics
        leadership_interest_count = sum(1 for p in unassigned_participants if p.get('interested_in_leadership'))
        
        # Calculate days waiting for each participant
        days_waiting = []
        total_wait_days = 0
        
        for participant in unassigned_participants:
            created_at = participant.get('created_at')
            if created_at:
                # Ensure created_at is timezone-aware for comparison
                if created_at.tzinfo is None:
                    # If naive, assume UTC
                    created_at = created_at.replace(tzinfo=timezone.utc)

                days_wait = (utc_for_calcs - created_at).days
                days_waiting.append(days_wait)
                total_wait_days += days_wait
            else:
                days_waiting.append(0)
        
        average_wait_days = round(total_wait_days / len(unassigned_participants)) if unassigned_participants else 0
        
        org_vars = get_organization_variables()
        content_blocks = EmailContentModel(db).resolve_all(circle_slug, 'admin_digest')
        subject, greeting_salutation_text, recommended_actions_text = _substitute_admin_digest_content(
            content_blocks, org_vars, current_time.strftime('%Y-%m-%d'))

        # Prepare email context
        email_context = {
            'unassigned_participants': unassigned_participants,
            'leadership_interest_count': leadership_interest_count,
            'days_waiting': days_waiting,
            'average_wait_days': average_wait_days,
            'current_date': current_time,
            'display_timezone': display_timezone,
            'admin_unassigned_url': get_admin_unassigned_url(),
            'test_mode': is_test_server(),
            'branding': get_email_branding(),
            'count_event_name': org_vars['count_event_name'],
            'count_experience_label': org_vars['count_experience_label'],
            'greeting_salutation_text': greeting_salutation_text,
            'recommended_actions_text': recommended_actions_text,
        }

        # Render email template
        try:
            with app.app_context():
                html_content = render_template('emails/admin_digest.html', **email_context)
        except Exception as template_error:
            logger.error(f"Template rendering error for admin digest: {template_error}")
            # Fallback to basic text email
            html_content = None

        # Recipients: union of this circle's own circle-admins and the global
        # super-admin whitelist - backward-compatible (Vancouver's admins are
        # already in ADMIN_EMAILS, so its behavior is unchanged) and ensures a
        # circle with no self-service admins configured yet still gets its digest.
        circle_admin_emails = [a['email'] for a in CircleAdminModel(db).get_admins_for_circle(circle_slug)]
        recipients = sorted(set(circle_admin_emails) | set(ADMIN_EMAILS))

        # Send email to all admins
        if email_service.send_email(recipients, subject, '', html_content,
                                     from_email=org_vars['from_email'],
                                     test_recipient=org_vars['test_recipient']):
            results['emails_sent'] = 1
            logger.info(f"Admin digest email sent to {len(recipients)} admins for {len(unassigned_participants)} unassigned participants")
        else:
            results['errors'].append("Failed to send admin digest email")
        
        logger.info(f"Admin digest email completed: {results['unassigned_count']} unassigned participants")
        return results

    except Exception as e:
        logger.error(f"Critical error in generate_admin_digest_email: {e}")
        return {'emails_sent': 0, 'unassigned_count': 0, 'errors': [str(e)]}
    finally:
        if ctx:
            ctx.pop()


def _sample_participant(**overrides):
    """A synthetic sample participant dict for the digest-email preview builders
    below - never real data. Matches the field shape ParticipantModel rows
    actually have, so it renders through the real templates identically to a
    genuine participant."""
    sample = {
        'first_name': 'Sample', 'last_name': 'Participant', 'email': 'sample@example.com',
        'phone': '(555) 555-6789', 'skill_level': 'Intermediate', 'experience': '1-2 counts',
        'participation_type': 'regular', 'status': 'active', 'has_binoculars': True,
        'spotting_scope': False, 'is_leader': False, 'assigned_area_leader': None,
        'interested_in_leadership': False, 'notes_to_organizers': '',
        'created_at': datetime.now(timezone.utc),
    }
    sample.update(overrides)
    return sample


def build_team_update_preview(circle_slug):
    """Render the real team_update template with synthetic sample data and this
    circle's currently-saved (resolved) email-content blocks, for the admin
    email-content preview route. Never sends anything.

    Reachable via routes/admin.py's CIRCLE_CONSOLE_ENDPOINTS from any host, so the
    ambient request's own g.circle may be a different circle than circle_slug (or
    None) - org_vars/branding/dashboard URL must come from circle_slug explicitly
    via a pushed context (same _push_circle_context() the real, scheduler-triggered
    generate_team_update_emails() needs), not any of these helpers' ambient lookup,
    or this could preview circle_slug's content dressed in another circle's
    identity/URLs."""
    import app as app_module

    db = get_db_session()
    ctx = app_module.push_circle_context(circle_slug)
    try:
        org_vars = get_organization_variables()
        current_time, display_timezone = convert_to_display_timezone(datetime.now(timezone.utc))
        leader_dashboard_url = get_leader_dashboard_url()
        branding = get_email_branding()
    finally:
        ctx.pop()

    content_blocks = EmailContentModel(db).resolve_all(circle_slug, 'team_update')
    subject, greeting_intro_text, next_steps_text = _substitute_team_update_content(
        content_blocks, org_vars, 'A', current_time.strftime('%Y-%m-%d'))

    sample = _sample_participant()
    email_context = {
        'area_code': 'A',
        'leader_names': ['Sample Leader'],
        'new_participants': [sample],
        'updated_participants': [],
        'removed_participants': [],
        'arrivals': [],
        'departures': [],
        'withdrawn_participants': [],
        'reactivated_participants': [],
        'current_team': [sample],
        'current_date': current_time,
        'display_timezone': display_timezone,
        'leader_dashboard_url': leader_dashboard_url,
        'test_mode': is_test_server(),
        'branding': branding,
        'count_event_name': org_vars['count_event_name'],
        'greeting_intro_text': greeting_intro_text,
        'next_steps_text': next_steps_text,
    }

    with current_app.app_context():
        html_content = render_template('emails/team_update.html', **email_context)
    return subject, html_content


def build_weekly_summary_preview(circle_slug):
    """Same as build_team_update_preview, for weekly_summary."""
    import app as app_module

    db = get_db_session()
    ctx = app_module.push_circle_context(circle_slug)
    try:
        org_vars = get_organization_variables()
        current_time, display_timezone = convert_to_display_timezone(datetime.now(timezone.utc))
        leader_dashboard_url = get_leader_dashboard_url()
        branding = get_email_branding()
    finally:
        ctx.pop()

    content_blocks = EmailContentModel(db).resolve_all(circle_slug, 'weekly_summary')
    subject, next_steps_text = _substitute_weekly_summary_content(
        content_blocks, org_vars, 'A', current_time.strftime('%Y-%m-%d'))

    sample = _sample_participant()
    current_team = [sample]
    email_context = {
        'area_code': 'A',
        'leader_names': ['Sample Leader'],
        'new_participants': [sample],
        'updated_participants': [],
        'removed_participants': [],
        'arrivals': [],
        'departures': [],
        'withdrawn_participants': [],
        'reactivated_participants': [],
        'current_team': current_team,
        'has_changes': True,
        'skill_breakdown': calculate_skill_breakdown(current_team),
        'experience_breakdown': calculate_experience_breakdown(current_team),
        'leadership_interest_count': 0,
        'current_date': current_time,
        'display_timezone': display_timezone,
        'leader_dashboard_url': leader_dashboard_url,
        'test_mode': is_test_server(),
        'branding': branding,
        'count_event_name': org_vars['count_event_name'],
        'next_steps_text': next_steps_text,
    }

    with current_app.app_context():
        html_content = render_template('emails/weekly_summary.html', **email_context)
    return subject, html_content


def build_admin_digest_preview(circle_slug):
    """Same as build_team_update_preview, for admin_digest."""
    import app as app_module

    db = get_db_session()
    ctx = app_module.push_circle_context(circle_slug)
    try:
        org_vars = get_organization_variables()
        current_time, display_timezone = convert_to_display_timezone(datetime.now(timezone.utc))
        admin_unassigned_url = get_admin_unassigned_url()
        branding = get_email_branding()
    finally:
        ctx.pop()

    content_blocks = EmailContentModel(db).resolve_all(circle_slug, 'admin_digest')
    subject, greeting_salutation_text, recommended_actions_text = _substitute_admin_digest_content(
        content_blocks, org_vars, current_time.strftime('%Y-%m-%d'))

    sample = _sample_participant(interested_in_leadership=True)
    email_context = {
        'unassigned_participants': [sample],
        'leadership_interest_count': 1,
        'days_waiting': [3],
        'average_wait_days': 3,
        'current_date': current_time,
        'display_timezone': display_timezone,
        'admin_unassigned_url': admin_unassigned_url,
        'test_mode': is_test_server(),
        'branding': branding,
        'count_event_name': org_vars['count_event_name'],
        'count_experience_label': org_vars['count_experience_label'],
        'greeting_salutation_text': greeting_salutation_text,
        'recommended_actions_text': recommended_actions_text,
    }

    with current_app.app_context():
        html_content = render_template('emails/admin_digest.html', **email_context)
    return subject, html_content


if __name__ == '__main__':
    # Command line testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CBC emails')
    parser.add_argument('--type', choices=['team_update', 'weekly_summary', 'admin_digest'],
                       help='Email type to generate')
    parser.add_argument('--circle', required=True, help='Circle slug to generate for (e.g. vancouver)')
    parser.add_argument('--test', action='store_true', help='Enable test mode')

    args = parser.parse_args()

    if args.test:
        os.environ['TEST_MODE'] = 'true'

    logging.basicConfig(level=logging.INFO)

    from app import app as flask_app

    if args.type == 'team_update':
        results = generate_team_update_emails(flask_app, args.circle)
    elif args.type == 'weekly_summary':
        results = generate_weekly_summary_emails(flask_app, args.circle)
    elif args.type == 'admin_digest':
        results = generate_admin_digest_email(flask_app, args.circle)
    else:
        print("Please specify --type (team_update, weekly_summary, or admin_digest)")
        sys.exit(1)

    print(f"Results: {results}")