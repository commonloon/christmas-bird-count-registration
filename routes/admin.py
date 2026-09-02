# Updated by Claude AI on 2025-12-18
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, g, current_app, session
from config.database import get_db_session
from config.email_settings import is_test_server
from models.participant import ParticipantModel
from models.removal_log import RemovalLogModel
from models.withdrawal_log import WithdrawalLogModel
from models.area_signup_type import AreaSignupTypeModel
from config.areas import get_area_info, get_all_areas
from config.organization import get_registration_status
from models.reassignment_log import ReassignmentLogModel
from config.fields import (
    normalize_participant_record, get_participant_csv_fields,
    get_participant_field_default, get_participant_display_name
)
from config.admins import get_admin_emails
from routes.auth import require_admin, require_super_admin, get_current_user
from models.circle import CircleModel, CircleAreaModel, CircleAdminModel
from services.kml_import import parse_kml_string, filter_main_areas, calculate_map_center_and_bounds, KmlParseError
from services.email_service import email_service
from services.ip_blocker import IPBlockerService
from test.email_generator import (
    generate_team_update_emails,
    generate_weekly_summary_emails,
    generate_admin_digest_email
)
from services.security import (
    sanitize_name, sanitize_email, sanitize_phone, sanitize_notes, sanitize_text_input,
    validate_area_code, validate_experience, validate_email_format, is_suspicious_input, log_security_event
)
from services.csv_security import escape_csv_formula
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS, get_rate_limit_message
from datetime import datetime, timezone
import csv
import logging
import os
from io import StringIO

admin_bp = Blueprint('admin', __name__)


# Endpoints that make sense with no circle context (they take an explicit
# slug, or manage the cross-circle circle list itself) - everything else in
# this blueprint implicitly acts on g.circle_slug, which is meaningless on
# the landing host (see app.py's LANDING_HOST branch).
_CIRCLE_CONSOLE_ENDPOINTS = {
    'admin.list_circles', 'admin.new_circle', 'admin.edit_circle',
    'admin.circle_admins', 'admin.circle_areas_manage',
}


@admin_bp.before_request
def load_db():
    """Load database session and check admin access."""
    g.db = get_db_session()

    if getattr(g, 'is_landing_host', False) and request.endpoint not in _CIRCLE_CONSOLE_ENDPOINTS:
        # No circle context here - every other /bigbird/* route would otherwise
        # silently act on Vancouver's data via the DEFAULT_CIRCLE_SLUG fallback,
        # which is correct for local dev but wrong here. The circles console's
        # own require_super_admin/require_admin decorators still gate access
        # after this redirect - this only redirects, it doesn't authorize.
        return redirect(url_for('admin.list_circles'))


@admin_bp.route('/')
@require_admin
@limiter.limit(RATE_LIMITS['admin_general'])
def dashboard():
    """Admin dashboard with year selector and overview."""
    if not g.db:
        return render_template('admin/dashboard.html', error="Database unavailable")

    # Get selected year from query params, default to current year
    selected_year = int(request.args.get('year', datetime.now().year))

    # Initialize models for selected year
    participant_model = ParticipantModel(g.db, selected_year)
    removal_model = RemovalLogModel(g.db, selected_year)

    # Get available years
    available_years = ParticipantModel.get_available_years(g.db)

    # Get dashboard data
    participants = participant_model.get_all_participants()
    unassigned_participants = participant_model.get_unassigned_participants()
    area_counts = participant_model.get_area_counts()
    areas_without_leaders = participant_model.get_areas_without_leaders()
    leadership_interested = participant_model.get_participants_interested_in_leadership()
    recent_removals = removal_model.get_recent_removals(7)

    # Calculate statistics
    total_participants = len(participants)
    total_unassigned = len(unassigned_participants)
    total_assigned = total_participants - total_unassigned

    # Get registration status
    reg_status = get_registration_status()

    return render_template('admin/dashboard.html',
                           selected_year=selected_year,
                           available_years=available_years,
                           participants=participants[:10],  # Recent 10 for dashboard
                           unassigned_participants=unassigned_participants,
                           area_counts=area_counts,
                           areas_without_leaders=areas_without_leaders,
                           leadership_interested=leadership_interested,
                           recent_removals=recent_removals,
                           total_participants=total_participants,
                           total_unassigned=total_unassigned,
                           total_assigned=total_assigned,
                           is_test_server=is_test_server(),
                           current_user=get_current_user(),
                           registration_status=reg_status)


@admin_bp.route('/recent-registrations')
@require_admin
@limiter.limit(RATE_LIMITS['admin_general'])
def recent_registrations():
    """View and filter recent registrations with email copy capability."""
    # Updated by Claude AI on 2025-12-12
    from datetime import timedelta, timezone

    if not g.db:
        return render_template('admin/recent_registrations.html', error="Database unavailable")

    # Get year selection
    selected_year = request.args.get('year', datetime.now().year, type=int)

    # Get filter parameters
    days = request.args.get('days', type=int)
    custom_date = request.args.get('date')

    # Validate and process filters
    cutoff_date = None
    filter_days = 7  # Default
    filter_date = None

    if custom_date:
        try:
            # Parse date and make it timezone-aware (UTC) to match Firestore timestamps
            cutoff_date = datetime.strptime(custom_date, '%Y-%m-%d')
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
            # Reject future dates
            now_utc = datetime.now(timezone.utc)
            if cutoff_date > now_utc:
                flash('Cannot filter by future dates.', 'error')
                cutoff_date = None
            else:
                filter_date = custom_date
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')

    if cutoff_date is None:
        # Use days parameter (default to 7 if not specified)
        if days and 1 <= days <= 90:
            filter_days = days
        else:
            if days:
                flash('Days must be between 1 and 90.', 'error')
            filter_days = 7

        # Calculate cutoff date from days (timezone-aware UTC)
        cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date - timedelta(days=filter_days)

    # Get all participants and filter in Python
    participant_model = ParticipantModel(g.db, selected_year)
    all_participants = participant_model.get_all_participants()

    # Filter by date in Python (avoids compound index requirement)
    filtered_participants = []
    for p in all_participants:
        if p.get('created_at') and p['created_at'] >= cutoff_date:
            filtered_participants.append(normalize_participant_record(p))

    # Get available years
    available_years = ParticipantModel.get_available_years(g.db)

    return render_template('admin/recent_registrations.html',
                         selected_year=selected_year,
                         available_years=available_years,
                         participants=filtered_participants,
                         filter_days=filter_days,
                         filter_date=filter_date,
                         total_count=len(filtered_participants),
                         today=datetime.now().strftime('%Y-%m-%d'),
                         current_user=get_current_user())


