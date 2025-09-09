from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response, g
from google.cloud import firestore
from models.participant import ParticipantModel
from models.area_leader import AreaLeaderModel
from models.removal_log import RemovalLogModel
from config.areas import get_area_info, get_all_areas
from routes.auth import require_admin, get_current_user
from services.email_service import email_service
from datetime import datetime
import csv
import logging
from io import StringIO

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
def load_db():
    """Load database client and check admin access."""
    try:
        g.db = firestore.Client()
    except Exception as e:
        g.db = None
        flash('Database unavailable.', 'error')


@admin_bp.route('/')
@require_admin
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
                           current_user=get_current_user())


@admin_bp.route('/participants')
@require_admin
def participants():
    """View and manage all participants."""
    if not g.db:
        return render_template('admin/participants.html', participants=[], error="Database unavailable")

    selected_year = int(request.args.get('year', datetime.now().year))
    participant_model = ParticipantModel(g.db, selected_year)
    available_years = ParticipantModel.get_available_years(g.db)

    participants = participant_model.get_all_participants()

    return render_template('admin/participants.html',
                           participants=participants,
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
def assign_participant():
    """Assign a participant to an area."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.unassigned'))

    participant_id = request.form.get('participant_id')
    area_code = request.form.get('area_code')
    selected_year = int(request.form.get('year', datetime.now().year))

    if not participant_id or not area_code:
        flash('Participant ID and area code are required.', 'error')
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
def add_leader():
    """Manually add a new area leader."""
    if not g.db:
        flash('Database unavailable.', 'error')
        return redirect(url_for('admin.leaders'))

    selected_year = int(request.form.get('year', datetime.now().year))
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    leader_email = request.form.get('leader_email', '').strip().lower()
    cell_phone = request.form.get('cell_phone', '').strip()
    area_code = request.form.get('area_code', '').strip().upper()
    notes = request.form.get('notes', '').strip()

    # Validate required fields
    if not all([first_name, last_name, leader_email, cell_phone, area_code]):
        flash('All required fields must be completed.', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    # Validate area code
    from config.areas import get_area_info
    if not get_area_info(area_code):
        flash(f'Invalid area code: {area_code}', 'error')
        return redirect(url_for('admin.leaders', year=selected_year))

    area_leader_model = AreaLeaderModel(g.db, selected_year)
    user = get_current_user()

    try:
        # Check if leader already assigned to this area
        existing_leaders = area_leader_model.get_leaders_by_area(area_code)
        for leader in existing_leaders:
            if leader.leader_email == leader_email:
                flash(f'{first_name} {last_name} is already assigned as a leader for Area {area_code}.', 'warning')
                return redirect(url_for('admin.leaders', year=selected_year))

        # Check if this email is already leading another area (one area per leader rule)
        leader_areas = area_leader_model.get_areas_by_leader_email(leader_email)
        if leader_areas:
            existing_area = leader_areas[0].area_code
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
            leader_name=f"{participant['first_name']} {participant['last_name']}",
            leader_phone=participant.get('phone', ''),
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

    # Write header
    writer.writerow([
        'First Name', 'Last Name', 'Email', 'Phone', 'Skill Level',
        'Experience', 'Area', 'Area Leader', 'Leadership Interest',
        'Registration Date', 'Year'
    ])

    # Write participant data
    for p in participants:
        writer.writerow([
            p.get('first_name', ''),
            p.get('last_name', ''),
            p.get('email', ''),
            p.get('phone', ''),
            p.get('skill_level', ''),
            p.get('experience', ''),
            p.get('preferred_area', ''),
            'Yes' if p.get('is_leader', False) else 'No',
            'Yes' if p.get('interested_in_leadership', False) else 'No',
            p.get('created_at', '').strftime('%Y-%m-%d %H:%M') if p.get('created_at') else '',
            selected_year
        ])

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