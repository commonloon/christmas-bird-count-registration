from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from google.cloud import firestore
from models.participant import ParticipantModel
from config.areas import get_area_info, get_all_areas
from services.email_service import email_service
import re
from datetime import datetime

main_bp = Blueprint('main', __name__)


@main_bp.before_request
def load_db():
    """Load database client for this request."""
    try:
        g.db = firestore.Client()
    except Exception as e:
        g.db = None
        print(f"Warning: Could not initialize Firestore: {e}")


@main_bp.route('/')
def index():
    """Main registration page."""
    return render_template('index.html')


@main_bp.route('/register', methods=['POST'])
def register():
    """Handle registration form submission."""
    if not g.db:
        flash('Registration system temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('main.index'))

    # Initialize year-aware participant model
    current_year = datetime.now().year
    participant_model = ParticipantModel(g.db, current_year)

    # Get form data
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    skill_level = request.form.get('skill_level', '')
    experience = request.form.get('experience', '')
    preferred_area = request.form.get('preferred_area', '')
    interested_in_leadership = request.form.get('interested_in_leadership') == 'on'

    # Basic validation
    errors = []

    if not first_name:
        errors.append('First name is required')
    if not last_name:
        errors.append('Last name is required')
    if not email or not is_valid_email(email):
        errors.append('Valid email address is required')
    if not skill_level:
        errors.append('Birding skill level is required')
    if not experience:
        errors.append('CBC experience level is required')
    if not preferred_area:
        errors.append('Area selection is required')

    # Check if email already registered for current year
    if participant_model.email_exists(email):
        errors.append('This email address is already registered for this year')

    # Validate preferred area
    valid_areas = get_all_areas() + ['UNASSIGNED']
    if preferred_area not in valid_areas:
        errors.append('Invalid area selection')

    if errors:
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('main.index'))

    # Create participant record
    participant_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': phone,
        'skill_level': skill_level,
        'experience': experience,
        'preferred_area': preferred_area,
        'interested_in_leadership': interested_in_leadership,
        'is_leader': False,  # Always false initially - admin assigns
        'assigned_area_leader': None,
        'auto_assigned': False  # No longer auto-assigning
    }

    try:
        participant_id = participant_model.add_participant(participant_data)

        if preferred_area == 'UNASSIGNED':
            flash(
                'Registration successful! An administrator will assign you to an area and your area leader will contact you.',
                'success')
            # Send confirmation email
            email_service.send_registration_confirmation(
                email,
                f"{first_name} {last_name}",
                "will be assigned by organizers"
            )
        else:
            flash(f'Registration successful! You have been registered for Area {preferred_area}.', 'success')
            # Send confirmation email
            email_service.send_registration_confirmation(
                email,
                f"{first_name} {last_name}",
                preferred_area
            )

        return redirect(url_for('main.registration_success',
                                area=preferred_area,
                                participant_id=participant_id))

    except Exception as e:
        print(f"Registration error: {e}")
        flash('Registration failed. Please try again.', 'error')
        return redirect(url_for('main.index'))


@main_bp.route('/success')
def registration_success():
    """Registration success page."""
    area = request.args.get('area', 'Unknown')
    participant_id = request.args.get('participant_id')

    if area == 'UNASSIGNED':
        area_info = {
            'name': 'Assignment Pending',
            'description': 'You will be assigned to an area by the organizers based on volunteer needs and your experience level.',
            'difficulty': 'To be determined',
            'terrain': 'To be determined'
        }
    else:
        area_info = get_area_info(area)

    return render_template('registration_success.html',
                           area=area,
                           area_info=area_info,
                           participant_id=participant_id)


@main_bp.route('/about')
def about():
    """About the Christmas Bird Count."""
    return render_template('about.html')


@main_bp.route('/areas')
def areas():
    """Information about count areas."""
    return render_template('areas.html', areas=get_all_areas())


def is_valid_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None