@admin_bp.route('/participants')
@require_admin
def participants():
    """View and manage all participants with historical year support."""
    if not g.db:
        return render_template('admin/participants.html',
                             participants=[],
                             area_leaders={},
                             error="Database unavailable")

    # Get current year
    current_year = datetime.now().year

    # Get selected year from query params, default to current year
    selected_year = int(request.args.get('year', current_year))

    # Initialize model for selected year
    participant_model = ParticipantModel(g.db, selected_year)

    # Get available years for tab navigation
    available_years = ParticipantModel.get_available_years(g.db)

    # Filter to current year + past 3 years with data
    historical_years = [y for y in available_years if y < current_year][-3:]
    display_years = [current_year] + historical_years if current_year in available_years else historical_years[:4]

    # Determine if selected year is historical (read-only)
    is_historical = selected_year < current_year

    all_participants = participant_model.get_all_participants()
    all_leaders = participant_model.get_leaders()

    # Filter out UNASSIGNED participants - they have their own dedicated interface at /bigbird/unassigned
    assigned_participants = [p for p in all_participants if p.get('preferred_area') != 'UNASSIGNED']

    # Normalize participant data to ensure all fields are present
    normalized_participants = [normalize_participant_record(p) for p in assigned_participants]

    # Convert manually added leaders to participant-like records for display
    leader_as_participants = []
    for leader in all_leaders:
        # Check if leader already exists as participant (avoid duplication by identity)
        leader_first_name = leader.get('first_name', '').strip()
        leader_last_name = leader.get('last_name', '').strip()
        email = leader.get('email', '').lower().strip()

        existing = next((p for p in normalized_participants
                        if (p.get('first_name', '').strip().lower() == leader_first_name.lower() and
                            p.get('last_name', '').strip().lower() == leader_last_name.lower() and
                            p.get('email', '').lower().strip() == email)), None)

        if not existing and email:  # Only add if not already a participant and has email
            leader_participant = {
                'id': leader.get('id'),
                'first_name': leader.get('first_name', ''),
                'last_name': leader.get('last_name', ''),
                'email': leader.get('email', ''),
                'phone': leader.get('phone', ''),
                'phone2': '',  # Leaders don't have secondary phone
                'preferred_area': leader.get('assigned_area_leader', ''),
                'skill_level': 'Area Leader',  # Special designation for leaders
                'experience': 'Area Leader',
                'participation_type': 'regular',
                'has_binoculars': False,
                'spotting_scope': False,
                'interested_in_leadership': True,  # Assumed for leaders
                'interested_in_scribe': False,
                'notes_to_organizers': leader.get('notes', ''),
                'is_leader': True,
                'assigned_area_leader': None,
                'auto_assigned': False,
                'assigned_by': leader.get('assigned_by', ''),
                'assigned_at': leader.get('assigned_at'),
                'created_at': leader.get('assigned_at'),  # Use assignment time as creation time
                'updated_at': None,
                'year': leader.get('year', selected_year)
            }
            # Normalize the leader record to ensure all fields are present
            leader_as_participants.append(normalize_participant_record(leader_participant))

    # Combine participants and leader-participants
    combined_participants = normalized_participants + leader_as_participants

    # Create area leader lookup
    area_leaders = {}
    for leader in all_leaders:
        area = leader.get('assigned_area_leader')
        if area:
            if area not in area_leaders:
                area_leaders[area] = []
            area_leaders[area].append(leader)

    # Define which fields to display in the table (subset of all fields for readability)
    display_fields = ['first_name', 'last_name', 'email', 'phone', 'phone2', 'skill_level',
                     'experience', 'participation_type', 'has_binoculars', 'spotting_scope',
                     'interested_in_leadership', 'interested_in_scribe', 'notes_to_organizers', 'created_at']

    return render_template('admin/participants.html',
                           participants=combined_participants,
                           area_leaders=area_leaders,
                           display_fields=display_fields,
                           get_display_name=get_participant_display_name,
                           selected_year=selected_year,
                           current_year=current_year,
                           available_years=display_years,
                           is_historical=is_historical,
                           all_areas=get_all_areas(),
                           current_user=get_current_user())


@admin_bp.route('/unassigned')
@require_admin
def unassigned():
    """Manage unassigned participants."""
    if not g.db:
        return render_template('admin/unassigned.html', participants=[], error="Database unavailable")

    selected_year = int(request.args.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)

    unassigned_participants = participant_model.get_unassigned_participants()
    all_areas = get_all_areas()
    area_counts = participant_model.get_area_counts()

    return render_template('admin/unassigned.html',
                           participants=unassigned_participants,
                           all_areas=all_areas,
                           area_counts=area_counts,
                           selected_year=selected_year,
                           current_user=get_current_user())


