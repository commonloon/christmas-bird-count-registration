from flask import Blueprint, session, request, redirect, url_for, flash, current_app
from google.oauth2 import id_token
from google.auth.transport import requests
from functools import wraps
import os
import logging

from config.admins import is_admin
from models.participant import ParticipantModel
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS, get_rate_limit_message

# Import CSRF protection instance
from app import csrf

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()


def get_user_role(email, db_client, year=None):
    """Determine user role based on email address."""
    if not email:
        return 'public'

    # Check admin status first
    if is_admin(email):
        return 'admin'

    # Check area leader status
    try:
        participant_model = ParticipantModel(db_client, year)
        if participant_model.is_area_leader(email):
            return 'leader'
    except Exception as e:
        logger.warning(f"Could not check area leader status for {email}: {e}")

    return 'public'


def require_auth(f):
    """Decorator to require any authenticated user."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            # Force HTTPS in next URL for OAuth security
            next_url = request.url.replace('http://', 'https://')
            return redirect(url_for('auth.login', next=next_url))
        return f(*args, **kwargs)

    return decorated_function


def require_admin(f):
    """Decorator to require admin privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))

        if session.get('user_role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))

        return f(*args, **kwargs)

    return decorated_function


def require_leader(f):
    """Decorator to require area leader privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))

        user_role = session.get('user_role')
        if user_role not in ['admin', 'leader']:
            flash('Area leader access required.', 'error')
            return redirect(url_for('main.index'))

        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route('/login')
@limiter.limit(RATE_LIMITS['auth'])
def login():
    """Initiate Google OAuth login."""
    # In a real implementation, this would redirect to Google OAuth
    # For now, return a simple page with Google Sign-In button
    from flask import render_template
    return render_template('auth/login.html',
                           google_client_id=GOOGLE_CLIENT_ID,
                           next_url=request.args.get('next', '/'))


@auth_bp.route('/oauth/callback', methods=['POST'])
@csrf.exempt
@limiter.limit(RATE_LIMITS['auth'], error_message=get_rate_limit_message('auth'))
def oauth_callback():
    """Handle Google OAuth callback."""
    try:
        # Get the ID token from the request
        token = request.form.get('credential')
        if not token:
            flash('Authentication failed. Please try again.', 'error')
            return redirect(url_for('main.index'))

        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), GOOGLE_CLIENT_ID)

        # Extract user information
        email = idinfo.get('email')
        name = idinfo.get('name')

        if not email:
            flash('Could not retrieve email from Google account.', 'error')
            return redirect(url_for('main.index'))

        # Determine user role
        from google.cloud import firestore
        from config.database import get_firestore_client
        try:
            db_client, _ = get_firestore_client()
            user_role = get_user_role(email, db_client)
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            # Default to public role if database unavailable
            user_role = 'public'

        # Store in session
        session['user_email'] = email
        session['user_name'] = name
        session['user_role'] = user_role

        logger.info(f"User {email} logged in with role: {user_role}")

        # Redirect based on role and next parameter
        next_url = request.form.get('next') or request.args.get('next') or session.pop('next_url', None)

        if user_role == 'admin':
            return redirect(next_url or url_for('admin.dashboard'))
        elif user_role == 'leader':
            return redirect(next_url or url_for('leader.dashboard'))
        else:
            return redirect(next_url or url_for('main.index'))

    except ValueError as e:
        logger.error(f"OAuth token verification failed: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('main.index'))
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        flash('Login error. Please try again.', 'error')
        return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    """Log out the user."""
    user_email = session.get('user_email', 'unknown')
    session.clear()
    logger.info(f"User {user_email} logged out")
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile')
@require_auth
def profile():
    """Show user profile information."""
    from flask import render_template
    return render_template('auth/profile.html',
                           user_email=session.get('user_email'),
                           user_name=session.get('user_name'),
                           user_role=session.get('user_role'))


def init_auth(app):
    """Initialize authentication for the Flask app."""
    # Set up session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'cbc:'

    # Ensure Google OAuth credentials are available
    if not GOOGLE_CLIENT_ID:
        logger.warning("GOOGLE_CLIENT_ID not set - OAuth will not work")
    if not GOOGLE_CLIENT_SECRET:
        logger.warning("GOOGLE_CLIENT_SECRET not set - OAuth will not work")


def get_current_user():
    """Get current user information from session."""
    return {
        'email': session.get('user_email'),
        'name': session.get('user_name'),
        'role': session.get('user_role', 'public'),
        'is_authenticated': 'user_email' in session,
        'is_admin': session.get('user_role') == 'admin',
        'is_leader': session.get('user_role') in ['admin', 'leader']
    }