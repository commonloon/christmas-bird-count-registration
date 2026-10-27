# Updated by Claude AI on 2026-10-27
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session
from config.database import get_db_session
from models.participant import ParticipantModel
from routes.auth import require_leader, get_current_user
from config.areas import get_area_info
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS
from datetime import datetime
from test.email_generator import build_weekly_summary_leader_preview
import logging

leader_bp = Blueprint('leader', __name__)
logger = logging.getLogger(__name__)


@leader_bp.before_request
def load_db():
    """Load database session for leader routes and re-validate role."""
    g.db = get_db_session()

    # Re-validate leader status on each request to leader routes
    # This ensures role changes are reflected immediately without re-login
    if 'user_email' in session:
        from routes.auth import get_user_role
        user_email = session['user_email']
        current_role = session.get('user_role')
        actual_role = get_user_role(user_email, g.db, g.circle_slug)

        # Update session if role has changed
        if actual_role != current_role:
            session['user_role'] = actual_role
            logger.info(f"Updated role for {user_email}: {current_role} -> {actual_role}")


def get_current_user_email():
    """Get current user's email from session."""
    from flask import session
    return session.get('user_email')


def _view_as_options(participant_model):
    """Dropdown entries for the admin "view as" selector: one per distinct leader
    email (the dashboard is keyed by email), labelled with names and areas."""
    by_email = {}
    for leader in participant_model.get_leaders():
        area = leader.get('assigned_area_leader')
        email = (leader.get('email') or '').lower()
        if not area or not email:
            continue
        entry = by_email.setdefault(email, {'names': [], 'areas': set()})
        name = f"{leader.get('first_name', '')} {leader.get('last_name', '')}".strip()
        if name not in entry['names']:
            entry['names'].append(name)
        entry['areas'].add(area)
    options = [
        {'email': email,
         'label': f"{' / '.join(e['names'])} - {', '.join(sorted(e['areas']))}",
         'sort': (sorted(e['areas'])[0], e['names'][0].lower())}
        for email, e in by_email.items()
    ]
    options.sort(key=lambda o: o['sort'])
    return options


@leader_bp.route('/')
@leader_bp.route('')
@require_leader
@limiter.limit(RATE_LIMITS['admin_general'])
def dashboard():
    """Leader dashboard showing their team roster with historical year support.

    A person can lead more than one area in the same year by registering under
    a separate participant record per area (same email, a distinguishing name -
    there is no other way to represent "one person, two areas" in a schema
    where one participant row has exactly one assigned_area_leader). This route
    surfaces all of that email's current-year leader records as area tabs
    rather than arbitrarily picking one."""
    user_email = get_current_user_email()
    if not user_email:
        flash('Authentication error. Please log in again.', 'error')
        return redirect(url_for('auth.login'))

    # Admin-only read-only "view as": render this page exactly as the named leader
    # sees it. Only this GET honours the override - the session is never changed,
    # so the admin can't act as the leader. Non-admins' ?as= is ignored.
    is_admin_viewer = session.get('user_role') in ('admin', 'super_admin')
    view_as_email = request.args.get('as', '').strip().lower() if is_admin_viewer else ''
    if view_as_email:
        logger.info(f"Leader dashboard view-as: {user_email} viewing as {view_as_email} "
                    f"(circle {g.circle_slug})")
        user_email = view_as_email

    # Get current year
    current_year = datetime.now().year

    # Get selected year from query params, default to current year
    selected_year = int(request.args.get('year', current_year))

    # Get leader info from current year to determine area assignment(s).
    # Which areas someone leads is always determined from the current year,
    # even when browsing a historical year's roster for one of those areas.
    current_participant_model = ParticipantModel(g.db, current_year)
    leader_records = current_participant_model.get_participants_by_email(user_email)
    leader_records = [r for r in leader_records if r.get('is_leader', False)]

    view_as_options = _view_as_options(current_participant_model) if is_admin_viewer else []

    if not leader_records:
        if view_as_email:
            flash('No area leader found for that email in this circle.', 'error')
            return redirect(url_for('leader.dashboard'))
        if is_admin_viewer:
            return render_template('leader/view_as_picker.html',
                                   view_as_options=view_as_options,
                                   selected_year=selected_year,
                                   current_user=get_current_user())
        flash('You are not assigned as an area leader.', 'error')
        return redirect(url_for('main.index'))

    # One leader record per led area (a record with no area is unusable), de-duplicated
    # and ordered alphabetically by area code for a stable, predictable tab order.
    records_by_area = {}
    for record in leader_records:
        area_code = record.get('assigned_area_leader')
        if area_code and area_code not in records_by_area:
            records_by_area[area_code] = record

    if not records_by_area:
        flash('No area assignment found for your leadership role.', 'error')
        return redirect(url_for('main.index'))

    led_areas = [
        {'code': code, 'name': get_area_info(code).get('name', code)}
        for code in sorted(records_by_area.keys())
    ]

    # Selected area from query params, defaulting to (and falling back to, if the
    # query param names an area this email doesn't lead) the first led area.
    requested_area = request.args.get('area')
    assigned_area = requested_area if requested_area in records_by_area else led_areas[0]['code']

    leader_info = records_by_area[assigned_area]

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

    # Admin "view as" only: read-only preview of the weekly summary email this
    # area's leaders get. Never sends or touches the schedule's last-sent timestamp.
    email_preview = None
    email_preview_error = False
    if view_as_email and not is_historical:
        try:
            email_preview = build_weekly_summary_leader_preview(g.circle_slug, assigned_area)
        except Exception:
            logger.exception(f"Weekly summary preview failed for area {assigned_area} "
                             f"(circle {g.circle_slug})")
            email_preview_error = True

    return render_template('leader/dashboard.html',
                           selected_year=selected_year,
                           current_year=current_year,
                           available_years=display_years,
                           is_historical=is_historical,
                           leader_info=leader_info,
                           area_code=assigned_area,
                           area_info=area_info,
                           led_areas=led_areas,
                           feeder_participants=feeder_participants,
                           regular_participants=regular_participants,
                           withdrawn_participants=withdrawn_participants,
                           total_participants=len(active_participants),
                           view_as_email=view_as_email,
                           email_preview=email_preview,
                           email_preview_error=email_preview_error,
                           view_as_args={'as': view_as_email} if view_as_email else {},
                           view_as_options=view_as_options,
                           current_user=get_current_user())