@admin_bp.route('/assign_participant', methods=['POST'])
@require_admin
@limiter.limit(RATE_LIMITS['admin_modify'], error_message=get_rate_limit_message('admin_modify'))
def assign_participant():
    """Assign a participant to an area."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.unassigned'))

    # Get and sanitize form data
    participant_id = request.form.get('participant_id', '').strip()
    area_code = request.form.get('area_code', '').strip().upper()
    selected_year = int(request.form.get('year', datetime.now().year))
    
    # Security checks
    user = get_current_user()
    if is_suspicious_input(participant_id) or is_suspicious_input(area_code):
        log_security_event('Suspicious admin input', f'Assign participant attempt with suspicious data', user.get('email'))
        flash('Invalid input detected.', 'error')
        return redirect(url_for('admin.unassigned', year=selected_year))

    if not participant_id or not area_code:
        flash('Participant ID and area code are required.', 'error')
        return redirect(url_for('admin.unassigned', year=selected_year))
        
    if not validate_area_code(area_code):
        flash('Invalid area code.', 'error')
        return redirect(url_for('admin.unassigned', year=selected_year))

    participant_model = ParticipantModel(g.db, selected_year)

    if participant_model.assign_participant_to_area(participant_id, area_code, user['email']):
        flash(f'Participant assigned to Area {area_code} successfully.', 'success')
    else:
        flash('Failed to assign participant.', 'error')

    return redirect(url_for('admin.unassigned', year=selected_year))


@admin_bp.route('/area/<area_code>')
@require_admin
def area_detail(area_code):
    """View participants for a specific area."""
    if not g.db:
        return render_template('admin/area_detail.html', error="Database unavailable")

    selected_year = int(request.args.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    available_years = ParticipantModel.get_available_years(g.db)

    participants = participant_model.get_participants_by_area(area_code)
    area_leaders = participant_model.get_leaders_by_area(area_code)
    area_info = get_area_info(area_code)

    # Get historical participants if requested
    show_historical = request.args.get('historical') == 'true'
    historical_participants = []
    if show_historical:
        historical_participants = participant_model.get_historical_participants(area_code, 3)

    return render_template('admin/area_detail.html',
                           area_code=area_code,
                           participants=participants,
                           area_leaders=area_leaders,
                           area_info=area_info,
                           historical_participants=historical_participants,
                           show_historical=show_historical,
                           selected_year=selected_year,
                           available_years=available_years,
                           current_user=get_current_user())


@admin_bp.route('/leaders')
@require_admin
@limiter.limit(RATE_LIMITS['admin_general'])
def leaders():
    """Manage area leaders with CSV export support."""
    if not g.db:
        return render_template('admin/leaders.html', error="Database unavailable")

    selected_year = int(request.args.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    available_years = ParticipantModel.get_available_years(g.db)

    all_leaders = participant_model.get_leaders()
    areas_without_leaders = participant_model.get_areas_without_leaders()
    leadership_interested = participant_model.get_participants_interested_in_leadership()
    all_areas = get_all_areas()

    # Normalize leader data to ensure all fields are present (single-table design uses participant fields)
    normalized_leaders = [normalize_participant_record(leader) for leader in all_leaders]

    # Sort current leaders by area code then by first name
    normalized_leaders.sort(key=lambda x: (x.get('assigned_area_leader', ''), x.get('first_name', '')))

    # Sort potential leaders by area preference then by first name
    leadership_interested.sort(key=lambda x: (x.get('preferred_area', ''), x.get('first_name', '')))

    # Check if CSV export is requested
    if request.args.get('format') == 'csv':
        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        if normalized_leaders:
            # Use participant field definitions for complete leader data
            fieldnames = get_participant_csv_fields()

            # Write CSV header
            writer.writerow(fieldnames)

            # Sort leaders by area, then by first name
            sorted_leaders = sorted(normalized_leaders, key=lambda x: (x.get('assigned_area_leader', ''), x.get('first_name', '')))

            # Write leader data
            for leader in sorted_leaders:
                row = []
                for field in fieldnames:
                    value = leader.get(field, get_participant_field_default(field))
                    # Handle datetime objects
                    if hasattr(value, 'strftime'):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    # Handle boolean values
                    elif isinstance(value, bool):
                        value = 'Yes' if value else 'No'
                    # Apply CSV formula injection protection (defense in depth)
                    row.append(escape_csv_formula(value))
                writer.writerow(row)

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=area_leaders_{selected_year}_{datetime.now().strftime("%Y%m%d")}.csv'
        response.headers['Content-type'] = 'text/csv'

        return response

    current_year = datetime.now().year
    is_historical = selected_year < current_year

    return render_template('admin/leaders.html',
                           all_leaders=normalized_leaders,
                           areas_without_leaders=areas_without_leaders,
                           leadership_interested=leadership_interested,
                           all_areas=all_areas,
                           get_area_info=get_area_info,
                           selected_year=selected_year,
                           available_years=available_years,
                           current_year=current_year,
                           is_historical=is_historical,
                           current_user=get_current_user())


@admin_bp.route('/add_leader', methods=['POST'])
@require_admin
@limiter.limit(RATE_LIMITS['admin_modify'], error_message=get_rate_limit_message('admin_modify'))
def add_leader():
    """Manually add a new area leader."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.leaders'))

    selected_year = int(request.form.get('year', datetime.now().year))
    
    # Get and sanitize form data
    first_name = sanitize_name(request.form.get('first_name', ''))
    last_name = sanitize_name(request.form.get('last_name', ''))
    email = sanitize_email(request.form.get('email', ''))
    phone = sanitize_phone(request.form.get('phone', ''))
    area_code = request.form.get('area_code', '').strip().upper()
    notes = sanitize_notes(request.form.get('notes', ''))
    
    # Security checks
    user = get_current_user()
    all_text_inputs = [first_name, last_name, phone, notes]
    for text_input in all_text_inputs:
        if is_suspicious_input(text_input):
            log_security_event('Suspicious admin input', f'Add leader attempt with suspicious input', user.get('email'))
            flash('Invalid input detected. Please check your entries.', 'error')
            return redirect(url_for('admin.leaders', year=selected_year))

    # Validate required fields
    if not all([first_name, last_name, email, phone, area_code]):
        flash('All required fields must be completed.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))
        
    # Length validations
    if len(first_name) > 100 or len(last_name) > 100:
        flash('Names must be 100 characters or less.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    if len(email) > 254:
        flash('Email address is too long.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Validate email format
    if not validate_email_format(email):
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    if len(phone) > 20:
        flash('Phone number must be 20 characters or less.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Validate area code
    if not validate_area_code(area_code):
        flash(f'Invalid area code: {area_code}', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Get additional form fields
    phone2 = sanitize_phone(request.form.get('phone2', ''))
    skill_level = request.form.get('skill_level', 'Expert').strip()
    experience = request.form.get('experience', '3+ counts').strip()
    has_binoculars = request.form.get('has_binoculars') == 'on'
    spotting_scope = request.form.get('spotting_scope') == 'on'
    interested_in_scribe = request.form.get('interested_in_scribe') == 'on'

    # Validate skill level
    valid_skill_levels = ['Newbie', 'Beginner', 'Intermediate', 'Expert']
    if skill_level not in valid_skill_levels:
        flash(f'Invalid skill level: {skill_level}', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Initialize participant model
    participant_model = ParticipantModel(g.db, selected_year)

    try:
        # Check if this exact person (identity) is already assigned to this area
        existing_leaders_for_person = participant_model.get_leaders_by_identity(first_name, last_name, email)
        for leader in existing_leaders_for_person:
            if leader.get('assigned_area_leader') == area_code:
                flash(f'{first_name} {last_name} is already assigned as a leader for Area {area_code}.', 'warning')
                return redirect(url_for('admin.leaders', year=selected_year))

        # Check if this person (identity) is already leading another area (one area per person rule)
        current_leader_areas = participant_model.get_leaders_by_identity(first_name, last_name, email)
        if current_leader_areas:
            existing_area = current_leader_areas[0]['assigned_area_leader']
            flash(f'{first_name} {last_name} is already leading Area {existing_area}. Each person can only lead one area.', 'error')
            return redirect(url_for('admin.leaders', year=selected_year))

        # Create the area leader record with full participant data
        leader_data = {
            'area_code': area_code,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'phone2': phone2,
            'skill_level': skill_level,
            'experience': experience,
            'has_binoculars': has_binoculars,
            'spotting_scope': spotting_scope,
            'interested_in_scribe': interested_in_scribe,
            'assigned_by': user['email'],
            'assigned_at': datetime.now(),
            'active': True,
            'year': selected_year,
            'created_from_participant': False,
            'notes': notes if notes else None
        }

        leader_id = participant_model.add_leader(leader_data)
        
        if leader_id:
            flash(f'Successfully added {first_name} {last_name} as leader for Area {area_code}.', 'success')
        else:
            flash('Failed to add leader. Please try again.', 'error')

    except Exception as e:
        logging.error(f"Error adding leader: {e}")
        flash('An error occurred while adding the leader.', 'error')

    return redirect(url_for('admin.leaders', year=selected_year))


@admin_bp.route('/assign_leader', methods=['POST'])
@require_admin
def assign_leader():
    """Assign a participant as area leader."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.leaders'))

    participant_id = request.form.get('participant_id')
    area_code = request.form.get('area_code', '').strip().upper()
    selected_year = int(request.form.get('year', datetime.now().year))

    # Validate required fields
    if not participant_id or not area_code:
        flash('Participant ID and area code are required.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Validate area code
    if not get_area_info(area_code):
        flash(f'Invalid area code: {area_code}', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    participant_model = ParticipantModel(g.db, selected_year)
    user = get_current_user()

    # Get participant details
    participant = participant_model.get_participant(participant_id)
    if not participant:
        flash('Participant not found.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    try:
        # Check if this person (identity) is already leading the SAME area
        first_name = participant['first_name']
        last_name = participant['last_name']
        participant_email = participant['email']
        leader_areas = participant_model.get_leaders_by_identity(first_name, last_name, participant_email)
        for leader in leader_areas:
            if leader.get('assigned_area_leader') == area_code:
                flash(f'{first_name} {last_name} is already assigned as leader for Area {area_code}.', 'warning')
                return redirect(url_for('admin.leaders', year=selected_year))

        # Update participant record with leadership
        # This will update their area to the new area and give them leadership
        # If they were leading another area, this automatically changes it (one area per person)
        participant_model.assign_area_leadership(participant_id, area_code, user['email'])

        flash(f"Assigned {participant['first_name']} {participant['last_name']} as leader for Area {area_code}.",
              'success')

    except Exception as e:
        logging.error(f"Error assigning leader: {e}")
        flash('An error occurred while assigning the leader.', 'error')

    return redirect(url_for('admin.leaders', year=selected_year))


@admin_bp.route('/delete_participant/<participant_id>', methods=['POST'])
@require_admin
def delete_participant(participant_id):
    """Delete a participant and log the removal."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.participants'))

    selected_year = int(request.form.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    removal_model = RemovalLogModel(g.db, selected_year)
    user = get_current_user()

    # Get participant info before deletion
    participant = participant_model.get_participant(participant_id)
    if not participant:
        flash('Participant not found.', 'error')
        return redirect(url_for('admin.participants', year=selected_year))

    participant_name = f"{participant['first_name']} {participant['last_name']}"
    area_code = participant.get('preferred_area', 'UNASSIGNED')
    reason = request.form.get('reason', 'Removed by administrator')

    # Check if participant is also a leader (needs synchronization)
    is_leader = participant.get('is_leader', False)

    # Delete participant
    if participant_model.delete_participant(participant_id):
        # Log the removal
        removal_model.log_removal(
            participant_name=participant_name,
            area_code=area_code,
            removed_by=user['email'],
            reason=reason,
            participant_email=participant.get('email', '')
        )

        # If participant was also a leader, deactivate corresponding leader records
        if is_leader:
            first_name = participant.get('first_name', '')
            last_name = participant.get('last_name', '')
            email = participant.get('email', '')

            if first_name and last_name and email:
                if participant_model.deactivate_leaders_by_identity(first_name, last_name, email, user['email']):
                    flash(f'Participant {participant_name} and corresponding leader records removed successfully.', 'success')
                else:
                    flash(f'Participant {participant_name} removed, but failed to deactivate leader records. Please check leader management.', 'warning')
            else:
                flash(f'Participant {participant_name} removed, but leader cleanup skipped due to missing identity information.', 'warning')
        else:
            flash(f'Participant {participant_name} removed successfully.', 'success')
    else:
        flash('Failed to remove participant.', 'error')

    return redirect(url_for('admin.participants', year=selected_year))


@admin_bp.route('/withdraw_participant/<participant_id>', methods=['POST'])
@require_admin
def withdraw_participant(participant_id):
    """Withdraw a participant from the count and log the withdrawal."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.participants'))

    selected_year = int(request.form.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    withdrawal_log_model = WithdrawalLogModel(g.db, selected_year)
    user = get_current_user()

    # Get participant info before withdrawal
    participant = participant_model.get_participant(participant_id)
    if not participant:
        flash('Participant not found.', 'error')
        return redirect(url_for('admin.participants', year=selected_year))

    participant_name = f"{participant['first_name']} {participant['last_name']}"
    area_code = participant.get('preferred_area', 'UNASSIGNED')
    withdrawal_reason = request.form.get('reason', 'Withdrawn by administrator')

    # Withdraw participant
    if participant_model.withdraw_participant(participant_id):
        # Log the withdrawal
        if withdrawal_log_model.log_withdrawal(
            participant_id=participant_id,
            first_name=participant.get('first_name', ''),
            last_name=participant.get('last_name', ''),
            email=participant.get('email', ''),
            area_code=area_code,
            withdrawal_reason=withdrawal_reason,
            recorded_by=user['email']
        ):
            # Send withdrawal confirmation email to participant
            try:
                from services.email_service import email_service
                email_service.send_withdrawal_confirmation(
                    participant_email=participant.get('email', ''),
                    first_name=participant.get('first_name', ''),
                    last_name=participant.get('last_name', ''),
                    withdrawal_reason=withdrawal_reason
                )
            except Exception as e:
                logger.error(f"Failed to send withdrawal confirmation email: {e}")

            flash(f'Participant {participant_name} has been withdrawn.', 'success')
        else:
            flash(f'Participant {participant_name} withdrawn but failed to log withdrawal. Please review.', 'warning')
    else:
        flash('Failed to withdraw participant.', 'error')

    return redirect(url_for('admin.participants', year=selected_year))


@admin_bp.route('/reactivate_participant/<participant_id>', methods=['POST'])
@require_admin
def reactivate_participant(participant_id):
    """Reactivate a withdrawn participant."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.participants'))

    selected_year = int(request.form.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    withdrawal_log_model = WithdrawalLogModel(g.db, selected_year)
    user = get_current_user()

    # Get participant info
    participant = participant_model.get_participant(participant_id)
    if not participant:
        flash('Participant not found.', 'error')
        return redirect(url_for('admin.participants', year=selected_year))

    participant_name = f"{participant['first_name']} {participant['last_name']}"
    area_code = participant.get('preferred_area', 'UNASSIGNED')

    # Check if participant is actually withdrawn
    if participant.get('status') != 'withdrawn':
        flash(f'Participant {participant_name} is not withdrawn.', 'warning')
        return redirect(url_for('admin.participants', year=selected_year))

    # Reactivate participant
    if participant_model.reactivate_participant(participant_id):
        # Log the reactivation
        if withdrawal_log_model.log_reactivation(
            participant_id=participant_id,
            first_name=participant.get('first_name', ''),
            last_name=participant.get('last_name', ''),
            email=participant.get('email', ''),
            area_code=area_code,
            recorded_by=user['email']
        ):
            flash(f'Participant {participant_name} has been reactivated.', 'success')
        else:
            flash(f'Participant {participant_name} reactivated but failed to log reactivation. Please review.', 'warning')
    else:
        flash('Failed to reactivate participant.', 'error')

    return redirect(url_for('admin.participants', year=selected_year))


@admin_bp.route('/export_csv')
@require_admin
@limiter.limit(RATE_LIMITS['admin_general'])
def export_csv():
    """Export all participants as CSV with formula injection protection."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.dashboard'))

    selected_year = int(request.args.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)

    participants = participant_model.get_all_participants()

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Sort participants: alphabetically by area → by participation type (regular/FEEDER) → by first name
    def sort_key(p):
        area = p.get('preferred_area', 'UNASSIGNED')
        participation_type = p.get('participation_type', 'regular')
        first_name = p.get('first_name', '').lower()
        # Sort areas alphabetically, then regular before FEEDER within each area
        type_order = 0 if participation_type == 'regular' else 1
        return (area, type_order, first_name)
    
    sorted_participants = sorted(participants, key=sort_key)

    if sorted_participants:
        # Use centralized field definition to ensure consistent ordering and complete fields
        fieldnames = get_participant_csv_fields()

        # Write CSV header
        writer.writerow(fieldnames)

        # Write participant data
        for p in sorted_participants:
            row = []
            for field in fieldnames:
                value = p.get(field, get_participant_field_default(field))
                # Handle datetime objects
                if hasattr(value, 'strftime'):
                    value = value.strftime('%Y-%m-%d %H:%M')
                # Handle boolean values
                elif isinstance(value, bool):
                    value = 'Yes' if value else 'No'
                # Apply CSV formula injection protection (defense in depth)
                row.append(escape_csv_formula(value))
            writer.writerow(row)

    # Prepare response
    response = make_response(output.getvalue())
    response.headers[
        'Content-Disposition'] = f'attachment; filename=cbc_participants_{selected_year}_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-type'] = 'text/csv'

    return response


@admin_bp.route('/send_unassigned_digest', methods=['POST'])
@require_admin
def send_unassigned_digest():
    """Manually trigger unassigned participant digest email."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.dashboard'))

    selected_year = int(request.form.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)

    unassigned_participants = participant_model.get_unassigned_participants()

    if not unassigned_participants:
        flash('No unassigned participants to report.', 'info')
        return redirect(url_for('admin.dashboard', year=selected_year))

    admin_emails = get_admin_emails()

    if email_service.send_unassigned_digest(admin_emails, unassigned_participants):
        flash(f'Unassigned participant digest sent to {len(admin_emails)} administrators.', 'success')
    else:
        flash('Failed to send digest email.', 'error')

    return redirect(url_for('admin.dashboard', year=selected_year))


@admin_bp.route('/edit_leader', methods=['POST'])
@require_admin
@limiter.limit(RATE_LIMITS['admin_modify'], error_message=get_rate_limit_message('admin_modify'))
def edit_leader():
    """Edit leader information with inline editing."""
    if not g.db:
        return jsonify({'success': False, 'message': 'Database unavailable'})

    try:
        # Parse JSON request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        # Get and sanitize data
        leader_id = data.get('participant_id', '').strip()
        area_code = data.get('area_code', '').strip().upper()
        first_name = sanitize_name(data.get('first_name', ''))
        last_name = sanitize_name(data.get('last_name', ''))
        email = sanitize_email(data.get('email', ''))
        phone = sanitize_phone(data.get('phone', ''))
        phone2 = sanitize_phone(data.get('phone2', ''))
        selected_year = int(data.get('year', datetime.now().year))
        
        # Security checks
        user = get_current_user()
        all_text_inputs = [first_name, last_name, phone, phone2]
        for text_input in all_text_inputs:
            if is_suspicious_input(text_input):
                log_security_event('Suspicious admin input', f'Edit leader attempt with suspicious input', user.get('email'))
                return jsonify({'success': False, 'message': 'Invalid input detected'})

        # Validate required fields
        if not all([leader_id, area_code, first_name, last_name, email]):
            return jsonify({'success': False, 'message': 'All fields are required except phone'})
            
        # Length validations
        if len(first_name) > 100 or len(last_name) > 100:
            return jsonify({'success': False, 'message': 'Names must be 100 characters or less'})
            
        if len(email) > 254:
            return jsonify({'success': False, 'message': 'Email address is too long'})

        # Validate email format
        if not validate_email_format(email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})

        if len(phone) > 20:
            return jsonify({'success': False, 'message': 'Phone number must be 20 characters or less'})

        if len(phone2) > 20:
            return jsonify({'success': False, 'message': 'Secondary phone number must be 20 characters or less'})

        # Validate area code
        if not validate_area_code(area_code):
            return jsonify({'success': False, 'message': f'Invalid area code: {area_code}'})

        # Initialize models
        participant_model = ParticipantModel(g.db, selected_year)

        # Get current leader data
        current_leader = participant_model.get_participant(leader_id)
        if not current_leader:
            return jsonify({'success': False, 'message': 'Leader not found'})

        current_email = current_leader.get('email')
        current_first_name = current_leader.get('first_name')
        current_last_name = current_leader.get('last_name')
        current_area = current_leader.get('assigned_area_leader')

        # Check if identity is changing and if new identity is already leading another area
        identity_changed = (first_name != current_first_name or
                          last_name != current_last_name or
                          email != current_email)

        if identity_changed:
            existing_leaders = participant_model.get_leaders_by_identity(first_name, last_name, email)
            for existing_leader in existing_leaders:
                if existing_leader['id'] != leader_id:  # Don't conflict with self
                    existing_area = existing_leader.get('assigned_area_leader')
                    return jsonify({'success': False, 'message': f'{first_name} {last_name} is already leading Area {existing_area}'})

        # Update participant record
        updates = {
            'assigned_area_leader': area_code,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'phone2': phone2,
            'updated_at': datetime.now(timezone.utc)
        }

        if not participant_model.update_participant(leader_id, updates):
            return jsonify({'success': False, 'message': 'Failed to update leader'})


        return jsonify({'success': True, 'message': 'Leader updated successfully'})

    except Exception as e:
        logging.error(f"Error editing leader: {e}")
        return jsonify({'success': False, 'message': f'Error updating leader: {str(e)}'})


@admin_bp.route('/delete_leader', methods=['POST'])
@require_admin
def delete_leader():
    """Delete (deactivate) a leader."""
    if not g.db:
        return jsonify({'success': False, 'message': 'Database unavailable'})

    try:
        # Parse JSON request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        leader_id = data.get('leader_id')
        selected_year = int(data.get('year', datetime.now().year))

        if not leader_id:
            return jsonify({'success': False, 'message': 'Leader ID is required'})

        # Initialize models
        participant_model = ParticipantModel(g.db, selected_year)
        user = get_current_user()

        # Get leader data before deletion
        leader = participant_model.get_participant(leader_id)
        if not leader:
            return jsonify({'success': False, 'message': 'Leader not found'})

        email = leader.get('email')

        # Remove leader (deactivate)
        if not participant_model.remove_leader(leader_id, user['email']):
            return jsonify({'success': False, 'message': 'Failed to delete leader'})


        return jsonify({'success': True, 'message': 'Leader deleted successfully'})

    except Exception as e:
        logging.error(f"Error deleting leader: {e}")
        return jsonify({'success': False, 'message': f'Error deleting leader: {str(e)}'})


@admin_bp.route('/edit_participant', methods=['POST'])
@require_admin
@limiter.limit(RATE_LIMITS['admin_modify'], error_message=get_rate_limit_message('admin_modify'))
def edit_participant():
    """Edit participant information with inline editing."""
    if not g.db:
        return jsonify({'success': False, 'message': 'Database unavailable'})

    try:
        # Parse JSON request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        # Get and sanitize data
        participant_id = data.get('participant_id', '').strip()
        first_name = sanitize_name(data.get('first_name', ''))
        last_name = sanitize_name(data.get('last_name', ''))
        email = sanitize_email(data.get('email', ''))
        phone = sanitize_phone(data.get('phone', ''))
        phone2 = sanitize_phone(data.get('phone2', ''))
        skill_level = data.get('skill_level', '').strip()
        experience = data.get('experience', '').strip()
        notes_to_organizers = sanitize_notes(data.get('notes_to_organizers', ''))
        has_binoculars = bool(data.get('has_binoculars', False))
        spotting_scope = bool(data.get('spotting_scope', False))
        interested_in_leadership = bool(data.get('interested_in_leadership', False))
        interested_in_scribe = bool(data.get('interested_in_scribe', False))
        preferred_area = data.get('preferred_area', '').strip().upper() if data.get('preferred_area') else None
        selected_year = int(data.get('year', datetime.now().year))

        # Security checks
        user = get_current_user()
        all_text_inputs = [first_name, last_name, phone, phone2, experience, notes_to_organizers]
        for text_input in all_text_inputs:
            if is_suspicious_input(text_input):
                log_security_event('Suspicious admin input', f'Edit participant attempt with suspicious input', user.get('email'))
                return jsonify({'success': False, 'message': 'Invalid input detected'})

        # Validate required fields
        if not all([participant_id, first_name, last_name, email]):
            return jsonify({'success': False, 'message': 'Participant ID, first name, last name, and email are required'})

        # Length validations
        if len(first_name) > 100 or len(last_name) > 100:
            return jsonify({'success': False, 'message': 'Names must be 100 characters or less'})

        if len(email) > 254:
            return jsonify({'success': False, 'message': 'Email address is too long'})

        # Validate email format
        if not validate_email_format(email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})

        if len(phone) > 20:
            return jsonify({'success': False, 'message': 'Phone number must be 20 characters or less'})

        if len(phone2) > 20:
            return jsonify({'success': False, 'message': 'Secondary phone number must be 20 characters or less'})

        # Validate skill level
        valid_skill_levels = ['Newbie', 'Beginner', 'Intermediate', 'Expert']
        if skill_level and skill_level not in valid_skill_levels:
            return jsonify({'success': False, 'message': f'Invalid skill level: {skill_level}'})

        # Validate experience
        if experience and not validate_experience(experience):
            return jsonify({'success': False, 'message': f'Invalid experience level: {experience}'})

        # Validate area code if provided
        if preferred_area and not validate_area_code(preferred_area):
            return jsonify({'success': False, 'message': f'Invalid area code: {preferred_area}'})

        # Initialize models
        participant_model = ParticipantModel(g.db, selected_year)

        # Get current participant data
        current_participant = participant_model.get_participant(participant_id)
        if not current_participant:
            return jsonify({'success': False, 'message': 'Participant not found'})

        # Build updates dictionary with only the fields being edited
        updates = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email.lower(),
            'updated_at': datetime.now(timezone.utc)
        }

        # Only update these fields if they are explicitly provided in the request
        if 'phone' in data:
            updates['phone'] = phone
        if 'phone2' in data:
            updates['phone2'] = phone2
        if 'skill_level' in data:
            updates['skill_level'] = skill_level
        if 'experience' in data:
            updates['experience'] = experience
        if 'notes_to_organizers' in data:
            updates['notes_to_organizers'] = notes_to_organizers
        if 'has_binoculars' in data:
            updates['has_binoculars'] = has_binoculars
        if 'spotting_scope' in data:
            updates['spotting_scope'] = spotting_scope
        if 'interested_in_leadership' in data:
            updates['interested_in_leadership'] = interested_in_leadership
        if 'interested_in_scribe' in data:
            updates['interested_in_scribe'] = interested_in_scribe
        # Track if area changed for reassignment logging
        area_changed = False
        old_area = None
        if 'preferred_area' in data:
            old_area = current_participant.get('preferred_area')
            area_changed = preferred_area != old_area
            updates['preferred_area'] = preferred_area
            # If participant was a leader and area changed, remove leadership
            if current_participant.get('is_leader') and area_changed:
                updates['is_leader'] = False
                updates['assigned_area_leader'] = None
                updates['leadership_removed_by'] = user['email']
                updates['leadership_removed_at'] = datetime.now(timezone.utc)

        if not participant_model.update_participant(participant_id, updates):
            return jsonify({'success': False, 'message': 'Failed to update participant'})

        # Log reassignment if area changed
        if area_changed and old_area and preferred_area:
            try:
                reassignment_log = ReassignmentLogModel(g.db, selected_year)
                reassignment_log.log_reassignment(
                    participant_id, first_name, last_name, email,
                    old_area, preferred_area, user['email']
                )
            except Exception as e:
                logging.error(f"Error logging reassignment for participant {participant_id}: {e}")
                # Don't fail the reassignment if logging fails, but log the error
                return jsonify({
                    'success': True,
                    'message': f'Participant updated but reassignment logging failed: {str(e)}'
                })

        return jsonify({'success': True, 'message': 'Participant updated successfully'})

    except Exception as e:
        logging.error(f"Error editing participant: {e}")
        return jsonify({'success': False, 'message': f'Error updating participant: {str(e)}'})


# Email Test Trigger Routes (Test Server Only)
# Only register these routes when TEST_MODE is enabled to prevent abuse on production

def register_test_email_routes():
    """Register test email routes only in test mode."""
    import os
    
    @admin_bp.route('/test/trigger-team-updates', methods=['POST'])
    @require_admin
    def test_trigger_team_updates():
        """Test trigger for twice-daily team update emails (test server only)."""
        # Environment check: only work on test server
        if not is_test_server():
            return jsonify({'error': 'Test triggers only available on test server'}), 403
        
        try:
            # Generate twice-daily team updates for all areas with leaders
            results = generate_team_update_emails(current_app)
            
            message = f"Team update emails: {results['emails_sent']} sent, {results['areas_processed']} areas processed"
            if results['errors']:
                message += f", {len(results['errors'])} errors"
                
            return jsonify({
                'success': True, 
                'message': message,
                'details': results
            })
            
        except Exception as e:
            logging.error(f"Error in test_trigger_team_updates: {e}")
            return jsonify({
                'success': False, 
                'error': f'Error generating team update emails: {str(e)}'
            }), 500

    @admin_bp.route('/test/trigger-weekly-summaries', methods=['POST'])
    @require_admin 
    def test_trigger_weekly_summaries():
        """Test trigger for weekly summary emails (test server only)."""
        # Environment check: only work on test server
        if not is_test_server():
            return jsonify({'error': 'Test triggers only available on test server'}), 403
        
        try:
            # Generate weekly summaries for all areas with leaders
            results = generate_weekly_summary_emails(current_app)
            
            message = f"Weekly summary emails: {results['emails_sent']} sent, {results['areas_processed']} areas processed"
            if results['errors']:
                message += f", {len(results['errors'])} errors"
                
            return jsonify({
                'success': True, 
                'message': message,
                'details': results
            })
            
        except Exception as e:
            logging.error(f"Error in test_trigger_weekly_summaries: {e}")
            return jsonify({
                'success': False, 
                'error': f'Error generating weekly summary emails: {str(e)}'
            }), 500

    @admin_bp.route('/test/trigger-admin-digest', methods=['POST'])
    @require_admin
    def test_trigger_admin_digest():
        """Test trigger for daily admin digest email (test server only)."""
        # Environment check: only work on test server
        if not is_test_server():
            return jsonify({'error': 'Test triggers only available on test server'}), 403
        
        try:
            # Generate admin digest
            results = generate_admin_digest_email(current_app)
            
            if results['unassigned_count'] == 0:
                message = "Admin digest: No unassigned participants found"
            else:
                message = f"Admin digest: {results['emails_sent']} email sent for {results['unassigned_count']} unassigned participants"
                
            if results['errors']:
                message += f", {len(results['errors'])} errors"
                
            return jsonify({
                'success': True, 
                'message': message,
                'details': results
            })
            
        except Exception as e:
            logging.error(f"Error in test_trigger_admin_digest: {e}")
            return jsonify({
                'success': False, 
                'error': f'Error generating admin digest email: {str(e)}'
            }), 500


@admin_bp.route('/area-signup-type')
@require_admin
@limiter.limit(RATE_LIMITS['admin_general'])
def area_signup_type():
    """Manage area signup types (open vs admin-only)."""
    if not g.db:
        return render_template('admin/area_signup_type.html', error="Database unavailable")

    # Get selected year from query params, default to current year
    selected_year = int(request.args.get('year', datetime.now().year))

    # Get available years
    available_years = ParticipantModel.get_available_years(g.db)

    # Get all areas and their signup types
    signup_type_model = AreaSignupTypeModel(g.db)

    # Initialize all areas on first access (ensures all areas exist in Firestore)
    try:
        signup_type_model.initialize_all_areas()
    except Exception as e:
        logging.error(f"Error initializing area signup types: {e}")

    signup_types = signup_type_model.get_all_signup_types()

    # Organize by type for display
    open_areas = [code for code, settings in sorted(signup_types.items())
                  if not settings.get('admin_assignment_only', False)]
    admin_only_areas = [code for code, settings in sorted(signup_types.items())
                        if settings.get('admin_assignment_only', False)]

    return render_template('admin/area_signup_type.html',
                           selected_year=selected_year,
                           available_years=available_years,
                           signup_types=signup_types,
                           open_areas=open_areas,
                           admin_only_areas=admin_only_areas,
                           all_areas=get_all_areas(),
                           get_area_info=get_area_info,
                           current_user=get_current_user())


@admin_bp.route('/api/update-area-signup-type', methods=['POST'])
@require_admin
def update_area_signup_type_api():
    """API endpoint to update area signup type."""
    if not g.db:
        return jsonify({'success': False, 'error': 'Database unavailable'}), 500

    try:
        data = request.get_json()
        area_code = data.get('area_code', '').strip().upper()
        admin_assignment_only = data.get('admin_assignment_only', False)

        if not area_code:
            return jsonify({'success': False, 'error': 'Area code is required'}), 400

        # Validate area code
        if area_code not in get_all_areas():
            return jsonify({'success': False, 'error': f'Invalid area code: {area_code}'}), 400

        # Update signup type
        signup_type_model = AreaSignupTypeModel(g.db)
        user = get_current_user()
        success = signup_type_model.set_admin_assignment_only(
            area_code,
            admin_assignment_only,
            updated_by=user.get('email') if user else 'unknown'
        )

        if success:
            new_type = 'Admin Only' if admin_assignment_only else 'Open'
            return jsonify({
                'success': True,
                'message': f'Area {area_code} is now {new_type}',
                'area_code': area_code,
                'admin_assignment_only': admin_assignment_only
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update area signup type'}), 500

    except Exception as e:
        logging.error(f"Error updating area signup type: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/blocked-ips')
@require_admin
def blocked_ips():
    """View and manage blocked IPs."""
    blocker = IPBlockerService(g.db)
    blocks = blocker.get_all_blocks(include_expired=False)
    stats = blocker.get_block_stats()

    return render_template('admin/blocked_ips.html', blocks=blocks, stats=stats, current_user=get_current_user())


@admin_bp.route('/blocked-ips/<ip_address>/unblock', methods=['POST'])
@require_admin
def unblock_ip(ip_address):
    """Manually unblock an IP address."""
    blocker = IPBlockerService(g.db)

    if blocker.remove_block(ip_address):
        flash(f'IP {ip_address} has been unblocked.', 'success')
    else:
        flash(f'Failed to unblock IP {ip_address}.', 'error')

    return redirect(url_for('admin.blocked_ips'))


@admin_bp.route('/blocked-ips/cleanup', methods=['POST'])
@require_admin
def cleanup_blocks():
    """Manually trigger cleanup of expired blocks."""
    blocker = IPBlockerService(g.db)
    count = blocker.cleanup_expired()

    flash(f'Cleaned up {count} expired blocks.', 'success')

    return redirect(url_for('admin.blocked_ips'))


CIRCLE_SLUG_PATTERN_MESSAGE = 'Slug must be lowercase letters, numbers, and hyphens only.'


def _valid_circle_slug(slug):
    import re as _re
    return bool(_re.match(r'^[a-z0-9-]+$', slug or ''))


def _from_email_domain_allowed(email):
    """Check a proposed from_email's domain against the code-level allowlist
    (config/email_settings.py's ALLOWED_FROM_EMAIL_DOMAINS) - deliberately not
    admin-editable through any form, since it controls what this site's
    outgoing mail can claim to be sent from."""
    from config.email_settings import ALLOWED_FROM_EMAIL_DOMAINS
    if not email or '@' not in email:
        return False
    domain = email.rsplit('@', 1)[1].lower()
    return domain in ALLOWED_FROM_EMAIL_DOMAINS


def _can_manage_circle(slug):
    """True if the current session may edit this circle's own config/areas -
    either a super-admin (any circle) or a circle-admin for THIS circle only."""
    user_role = session.get('user_role')
    if user_role == 'super_admin':
        return True
    return user_role == 'admin' and g.circle_slug == slug


def _require_circle_manage_access(slug):
    """Returns a redirect response if access should be denied, else None."""
    if 'user_email' not in session:
        return redirect(url_for('auth.login', next=request.url))
    if not _can_manage_circle(slug):
        flash('You do not have permission to manage this circle.', 'error')
        return redirect(url_for('main.index'))
    return None


def _circle_form_data(form):
    """Extract and sanitize circle config fields from a submitted form."""
    return {
        'circle_name': sanitize_text_input(form.get('circle_name', ''), max_length=200),
        'name': sanitize_text_input(form.get('name', ''), max_length=200),
        'website': sanitize_text_input(form.get('website', ''), max_length=500),
        'contact': sanitize_email(form.get('contact', '')),
        'count_contact': sanitize_email(form.get('count_contact', '')),
        'count_event_name': sanitize_text_input(form.get('count_event_name', ''), max_length=200),
        'count_info_url': sanitize_text_input(form.get('count_info_url', ''), max_length=500),
        'from_email': sanitize_email(form.get('from_email', '')),
        # logo_path deliberately not settable here - a free-text server path
        # isn't sound UX or particularly safe; a real upload feature (storing
        # image bytes in the DB, not the app server's filesystem - see this
        # session's reasoning for area boundaries) is a scoped follow-up.
        'test_recipient': sanitize_email(form.get('test_recipient', '')),
        'display_timezone': sanitize_text_input(form.get('display_timezone', 'America/Vancouver'), max_length=100),
        'is_cbc': form.get('is_cbc') == 'on',
        'count_experience_label': sanitize_text_input(form.get('count_experience_label', ''), max_length=200),
        'feeder_counter_label': sanitize_text_input(form.get('feeder_counter_label', ''), max_length=200),
        'notes_placeholder_example': sanitize_notes(form.get('notes_placeholder_example', '')),
        'registration_opens_months': int(form.get('registration_opens_months') or 4),
        'registration_closes_days': int(form.get('registration_closes_days') or 1),
        'latitude': float(form['latitude']) if form.get('latitude') else None,
        'longitude': float(form['longitude']) if form.get('longitude') else None,
    }


@admin_bp.route('/circles')
@require_super_admin
def list_circles():
    """Super-admin console: list all count circles."""
    circles = CircleModel(g.db).get_all()
    return render_template('admin/circles.html', circles=circles, current_user=get_current_user())


@admin_bp.route('/circles/new', methods=['GET', 'POST'])
@require_super_admin
def new_circle():
    """Super-admin console: create a new count circle."""
    if request.method == 'GET':
        import pytz
        return render_template('admin/circle_form.html', circle=None, current_user=get_current_user(),
                                timezones=pytz.all_timezones)

    slug = sanitize_text_input(request.form.get('slug', ''), max_length=50).lower()
    if not _valid_circle_slug(slug):
        flash(f'Invalid slug: {CIRCLE_SLUG_PATTERN_MESSAGE}', 'error')
        return redirect(url_for('admin.new_circle'))

    if CircleModel(g.db).get_by_slug(slug):
        flash(f'A circle with slug "{slug}" already exists.', 'error')
        return redirect(url_for('admin.new_circle'))

    data = _circle_form_data(request.form)
    data['slug'] = slug

    if not _from_email_domain_allowed(data['from_email']):
        from config.email_settings import ALLOWED_FROM_EMAIL_DOMAINS
        flash(f'From email must be on one of these domains: {", ".join(ALLOWED_FROM_EMAIL_DOMAINS)}', 'error')
        return redirect(url_for('admin.new_circle'))

    count_date = request.form.get('count_date', '').strip()
    data['yearly_count_dates'] = {str(datetime.now().year): count_date} if count_date else {}

    CircleModel(g.db).create(data)
    flash(f'Circle "{data["circle_name"]}" created.', 'success')
    return redirect(url_for('admin.list_circles'))


@admin_bp.route('/circles/<slug>/edit', methods=['GET', 'POST'])
def edit_circle(slug):
    """Edit a circle's config - super-admin (any circle) or that circle's own admin."""
    denied = _require_circle_manage_access(slug)
    if denied:
        return denied

    circle = CircleModel(g.db).get_by_slug(slug)
    if not circle:
        flash('Circle not found.', 'error')
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        import pytz
        return render_template('admin/circle_form.html', circle=circle, current_user=get_current_user(),
                                timezones=pytz.all_timezones)

    data = _circle_form_data(request.form)

    if not _from_email_domain_allowed(data['from_email']):
        from config.email_settings import ALLOWED_FROM_EMAIL_DOMAINS
        flash(f'From email must be on one of these domains: {", ".join(ALLOWED_FROM_EMAIL_DOMAINS)}', 'error')
        return redirect(url_for('admin.edit_circle', slug=slug))

    count_date = request.form.get('count_date', '').strip()
    yearly_dates = dict(circle.get('yearly_count_dates') or {})
    current_year_key = str(datetime.now().year)
    if count_date:
        yearly_dates[current_year_key] = count_date
    else:
        # Field submitted blank - clear this year's date (revert to "TBD") rather
        # than silently leaving a previously-set date in place.
        yearly_dates.pop(current_year_key, None)
    data['yearly_count_dates'] = {str(k): v for k, v in yearly_dates.items()}

    CircleModel(g.db).update(slug, data)
    flash(f'Circle "{data["circle_name"]}" updated.', 'success')
    return redirect(url_for('admin.edit_circle', slug=slug))


@admin_bp.route('/circles/<slug>/admins', methods=['GET', 'POST'])
@require_super_admin
def circle_admins(slug):
    """Super-admin console: manage which emails are circle-admins for a circle."""
    circle = CircleModel(g.db).get_by_slug(slug)
    if not circle:
        flash('Circle not found.', 'error')
        return redirect(url_for('admin.list_circles'))

    model = CircleAdminModel(g.db)

    if request.method == 'POST':
        action = request.form.get('action')
        email = sanitize_email(request.form.get('email', ''))
        if action == 'add' and email and validate_email_format(email):
            model.add_admin(email, slug)
            flash(f'{email} added as an admin for {circle["circle_name"]}.', 'success')
        elif action == 'remove' and email:
            model.remove_admin(email, slug)
            flash(f'{email} removed as an admin for {circle["circle_name"]}.', 'success')
        else:
            flash('Invalid request.', 'error')
        return redirect(url_for('admin.circle_admins', slug=slug))

    admins = model.get_admins_for_circle(slug)
    return render_template('admin/circle_admins.html', circle=circle, admins=admins, current_user=get_current_user())


@admin_bp.route('/circles/<slug>/areas', methods=['GET', 'POST'])
def circle_areas_manage(slug):
    """Manage areas for a circle - super-admin (any circle) or that circle's own
    admin. Labels (name/description/difficulty/terrain) can be added/edited by
    hand below; boundaries (the map shape) are imported in bulk from a KML file
    via circle_areas_import_kml."""
    denied = _require_circle_manage_access(slug)
    if denied:
        return denied

    circle = CircleModel(g.db).get_by_slug(slug)
    if not circle:
        flash('Circle not found.', 'error')
        return redirect(url_for('main.index'))

    area_model = CircleAreaModel(g.db)

    if request.method == 'POST':
        code = sanitize_text_input(request.form.get('code', ''), max_length=10).upper()
        name = sanitize_text_input(request.form.get('name', ''), max_length=200)
        description = sanitize_notes(request.form.get('description', ''))
        difficulty = sanitize_text_input(request.form.get('difficulty', ''), max_length=50)
        terrain = sanitize_text_input(request.form.get('terrain', ''), max_length=200)

        if not code or not name:
            flash('Area code and name are required.', 'error')
        elif area_model.get_area(slug, code):
            area_model.update_area(slug, code, name=name, description=description, difficulty=difficulty, terrain=terrain)
            flash(f'Area {code} updated.', 'success')
        else:
            area_model.add_area(slug, code, name, description=description, difficulty=difficulty, terrain=terrain)
            flash(f'Area {code} added.', 'success')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    areas = area_model.get_areas_for_circle(slug)
    return render_template('admin/circle_areas.html', circle=circle, areas=areas, current_user=get_current_user())


MAX_KML_UPLOAD_BYTES = 5 * 1024 * 1024  # generous - real CBC-circle KML exports run well under 1MB


@admin_bp.route('/circles/<slug>/areas/import-kml', methods=['POST'])
def circle_areas_import_kml(slug):
    """Bulk-import area boundaries (+ name/description) from an uploaded KML file,
    exported from Google My Maps. Overwrites name/description/boundary_geojson for
    any area code the KML defines, leaving difficulty/terrain (and any area not
    mentioned in the KML) untouched. Also refreshes the circle's own lat/lng from
    the imported areas' calculated center, since KML import supersedes manual
    lat/lng entry (see the circle-config form)."""
    denied = _require_circle_manage_access(slug)
    if denied:
        return denied

    circle = CircleModel(g.db).get_by_slug(slug)
    if not circle:
        flash('Circle not found.', 'error')
        return redirect(url_for('main.index'))

    upload = request.files.get('kml_file')
    if not upload or not upload.filename:
        flash('Choose a KML file to import.', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    if not upload.filename.lower().endswith('.kml'):
        flash('That file does not look like a .kml file.', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    raw = upload.read(MAX_KML_UPLOAD_BYTES + 1)
    if len(raw) > MAX_KML_UPLOAD_BYTES:
        flash(f'That file is larger than the {MAX_KML_UPLOAD_BYTES // (1024 * 1024)}MB limit.', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    try:
        kml_content = raw.decode('utf-8')
    except UnicodeDecodeError:
        flash('Could not read that file as UTF-8 text - is it really a KML file?', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    try:
        all_areas = parse_kml_string(kml_content)
    except KmlParseError as e:
        flash(f'Could not import KML: {e}', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    areas = filter_main_areas(all_areas)
    if not areas:
        flash('No main areas (non-sub-area placemarks) were found in that file.', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    area_model = CircleAreaModel(g.db)
    try:
        for area in areas:
            area_model.upsert_from_kml(
                slug, area['letter_code'], area['name'], area['description'], area['geometry'],
                commit=False,
            )

        map_config = calculate_map_center_and_bounds(areas)
        if map_config:
            CircleModel(g.db).update(slug, {
                'latitude': map_config['center'][0],
                'longitude': map_config['center'][1],
            })
        else:
            g.db.commit()
    except Exception:
        g.db.rollback()
        logging.exception(f'KML import failed for circle {slug}')
        flash('Something went wrong while importing that file - no changes were saved.', 'error')
        return redirect(url_for('admin.circle_areas_manage', slug=slug))

    skipped = len(all_areas) - len(areas)
    message = f'Imported {len(areas)} area boundaries for {circle["circle_name"]}.'
    if skipped:
        message += f' Skipped {skipped} sub-area placemark(s).'
    flash(message, 'success')
    return redirect(url_for('admin.circle_areas_manage', slug=slug))


# Only register test routes when TEST_MODE is enabled
if os.getenv('TEST_MODE', '').lower() == 'true':
    register_test_email_routes()