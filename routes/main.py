# Updated by Claude AI on 2026-01-12
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, send_from_directory, abort
from config.database import get_db_session
from models.participant import ParticipantModel
from models.area_signup_type import AreaSignupTypeModel
from config.areas import get_area_info, get_all_areas
from config.organization import LOGO_PATH, get_count_date, get_registration_status, get_organization_variables
from services.email_service import email_service
from services.security import (
    sanitize_name, sanitize_email, sanitize_phone, sanitize_notes,
    validate_area_code, validate_skill_level, validate_experience,
    validate_participation_type, validate_email_format, is_suspicious_input, log_security_event
)
from services.ip_blocker import IPBlockerService, get_client_ip
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS, get_rate_limit_message
from config.ip_blocking import HONEYPOT_ENABLED
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.before_request
def load_db():
    """Load database session for this request."""
    g.db = get_db_session()


@main_bp.route('/')
def index():
    """Main registration page."""
    if getattr(g, 'is_landing_host', False):
        from models.circle import CircleModel
        all_circles = CircleModel(g.db).get_all() if g.db else []
        # Deliberately excludes contact email - it's fetched on demand via
        # /api/circles/<slug>/contact instead, so it never sits in this page's
        # initial HTML/JSON where a scraper could harvest it for free (bots
        # scraping this contact address caused a real spam problem previously).
        circles = [
            {
                'slug': c['slug'],
                'circle_name': c['circle_name'],
                'organization_name': c['name'],
                'latitude': c['latitude'],
                'longitude': c['longitude'],
            }
            for c in all_circles
        ]
        return render_template('landing.html', circles=circles)

    # Check registration status
    reg_status = get_registration_status()

    # Get public areas from Firestore
    if g.db:
        signup_type_model = AreaSignupTypeModel(g.db)
        public_areas = signup_type_model.get_public_areas()
    else:
        # Fallback to all areas if database unavailable (graceful degradation)
        public_areas = get_all_areas()

    # Pass all query parameters to template for form restoration
    form_data = dict(request.args)

    # Fetch area leaders from database
    all_areas = get_all_areas()
    area_leaders = {}  # Maps area_code -> list of leaders

    try:
        if g.db:
            current_year = datetime.now().year
            participant_model = ParticipantModel(g.db, current_year)

            # Get all leaders for current year
            leaders = participant_model.get_leaders()

            # Organize leaders by assigned area
            for leader in leaders:
                assigned_area = leader.get('assigned_area_leader')
                if assigned_area:
                    if assigned_area not in area_leaders:
                        area_leaders[assigned_area] = []
                    area_leaders[assigned_area].append(leader)

            # Sort leaders within each area by first name
            for area in area_leaders:
                area_leaders[area].sort(key=lambda x: x.get('first_name', ''))
    except Exception as e:
        print(f"Warning: Could not fetch area leaders: {e}")

    # Ensure all areas are represented (with empty list if no leaders)
    for area_code in all_areas:
        if area_code not in area_leaders:
            area_leaders[area_code] = []

    count_date = get_count_date()
    org_vars = get_organization_variables()

    return render_template('index.html',
                         public_areas=public_areas,
                         get_area_info=get_area_info,
                         form_data=form_data,
                         all_areas=all_areas,
                         area_leaders=area_leaders,
                         count_date=count_date,
                         registration_status=reg_status,
                         logo_path=LOGO_PATH,
                         **org_vars)


