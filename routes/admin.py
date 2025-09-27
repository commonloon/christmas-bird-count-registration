# Updated by Claude AI on 2025-09-17
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, g, current_app
from google.cloud import firestore
from config.database import get_firestore_client
from config.email_settings import is_test_server
from models.participant import ParticipantModel
from models.removal_log import RemovalLogModel
from config.areas import get_area_info, get_all_areas, get_public_areas
from config.fields import (
    normalize_participant_record, get_participant_csv_fields,
    get_participant_field_default, get_participant_display_name
)
from config.admins import get_admin_emails
from routes.auth import require_admin, get_current_user
from services.email_service import email_service
from services.security import (
    sanitize_name, sanitize_email, sanitize_phone, sanitize_notes,
    validate_area_code, validate_experience, is_suspicious_input, log_security_event
)
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS, get_rate_limit_message
from datetime import datetime
import csv
import logging
import os
from io import StringIO

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
def load_db():
    """Load database client and check admin access."""
    try:
        g.db, _ = get_firestore_client()
    except Exception as e:
        g.db = None
        flash('Database unavailable.', 'error')


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
                           current_user=get_current_user())


@admin_bp.route('/participants')
@require_admin
def participants():
    """View and manage all participants."""
    if not g.db:
        return render_template('admin/participants.html',
                             participants=[],
                             area_leaders={},
                             error="Database unavailable")

    selected_year = int(request.args.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    available_years = ParticipantModel.get_available_years(g.db)

    all_participants = participant_model.get_all_participants()
    all_leaders = participant_model.get_leaders()

    # Normalize participant data to ensure all fields are present
    normalized_participants = [normalize_participant_record(p) for p in all_participants]

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
                           available_years=available_years,
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
    user = get_current_user()

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
def leaders():
    """Manage area leaders."""
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
                    row.append(value)
                writer.writerow(row)

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=area_leaders_{selected_year}_{datetime.now().strftime("%Y%m%d")}.csv'
        response.headers['Content-type'] = 'text/csv'

        return response

    return render_template('admin/leaders.html',
                           all_leaders=normalized_leaders,
                           areas_without_leaders=areas_without_leaders,
                           leadership_interested=leadership_interested,
                           all_areas=all_areas,
                           get_area_info=get_area_info,
                           selected_year=selected_year,
                           available_years=available_years,
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

    if len(phone) > 20:
        flash('Phone number must be 20 characters or less.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Validate area code
    if not validate_area_code(area_code):
        flash(f'Invalid area code: {area_code}', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    user = get_current_user()

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

        # Create the area leader record
        leader_data = {
            'area_code': area_code,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
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
        # Check if this person (identity) is already leading another area (one area per leader rule)
        first_name = participant['first_name']
        last_name = participant['last_name']
        participant_email = participant['email']
        leader_areas = participant_model.get_leaders_by_identity(first_name, last_name, participant_email)
        if leader_areas:
            existing_area = leader_areas[0]['assigned_area_leader']
            flash(f'{first_name} {last_name} is already leading Area {existing_area}. Leaders can only lead one area.', 'error')
            return redirect(url_for('admin.leaders', year=selected_year))

        # Update participant record with leadership
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


@admin_bp.route('/export_csv')
@require_admin
def export_csv():
    """Export all participants as CSV."""
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
        from config.fields import get_participant_csv_fields
        fieldnames = get_participant_csv_fields()

        # Write CSV header
        writer.writerow(fieldnames)

        # Write participant data
        from config.fields import get_participant_field_default
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
                row.append(value)
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
            
        if len(phone) > 20:
            return jsonify({'success': False, 'message': 'Phone number must be 20 characters or less'})

        if len(phone2) > 20:
            return jsonify({'success': False, 'message': 'Secondary phone number must be 20 characters or less'})

        # Validate area code
        if not validate_area_code(area_code):
            return jsonify({'success': False, 'message': f'Invalid area code: {area_code}'})

        # Initialize models
        participant_model = ParticipantModel(g.db, selected_year)
        user = get_current_user()

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
            'updated_at': datetime.now()
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

        if len(phone) > 20:
            return jsonify({'success': False, 'message': 'Phone number must be 20 characters or less'})

        if len(phone2) > 20:
            return jsonify({'success': False, 'message': 'Secondary phone number must be 20 characters or less'})

        # Validate skill level
        valid_skill_levels = ['Beginner', 'Intermediate', 'Expert']
        if skill_level and skill_level not in valid_skill_levels:
            return jsonify({'success': False, 'message': f'Invalid skill level: {skill_level}'})

        # Validate experience
        if experience and not validate_experience(experience):
            return jsonify({'success': False, 'message': f'Invalid experience level: {experience}'})

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
            'phone': phone,
            'phone2': phone2,
            'skill_level': skill_level,
            'experience': experience,
            'updated_at': datetime.now()
        }

        # Only update these fields if they are explicitly provided in the request
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

        if not participant_model.update_participant(participant_id, updates):
            return jsonify({'success': False, 'message': 'Failed to update participant'})

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
            # Import here to avoid circular imports
            from test.email_generator import generate_team_update_emails
            
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
            # Import here to avoid circular imports
            from test.email_generator import generate_weekly_summary_emails
            
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
            # Import here to avoid circular imports
            from test.email_generator import generate_admin_digest_email
            
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


# Only register test routes when TEST_MODE is enabled
if os.getenv('TEST_MODE', '').lower() == 'true':
    register_test_email_routes()