#!/usr/bin/env python3
"""
Email Generation System for Vancouver CBC Registration

This module handles the generation and sending of automated emails:
1. Twice-daily team updates to area leaders
2. Weekly team summaries for areas with no changes  
3. Daily admin digest of unassigned participants

Implements race condition prevention and change detection logic.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from flask import render_template, current_app
from jinja2 import Template
from google.cloud import firestore
import logging

from config.database import get_firestore_client
from config.admins import ADMIN_EMAILS
from config.email_settings import (
    is_test_server, get_admin_unassigned_url, get_leader_dashboard_url,
    EMAIL_SUBJECTS
)
from models.participant import ParticipantModel
from models.removal_log import RemovalLogModel
from services.email_service import email_service

logger = logging.getLogger(__name__)


class EmailTimestampModel:
    """Handle email timestamp tracking to prevent race conditions."""
    
    def __init__(self, db_client, year: int = None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'email_timestamps_{self.year}'
    
    def get_last_email_sent(self, area_code: str, email_type: str) -> Optional[datetime]:
        """Get the last email sent timestamp for an area and email type."""
        try:
            doc_ref = self.db.collection(self.collection).document(f'{area_code}_{email_type}')
            doc = doc_ref.get()
            if doc.exists:
                return doc.get('last_sent')
            return None
        except Exception as e:
            logger.error(f"Error getting last email sent for {area_code}_{email_type}: {e}")
            return None
    
    def update_last_email_sent(self, area_code: str, email_type: str, timestamp: datetime) -> bool:
        """Update the last email sent timestamp for an area and email type."""
        try:
            doc_ref = self.db.collection(self.collection).document(f'{area_code}_{email_type}')
            doc_ref.set({
                'area_code': area_code,
                'email_type': email_type,
                'last_sent': timestamp,
                'year': self.year
            })
            return True
        except Exception as e:
            logger.error(f"Error updating last email sent for {area_code}_{email_type}: {e}")
            return False


def get_area_leaders_emails(participant_model: ParticipantModel, area_code: str) -> List[str]:
    """Get all email addresses for leaders of a specific area."""
    try:
        leaders = participant_model.get_leaders_by_area(area_code)
        return [leader['email'] for leader in leaders if leader.get('is_leader', False)]
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
                                   since_timestamp: datetime) -> Tuple[List[Dict], List[Dict]]:
    """Get participants added and removed since the given timestamp."""
    try:
        # Ensure since_timestamp is timezone-aware for comparison
        if since_timestamp.tzinfo is None:
            since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)
        
        # Get current participants for the area
        current_participants = participant_model.get_participants_by_area(area_code)
        
        # Get recently added participants (created or updated since timestamp)
        new_participants = []
        for participant in current_participants:
            created_at = participant.get('created_at')
            updated_at = participant.get('updated_at')
            
            # Handle created_at comparison
            if created_at:
                # Ensure created_at is timezone-aware for comparison
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                if created_at > since_timestamp:
                    new_participants.append(participant)
                    continue
            
            # Handle updated_at comparison
            if updated_at:
                # Ensure updated_at is timezone-aware for comparison
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                
                if updated_at > since_timestamp:
                    # Check if this was an area reassignment to this area
                    if participant.get('preferred_area') == area_code:
                        new_participants.append(participant)
        
        # Get removed participants from removal log
        removal_model = RemovalLogModel(participant_model.db, participant_model.year)
        removed_participants = removal_model.get_removals_since(area_code, since_timestamp)
        
        return new_participants, removed_participants
        
    except Exception as e:
        logger.error(f"Error getting participant changes for area {area_code} since {since_timestamp}: {e}")
        return [], []


def generate_team_update_emails(app=None) -> Dict[str, Any]:
    """Generate twice-daily team update emails for areas with changes."""
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        current_time = datetime.utcnow()  # Race condition prevention: pick timestamp first
        
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
                new_participants, removed_participants = get_participants_changes_since(
                    participant_model, area_code, last_email_sent
                )
                
                # Only send email if there are changes
                if not new_participants and not removed_participants:
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
                
                # Get current team roster
                current_team = participant_model.get_participants_by_area(area_code)
                
                # Prepare email context
                email_context = {
                    'area_code': area_code,
                    'leader_names': leader_names,
                    'new_participants': new_participants,
                    'removed_participants': removed_participants,
                    'current_team': current_team,
                    'current_date': current_time,
                    'leader_dashboard_url': get_leader_dashboard_url(),
                    'test_mode': is_test_server()
                }
                
                # Render email template
                try:
                    if app:
                        with app.app_context():
                            html_content = render_template('emails/team_update.html', **email_context)
                    else:
                        # Fallback to basic text if no app context
                        html_content = None
                except Exception as template_error:
                    logger.error(f"Template rendering error for area {area_code}: {template_error}")
                    # Fallback to basic text email
                    html_content = None
                subject = EMAIL_SUBJECTS['team_update'].format(area_code=area_code)
                
                # Send email
                if email_service.send_email(leader_emails, subject, '', html_content):
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


def generate_weekly_summary_emails(app=None) -> Dict[str, Any]:
    """Generate weekly summary emails for areas with no changes in the past week."""
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        current_time = datetime.utcnow()
        one_week_ago = current_time - timedelta(days=7)
        
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
                
                # Check if there have been changes in the past week
                new_participants, removed_participants = get_participants_changes_since(
                    participant_model, area_code, one_week_ago
                )
                
                # Only send weekly summary if NO changes in past week
                if new_participants or removed_participants:
                    logger.info(f"Area {area_code} has recent changes, skipping weekly summary")
                    continue
                
                # Get leader emails and names
                leader_emails = get_area_leaders_emails(participant_model, area_code)
                if not leader_emails:
                    logger.warning(f"No leader emails found for area {area_code}")
                    continue

                leaders = participant_model.get_leaders_by_area(area_code)
                leader_names = [f"{leader.get('first_name', '')} {leader.get('last_name', '')}".strip()
                              for leader in leaders if leader.get('is_leader', False)]
                
                # Get current team and statistics
                current_team = participant_model.get_participants_by_area(area_code)
                skill_breakdown = calculate_skill_breakdown(current_team)
                experience_breakdown = calculate_experience_breakdown(current_team)
                leadership_interest_count = sum(1 for p in current_team if p.get('interested_in_leadership'))
                
                # Prepare email context
                email_context = {
                    'area_code': area_code,
                    'leader_names': leader_names,
                    'current_team': current_team,
                    'skill_breakdown': skill_breakdown,
                    'experience_breakdown': experience_breakdown,
                    'leadership_interest_count': leadership_interest_count,
                    'current_date': current_time,
                    'leader_dashboard_url': get_leader_dashboard_url(),
                    'test_mode': is_test_server()
                }
                
                # Render email template
                try:
                    if app:
                        with app.app_context():
                            html_content = render_template('emails/weekly_summary.html', **email_context)
                    else:
                        # Fallback to basic text if no app context
                        html_content = None
                except Exception as template_error:
                    logger.error(f"Template rendering error for weekly summary {area_code}: {template_error}")
                    # Fallback to basic text email
                    html_content = None
                subject = EMAIL_SUBJECTS['weekly_summary'].format(area_code=area_code)
                
                # Send email
                if email_service.send_email(leader_emails, subject, '', html_content):
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


def generate_admin_digest_email(app=None) -> Dict[str, Any]:
    """Generate daily admin digest with unassigned participants."""
    try:
        db, _ = get_firestore_client()
        current_year = datetime.now().year
        current_time = datetime.utcnow()
        
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
        
        # Ensure current_time is timezone-aware (UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        for participant in unassigned_participants:
            created_at = participant.get('created_at')
            if created_at:
                # Ensure created_at is timezone-aware for comparison
                if created_at.tzinfo is None:
                    # If naive, assume UTC
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                days_wait = (current_time - created_at).days
                days_waiting.append(days_wait)
                total_wait_days += days_wait
            else:
                days_waiting.append(0)
        
        average_wait_days = round(total_wait_days / len(unassigned_participants)) if unassigned_participants else 0
        
        # Prepare email context
        email_context = {
            'unassigned_participants': unassigned_participants,
            'leadership_interest_count': leadership_interest_count,
            'days_waiting': days_waiting,
            'average_wait_days': average_wait_days,
            'current_date': current_time,
            'admin_unassigned_url': get_admin_unassigned_url(),
            'test_mode': is_test_server()
        }
        
        # Render email template
        try:
            if app:
                with app.app_context():
                    html_content = render_template('emails/admin_digest.html', **email_context)
            else:
                # Fallback to basic text if no app context
                html_content = None
        except Exception as template_error:
            logger.error(f"Template rendering error for admin digest: {template_error}")
            # Fallback to basic text email
            html_content = None
        subject = EMAIL_SUBJECTS['admin_digest']
        
        # Send email to all admins
        if email_service.send_email(ADMIN_EMAILS, subject, '', html_content):
            results['emails_sent'] = 1
            logger.info(f"Admin digest email sent to {len(ADMIN_EMAILS)} admins for {len(unassigned_participants)} unassigned participants")
        else:
            results['errors'].append("Failed to send admin digest email")
        
        logger.info(f"Admin digest email completed: {results['unassigned_count']} unassigned participants")
        return results
        
    except Exception as e:
        logger.error(f"Critical error in generate_admin_digest_email: {e}")
        return {'emails_sent': 0, 'unassigned_count': 0, 'errors': [str(e)]}


if __name__ == '__main__':
    # Command line testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CBC emails')
    parser.add_argument('--type', choices=['team_update', 'weekly_summary', 'admin_digest'], 
                       help='Email type to generate')
    parser.add_argument('--test', action='store_true', help='Enable test mode')
    
    args = parser.parse_args()
    
    if args.test:
        os.environ['TEST_MODE'] = 'true'
    
    logging.basicConfig(level=logging.INFO)
    
    if args.type == 'team_update':
        results = generate_team_update_emails()
    elif args.type == 'weekly_summary':
        results = generate_weekly_summary_emails()
    elif args.type == 'admin_digest':
        results = generate_admin_digest_email()
    else:
        print("Please specify --type (team_update, weekly_summary, or admin_digest)")
        sys.exit(1)
    
    print(f"Results: {results}")