@main_bp.route('/register', methods=['POST'])
@limiter.limit(RATE_LIMITS['registration'], error_message=get_rate_limit_message('registration'))
def register():
    """Handle registration form submission."""
    # Check if registration is open
    reg_status = get_registration_status()
    if not reg_status['is_open']:
        flash('Registration is currently closed. Please check back later.', 'error')
        return redirect(url_for('main.index'))

    if not g.db:
        flash('Registration system temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('main.index'))

    # Initialize year-aware models
    current_year = datetime.now().year
    participant_model = ParticipantModel(g.db, current_year)

    # Get and sanitize form data
    first_name = sanitize_name(request.form.get('first_name', ''))
    last_name = sanitize_name(request.form.get('last_name', ''))
    email = sanitize_email(request.form.get('email', ''))
    phone = sanitize_phone(request.form.get('phone', ''))
    phone2 = sanitize_phone(request.form.get('phone2', ''))
    skill_level = request.form.get('skill_level', '').strip()
    experience = request.form.get('experience', '').strip()
    preferred_area = request.form.get('preferred_area', '').strip().upper()

    # Get public areas for validation
    signup_type_model = AreaSignupTypeModel(g.db)
    public_areas = signup_type_model.get_public_areas()
    interested_in_leadership = request.form.get('interested_in_leadership') == 'on'
    interested_in_scribe = request.form.get('interested_in_scribe') == 'on'
    
    # Get and sanitize new fields
    participation_type = request.form.get('participation_type', '').strip()
    has_binoculars = request.form.get('has_binoculars') == 'on'
    spotting_scope = request.form.get('spotting_scope') == 'on'
    notes_to_organizers = sanitize_notes(request.form.get('notes_to_organizers', ''))
    
    # Security check for suspicious input patterns
    all_text_inputs = [first_name, last_name, phone, phone2, notes_to_organizers]
    for text_input in all_text_inputs:
        if is_suspicious_input(text_input):
            log_security_event('Suspicious input detected', f'Registration attempt with suspicious input: {text_input[:50]}...', email)
            flash('Invalid input detected. Please check your entries and try again.', 'error')
            return redirect(url_for('main.index'))

    # Enhanced validation with security checks
    errors = []

    if not first_name:
        errors.append('First name is required')
    elif len(first_name) > 100:
        errors.append('First name must be 100 characters or less')
        
    if not last_name:
        errors.append('Last name is required')
    elif len(last_name) > 100:
        errors.append('Last name must be 100 characters or less')
        
    if not email or not validate_email_format(email):
        errors.append('Valid email address is required')
    elif len(email) > 254:
        errors.append('Email address is too long')
        
    if phone and len(phone) > 20:
        errors.append('Primary phone number must be 20 characters or less')

    if phone2 and len(phone2) > 20:
        errors.append('Secondary phone number must be 20 characters or less')
        
    if not skill_level:
        errors.append('Birding skill level is required')
    elif not validate_skill_level(skill_level):
        errors.append('Invalid birding skill level selection')
        
    if not experience:
        errors.append('CBC experience level is required')
    elif not validate_experience(experience):
        errors.append('Invalid CBC experience level selection')
        
    if not preferred_area:
        errors.append('Area selection is required')
    elif not validate_area_code(preferred_area):
        errors.append('Invalid area selection')
    elif preferred_area != 'UNASSIGNED' and preferred_area not in public_areas:
        # Area is valid but restricted to admin assignment
        errors.append('This area is not available for public registration. Please choose another area or select "Wherever needed"')

    if not participation_type:
        errors.append('Please select how you would like to participate')
    elif not validate_participation_type(participation_type):
        errors.append('Invalid participation type selection')
        
    if notes_to_organizers and len(notes_to_organizers) > 1000:
        errors.append('Notes to organizers must be 1000 characters or less')

    # Check if email+name combination already registered for current year
    if participant_model.email_name_exists(email, first_name, last_name):
        errors.append('This name and email combination is already registered for this year')
        
    # Validate FEEDER participant constraints
    if participation_type == 'FEEDER':
        if preferred_area == 'UNASSIGNED':
            errors.append('Feeder counters must select a specific area')
        if interested_in_leadership:
            errors.append('Feeder counters cannot be area leaders')

    if errors:
        for error in errors:
            flash(error, 'error')

        # Preserve all form data programmatically for restoration
        form_data = request.form.to_dict()

        # Get public areas from Firestore
        if g.db:
            signup_type_model = AreaSignupTypeModel(g.db)
            public_areas = signup_type_model.get_public_areas()
        else:
            # Fallback to all areas if database unavailable
            public_areas = get_all_areas()

        all_areas = get_all_areas()
        area_leaders = {}  # Maps area_code -> list of leaders

        try:
            if g.db:
                current_year = datetime.now().year
                participant_model = ParticipantModel(g.db, current_year)

                # Get all leaders for current year
                leaders = participant_model.get_leaders()

                # Organize leaders by assigned area
                for leader in leaders:
                    assigned_area = leader.get('assigned_area_leader')
                    if assigned_area:
                        if assigned_area not in area_leaders:
                            area_leaders[assigned_area] = []
                        area_leaders[assigned_area].append(leader)

                # Sort leaders within each area by first name
                for area in area_leaders:
                    area_leaders[area].sort(key=lambda x: x.get('first_name', ''))
        except Exception as e:
            print(f"Warning: Could not fetch area leaders: {e}")

        # Ensure all areas are represented (with empty list if no leaders)
        for area_code in all_areas:
            if area_code not in area_leaders:
                area_leaders[area_code] = []

        count_date = get_count_date()
        org_vars = get_organization_variables()

        return render_template('index.html',
                             public_areas=public_areas,
                             get_area_info=get_area_info,
                             form_data=form_data,
                             all_areas=all_areas,
                             area_leaders=area_leaders,
                             count_date=count_date,
                             logo_path=LOGO_PATH,
                             **org_vars)


    # Create participant record
    participant_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': phone,
        'phone2': phone2,
        'skill_level': skill_level,
        'experience': experience,
        'preferred_area': preferred_area,
        'interested_in_leadership': interested_in_leadership,
        'interested_in_scribe': interested_in_scribe,
        'is_leader': False,  # Only admins can assign leadership
        'assigned_area_leader': None,
        'participation_type': participation_type,
        'has_binoculars': has_binoculars,
        'spotting_scope': spotting_scope,
        'notes_to_organizers': notes_to_organizers
    }

    try:
        participant_id = participant_model.add_participant(participant_data)

        if preferred_area == 'UNASSIGNED':
            flash(
                'Registration successful! An administrator will assign you to an area and your area leader will contact you.',
                'success')
            # Send confirmation email with participant data
            email_service.send_registration_confirmation(participant_data, 'UNASSIGNED')
        else:
            flash(f'Registration successful! You have been registered for Area {preferred_area}.', 'success')

            # Send confirmation email with participant data
            email_service.send_registration_confirmation(participant_data, preferred_area)

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

    org_vars = get_organization_variables()
    return render_template('registration_success.html',
                           area=area,
                           area_info=area_info,
                           participant_id=participant_id,
                           **org_vars)


