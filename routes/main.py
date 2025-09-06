from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from google.cloud import firestore
from models.participant import ParticipantModel
from config.areas import get_area_info, get_all_areas
import re

main_bp = Blueprint('main', __name__)

# Initialize Firestore and models
try:
    db = firestore.Client()
    participant_model = ParticipantModel(db)
except Exception as e:
    print(f"Warning: Could not initialize Firestore: {e}")
    db = None
    participant_model = None


@main_bp.route('/')
def index():
    """Main registration page."""
    return render_template('index.html')


@main_bp.route('/register', methods=['POST'])
def register():
    """Handle registration form submission."""
    if not participant_model:
        flash('Registration system temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('main.index'))

    # Get form data
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone = request.form.get('phone', '').strip()
    skill_level = request.form.get('skill_level', '')
    experience = request.form.get('experience', '')
    preferred_area = request.form.get('preferred_area', '')
    is_leader = request.form.get('is_leader') == 'on'

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

    # Check if email already registered
    if participant_model.email_exists(email):
        errors.append('This email address is already registered for this year')

    if errors:
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('main.index'))

    # Handle auto-assignment
    if preferred_area == 'ANYWHERE':
        preferred_area = assign_area_automatically()

    interested_in_leadership = request.form.get('interested_in_leadership') == 'on'

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
        'is_leader': False,           # Always false initially
        'assigned_area_leader': None, # Admin sets this later
        'auto_assigned': request.form.get('preferred_area') == 'ANYWHERE'
    }

    try:
        participant_id = participant_model.add_participant(participant_data)
        flash(f'Registration successful! You have been registered for Area {preferred_area}.', 'success')
        return redirect(url_for('main.registration_success', area=preferred_area))
    except Exception as e:
        flash('Registration failed. Please try again.', 'error')
        return redirect(url_for('main.index'))


@main_bp.route('/success')
def registration_success():
    """Registration success page."""
    area = request.args.get('area', 'Unknown')
    area_info = get_area_info(area)
    return render_template('registration_success.html', area=area, area_info=area_info)


def is_valid_email(email):
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def assign_area_automatically():
    """Assign user to area with lowest current registration count."""
    if not participant_model:
        return 'A'  # Fallback

    area_counts = participant_model.get_area_counts()
    all_areas = get_all_areas()

    # Find area with minimum registrations
    min_count = float('inf')
    assigned_area = 'A'  # Default fallback

    for area in all_areas:
        count = area_counts.get(area, 0)
        if count < min_count:
            min_count = count
            assigned_area = area

    return assigned_area