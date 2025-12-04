# Updated by Claude AI on 2025-10-03
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session
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
    """Leader dashboard showing their team roster with historical year support."""
    if not g.db:
        return render_template('leader/dashboard.html', error="Database unavailable")

    user_email = get_current_user_email()
    if not user_email:
        flash('Authentication error. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    # Get current year
    current_year = datetime.now().year

    # Get selected year from query params, default to current year
    selected_year = int(request.args.get('year', current_year))

    # Get leader info from current year to determine area assignment
    current_participant_model = ParticipantModel(g.db, current_year)
    leader_records = current_participant_model.get_participants_by_email(user_email)
    leader_records = [r for r in leader_records if r.get('is_leader', False)]

    if not leader_records:
        flash('You are not assigned as an area leader.', 'error')
        return redirect(url_for('main.index'))

    # Get the first leader record (primary) - always from current year
    leader_info = leader_records[0]
    assigned_area = leader_info.get('assigned_area_leader')

    if not assigned_area:
        flash('No area assignment found for your leadership role.', 'error')
        return redirect(url_for('main.index'))

    # Get area information
    area_info = get_area_info(assigned_area)

    # Initialize model for selected year to get participant data
    participant_model = ParticipantModel(g.db, selected_year)

    # Get active and withdrawn participants for this area in the selected year
    active_participants = participant_model.get_participants_by_area(assigned_area)
    withdrawn_participants = participant_model.get_withdrawn_participants_by_area(assigned_area)

    # Separate active FEEDER and regular participants
    feeder_participants = [p for p in active_participants if p.get('participation_type') == 'FEEDER']
    regular_participants = [p for p in active_participants if p.get('participation_type') != 'FEEDER']

    # Sort participants by first name
    feeder_participants.sort(key=lambda x: x.get('first_name', '').lower())
    regular_participants.sort(key=lambda x: x.get('first_name', '').lower())
    withdrawn_participants.sort(key=lambda x: x.get('first_name', '').lower())

    # Combine all participants for total count
    all_participants = active_participants + withdrawn_participants

    # Get available years for tab navigation
    available_years = ParticipantModel.get_available_years(g.db)

    # Filter to current year + past 3 years with data
    historical_years = [y for y in available_years if y < current_year][-3:]
    display_years = [current_year] + historical_years if current_year in available_years else historical_years[:4]

    # Determine if selected year is historical (read-only)
    is_historical = selected_year < current_year

    return render_template('leader/dashboard.html',
                           selected_year=selected_year,
                           current_year=current_year,
                           available_years=display_years,
                           is_historical=is_historical,
                           leader_info=leader_info,
                           area_code=assigned_area,
                           area_info=area_info,
                           feeder_participants=feeder_participants,
                           regular_participants=regular_participants,
                           withdrawn_participants=withdrawn_participants,
                           total_participants=len(active_participants),
                           current_user=get_current_user())