@main_bp.route('/area-leader-info')
def area_leader_info():
    """Information about area leader responsibilities."""
    # Pass all query parameters to template for form restoration links, except
    # csrf_token - it must never end up in a URL/browser history/referrer, and
    # a client-side bug previously leaked it in here (fixed, but this is a
    # server-side backstop in case any other path ever reintroduces it).
    form_data = {k: v for k, v in request.args.items() if k != 'csrf_token'}
    org_vars = get_organization_variables()
    return render_template('area_leader_info.html', form_data=form_data, **org_vars)


@main_bp.route('/scribe-info')
def scribe_info():
    """Information about scribe responsibilities."""
    # Pass all query parameters to template for form restoration links, except
    # csrf_token - see area_leader_info's comment above for why.
    form_data = {k: v for k, v in request.args.items() if k != 'csrf_token'}
    org_vars = get_organization_variables()
    return render_template('scribe_info.html', form_data=form_data, **org_vars)


@main_bp.route('/robots.txt')
def robots_txt():
    """Serve robots.txt to guide bots and define honeypot traps."""
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')


@main_bp.route('/wp-admin.php')
@main_bp.route('/administrator')
@main_bp.route('/admin.php')
@main_bp.route('/login.php')
@main_bp.route('/admin')
@main_bp.route('/admin/<path:_subpath>')
def honeypot_trap(_subpath=None):
    """
    Honeypot trap - immediate block for bots that ignore robots.txt.
    Good bots respect robots.txt and never access these URLs.
    Bad bots ignore robots.txt and fall into the trap.

    /admin and /admin/* are included here because the real admin blueprint
    moved to /bigbird - anything still guessing the old, common /admin path
    is a bot, not a legitimate user (nobody has /admin bookmarked or linked).
    """
    if not HONEYPOT_ENABLED:
        abort(404)

    client_ip = get_client_ip(request)
    user_agent = request.headers.get('User-Agent', '')

    # Block immediately
    if g.db:
        blocker = IPBlockerService(g.db)
        blocker.trigger_honeypot(client_ip, request.path, user_agent)
        logger.warning(f"HONEYPOT_TRIGGERED: {client_ip} accessed {request.path}")

    # Return 404 to avoid revealing trap existence
    return render_template('errors/404.html'), 404


# Email validation moved to services/security.py::validate_email_format()
# for centralized validation across all routes