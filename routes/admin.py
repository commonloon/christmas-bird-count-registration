# Updated by Claude AI on 2025-09-12
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, g, current_app
from google.cloud import firestore
from config.database import get_firestore_client
from config.email_settings import is_test_server
from models.participant import ParticipantModel
from models.area_leader import AreaLeaderModel
from models.removal_log import RemovalLogModel
from config.areas import get_area_info, get_all_areas, get_public_areas
from routes.auth import require_admin, get_current_user
from services.email_service import email_service
from services.security import (
    sanitize_name, sanitize_email, sanitize_phone, sanitize_notes,
    validate_area_code, is_suspicious_input, log_security_event
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
    area_leader_model = AreaLeaderModel(g.db, selected_year)
    removal_model = RemovalLogModel(g.db, selected_year)

    # Get available years
    available_years = ParticipantModel.get_available_years(g.db)

    # Get dashboard data
    participants = participant_model.get_all_participants()
    unassigned_participants = participant_model.get_unassigned_participants()
    area_counts = participant_model.get_area_counts()
    areas_without_leaders = area_leader_model.get_areas_without_leaders()
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
    area_leader_model = AreaLeaderModel(g.db, selected_year)
    available_years = ParticipantModel.get_available_years(g.db)

    all_participants = participant_model.get_all_participants()
    all_leaders = area_leader_model.get_all_leaders()
    
    # Create area leader lookup
    area_leaders = {}
    for leader in all_leaders:
        area = leader.get('area_code')
        if area:
            if area not in area_leaders:
                area_leaders[area] = []
            area_leaders[area].append(leader)
    
    return render_template('admin/participants.html',
                           participants=all_participants,
                           area_leaders=area_leaders,
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
    area_leader_model = AreaLeaderModel(g.db, selected_year)
    available_years = ParticipantModel.get_available_years(g.db)

    participants = participant_model.get_participants_by_area(area_code)
    area_leaders = area_leader_model.get_leaders_by_area(area_code)
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
    area_leader_model = AreaLeaderModel(g.db, selected_year)
    participant_model = ParticipantModel(g.db, selected_year)
    available_years = AreaLeaderModel.get_available_years(g.db)

    all_leaders = area_leader_model.get_all_leaders()
    areas_without_leaders = area_leader_model.get_areas_without_leaders()
    leadership_interested = participant_model.get_participants_interested_in_leadership()
    all_areas = get_all_areas()

    # Check if CSV export is requested
    if request.args.get('format') == 'csv':
        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        if all_leaders:
            # Get all field names from the first leader record
            fieldnames = list(all_leaders[0].keys())

            # Write CSV header
            writer.writerow(fieldnames)

            # Sort leaders by area code
            sorted_leaders = sorted(all_leaders, key=lambda x: x.get('area_code', ''))

            # Write leader data
            for leader in sorted_leaders:
                row = []
                for field in fieldnames:
                    value = leader.get(field, '')
                    # Handle datetime objects
                    if hasattr(value, 'strftime'):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    row.append(value)
                writer.writerow(row)

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=area_leaders_{selected_year}_{datetime.now().strftime("%Y%m%d")}.csv'
        response.headers['Content-type'] = 'text/csv'

        return response

    return render_template('admin/leaders.html',
                           all_leaders=all_leaders,
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
    leader_email = sanitize_email(request.form.get('leader_email', ''))
    cell_phone = sanitize_phone(request.form.get('cell_phone', ''))
    area_code = request.form.get('area_code', '').strip().upper()
    notes = sanitize_notes(request.form.get('notes', ''))
    
    # Security checks
    user = get_current_user()
    all_text_inputs = [first_name, last_name, cell_phone, notes]
    for text_input in all_text_inputs:
        if is_suspicious_input(text_input):
            log_security_event('Suspicious admin input', f'Add leader attempt with suspicious input', user.get('email'))
            flash('Invalid input detected. Please check your entries.', 'error')
            return redirect(url_for('admin.leaders', year=selected_year))

    # Validate required fields
    if not all([first_name, last_name, leader_email, cell_phone, area_code]):
        flash('All required fields must be completed.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))
        
    # Length validations
    if len(first_name) > 100 or len(last_name) > 100:
        flash('Names must be 100 characters or less.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))
        
    if len(leader_email) > 254:
        flash('Email address is too long.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))
        
    if len(cell_phone) > 20:
        flash('Phone number must be 20 characters or less.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Validate area code
    if not validate_area_code(area_code):
        flash(f'Invalid area code: {area_code}', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    area_leader_model = AreaLeaderModel(g.db, selected_year)
    user = get_current_user()

    try:
        # Check if leader already assigned to this area
        existing_leaders = area_leader_model.get_leaders_by_area(area_code)
        for leader in existing_leaders:
            if leader['leader_email'] == leader_email:
                flash(f'{first_name} {last_name} is already assigned as a leader for Area {area_code}.', 'warning')
                return redirect(url_for('admin.leaders', year=selected_year))

        # Check if this email is already leading another area (one area per leader rule)
        leader_areas = area_leader_model.get_areas_by_leader_email(leader_email)
        if leader_areas:
            existing_area = leader_areas[0]['area_code']
            flash(f'{leader_email} is already leading Area {existing_area}. Leaders can only lead one area.', 'error')
            return redirect(url_for('admin.leaders', year=selected_year))

        # Create the area leader record
        leader_data = {
            'area_code': area_code,
            'leader_email': leader_email,
            'first_name': first_name,
            'last_name': last_name,
            'cell_phone': cell_phone,
            'assigned_by': user['email'],
            'assigned_at': datetime.now(),
            'active': True,
            'year': selected_year,
            'created_from_participant': False,
            'notes': notes if notes else None
        }

        leader_id = area_leader_model.add_leader(leader_data)
        
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
    area_leader_model = AreaLeaderModel(g.db, selected_year)
    user = get_current_user()

    # Get participant details
    participant = participant_model.get_participant(participant_id)
    if not participant:
        flash('Participant not found.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    try:
        # Check if this email is already leading another area (one area per leader rule)
        participant_email = participant['email']
        leader_areas = area_leader_model.get_areas_by_leader_email(participant_email)
        if leader_areas:
            existing_area = leader_areas[0]['area_code']
            flash(f'{participant_email} is already leading Area {existing_area}. Leaders can only lead one area.', 'error')
            return redirect(url_for('admin.leaders', year=selected_year))

        # Update participant record
        participant_model.assign_leadership(participant_id, area_code, user['email'])

        # Create area leader record
        area_leader_model.assign_leader(
            area_code=area_code,
            leader_email=participant['email'],
            first_name=participant['first_name'],
            last_name=participant['last_name'],
            cell_phone=participant.get('phone', ''),
            assigned_by=user['email']
        )

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
        # Get all field names from the first participant record
        fieldnames = list(sorted_participants[0].keys())

        # Write CSV header
        writer.writerow(fieldnames)

        # Write participant data
        for p in sorted_participants:
            row = []
            for field in fieldnames:
                value = p.get(field, '')
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

    from config.admins import get_admin_emails
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
        leader_id = data.get('leader_id', '').strip()
        area_code = data.get('area_code', '').strip().upper()
        first_name = sanitize_name(data.get('first_name', ''))
        last_name = sanitize_name(data.get('last_name', ''))
        leader_email = sanitize_email(data.get('leader_email', ''))
        cell_phone = sanitize_phone(data.get('cell_phone', ''))
        selected_year = int(data.get('year', datetime.now().year))
        
        # Security checks
        user = get_current_user()
        all_text_inputs = [first_name, last_name, cell_phone]
        for text_input in all_text_inputs:
            if is_suspicious_input(text_input):
                log_security_event('Suspicious admin input', f'Edit leader attempt with suspicious input', user.get('email'))
                return jsonify({'success': False, 'message': 'Invalid input detected'})

        # Validate required fields
        if not all([leader_id, area_code, first_name, last_name, leader_email]):
            return jsonify({'success': False, 'message': 'All fields are required except phone'})
            
        # Length validations
        if len(first_name) > 100 or len(last_name) > 100:
            return jsonify({'success': False, 'message': 'Names must be 100 characters or less'})
            
        if len(leader_email) > 254:
            return jsonify({'success': False, 'message': 'Email address is too long'})
            
        if len(cell_phone) > 20:
            return jsonify({'success': False, 'message': 'Phone number must be 20 characters or less'})

        # Validate area code
        if not validate_area_code(area_code):
            return jsonify({'success': False, 'message': f'Invalid area code: {area_code}'})

        # Initialize models
        area_leader_model = AreaLeaderModel(g.db, selected_year)
        participant_model = ParticipantModel(g.db, selected_year)
        user = get_current_user()

        # Get current leader data
        current_leader = area_leader_model.get_area_leader(leader_id)
        if not current_leader:
            return jsonify({'success': False, 'message': 'Leader not found'})

        current_email = current_leader.get('leader_email')
        current_area = current_leader.get('area_code')

        # Check if email is changing and if new email is already leading another area
        if leader_email != current_email:
            existing_areas = area_leader_model.get_areas_by_leader_email(leader_email)
            if existing_areas:
                existing_area = existing_areas[0]['area_code']
                return jsonify({'success': False, 'message': f'Email {leader_email} is already leading Area {existing_area}'})

        # Update leader record
        updates = {
            'area_code': area_code,
            'first_name': first_name,
            'last_name': last_name,
            'leader_email': leader_email,
            'cell_phone': cell_phone,
            'updated_by': user['email'],
            'updated_at': datetime.now()
        }

        if not area_leader_model.update_leader(leader_id, updates):
            return jsonify({'success': False, 'message': 'Failed to update leader'})

        # If this leader was promoted from a participant, update participant record too
        if current_leader.get('created_from_participant'):
            # Find participant by old email
            participants = participant_model.get_participants_by_email(current_email)
            if participants:
                participant = participants[0]
                participant_updates = {
                    'preferred_area': area_code,
                    'updated_at': datetime.now()
                }
                
                # If email changed, update that too
                if leader_email != current_email:
                    participant_updates['email'] = leader_email
                
                participant_model.update_participant(participant['id'], participant_updates)

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
        area_leader_model = AreaLeaderModel(g.db, selected_year)
        participant_model = ParticipantModel(g.db, selected_year)
        user = get_current_user()

        # Get leader data before deletion
        leader = area_leader_model.get_area_leader(leader_id)
        if not leader:
            return jsonify({'success': False, 'message': 'Leader not found'})

        leader_email = leader.get('leader_email')

        # Remove leader (deactivate)
        if not area_leader_model.remove_leader(leader_id, user['email']):
            return jsonify({'success': False, 'message': 'Failed to delete leader'})

        # If this leader was promoted from a participant, reset their is_leader status
        if leader.get('created_from_participant'):
            participants = participant_model.get_participants_by_email(leader_email)
            if participants:
                participant = participants[0]
                participant_updates = {
                    'is_leader': False,
                    'assigned_area_leader': None,
                    'updated_at': datetime.now()
                }
                participant_model.update_participant(participant['id'], participant_updates)

        return jsonify({'success': True, 'message': 'Leader deleted successfully'})

    except Exception as e:
        logging.error(f"Error deleting leader: {e}")
        return jsonify({'success': False, 'message': f'Error deleting leader: {str(e)}'})


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