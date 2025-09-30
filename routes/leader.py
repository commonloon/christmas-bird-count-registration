# Updated by Claude AI on 2025-09-29
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session
from google.cloud import firestore
from config.database import get_firestore_client
from models.participant import ParticipantModel
from routes.auth import require_leader, get_current_user
from config.areas import get_area_info
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS
from datetime import datetime
import logging

leader_bp = Blueprint('leader', __name__)
logger = logging.getLogger(__name__)


@leader_bp.before_request
def load_db():
    """Load database client for leader routes and re-validate role."""
    try:
        g.db, _ = get_firestore_client()

        # Re-validate leader status on each request to leader routes
        # This ensures role changes are reflected immediately without re-login
        if 'user_email' in session:
            from routes.auth import get_user_role
            user_email = session['user_email']
            current_role = session.get('user_role')
            actual_role = get_user_role(user_email, g.db)

            # Update session if role has changed
            if actual_role != current_role:
                session['user_role'] = actual_role
                logger.info(f"Updated role for {user_email}: {current_role} -> {actual_role}")
    except Exception as e:
        g.db = None
        flash('Database unavailable.', 'error')


def get_current_user_email():
    """Get current user's email from session."""
    from flask import session
    return session.get('user_email')


@leader_bp.route('/')
@leader_bp.route('')
@require_leader
@limiter.limit(RATE_LIMITS['admin_general'])
def dashboard():
    """Leader dashboard showing their team roster."""
    if not g.db:
        return render_template('leader/dashboard.html', error="Database unavailable")

    user_email = get_current_user_email()
    if not user_email:
        flash('Authentication error. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    # Get selected year from query params, default to current year
    selected_year = int(request.args.get('year', datetime.now().year))

    # Initialize model for selected year
    participant_model = ParticipantModel(g.db, selected_year)

    # Get leader's own participant record(s) - there may be multiple family members
    leader_records = participant_model.get_participants_by_email(user_email)

    # Filter to only those with is_leader=True
    leader_records = [r for r in leader_records if r.get('is_leader', False)]

    if not leader_records:
        flash('You are not assigned as an area leader.', 'error')
        return redirect(url_for('main.index'))

    # Get the first leader record (primary)
    leader_info = leader_records[0]
    assigned_area = leader_info.get('assigned_area_leader')

    if not assigned_area:
        flash('No area assignment found for your leadership role.', 'error')
        return redirect(url_for('main.index'))

    # Get area information
    area_info = get_area_info(assigned_area)

    # Get all participants for this area
    all_participants = participant_model.get_participants_by_area(assigned_area)

    # Separate FEEDER and regular participants
    feeder_participants = [p for p in all_participants if p.get('participation_type') == 'FEEDER']
    regular_participants = [p for p in all_participants if p.get('participation_type') != 'FEEDER']

    # Sort participants by first name
    feeder_participants.sort(key=lambda x: x.get('first_name', '').lower())
    regular_participants.sort(key=lambda x: x.get('first_name', '').lower())

    # Get available years (for future historical data feature)
    available_years = ParticipantModel.get_available_years(g.db)

    return render_template('leader/dashboard.html',
                           selected_year=selected_year,
                           available_years=available_years,
                           leader_info=leader_info,
                           area_code=assigned_area,
                           area_info=area_info,
                           feeder_participants=feeder_participants,
                           regular_participants=regular_participants,
                           total_participants=len(all_participants),
                           current_user=get_current_user())