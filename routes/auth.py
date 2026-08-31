from flask import Blueprint, session, request, redirect, url_for, flash, render_template, g
from functools import wraps
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import secrets

from config.admins import is_admin
from config.database import get_db_session
from models.db import MagicLinkToken
from models.participant import ParticipantModel
from models.circle import CircleAdminModel
from services.limiter import limiter
from config.rate_limits import RATE_LIMITS, get_rate_limit_message

# Import CSRF protection instance
from app import csrf

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

MAGIC_LINK_EXPIRY_MINUTES = 15


def get_user_role(email, db_session, circle_slug, year=None):
    """Determine user role based on email address, scoped to the current circle.

    Roles, most to least privileged:
    - 'super_admin': global whitelist (config/admins.py) - full access to every
      circle, plus the /bigbird/circles super-admin console.
    - 'admin': a circle-admin for THIS circle only (circle_admins table). Reuses
      the same role value 'admin' has always had, so require_admin's existing
      per-route gating on /bigbird/* needs no changes - ParticipantModel etc.
      already auto-scope by g.circle_slug, so this "just works" for isolation.
    - 'leader': an area leader for THIS circle only.
    - 'public': none of the above, or no circle context (e.g. the landing host).
    """
    if not email:
        return 'public'

    # Check super-admin status first - global, not circle-scoped
    if is_admin(email):
        return 'super_admin'

    if circle_slug is None:
        # No circle context (e.g. the cbc.birdcount.ca landing host) - only
        # super-admins have anything to do there.
        return 'public'

    # Check circle-admin status
    try:
        if CircleAdminModel(db_session).is_circle_admin(email, circle_slug):
            return 'admin'
    except Exception as e:
        logger.warning(f"Could not check circle-admin status for {email}: {e}")

    # Check area leader status
    try:
        participant_model = ParticipantModel(db_session, year, circle_slug)
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
            next_url = request.url.replace('http://', 'https://')
            return redirect(url_for('auth.login', next=next_url))
        return f(*args, **kwargs)

    return decorated_function


def require_admin(f):
    """Decorator to require admin privileges (circle-admin or super-admin)."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))

        user_role = session.get('user_role')
        if user_role in ('admin', 'super_admin'):
            return f(*args, **kwargs)

        if user_role == 'leader':
            # Leaders sometimes land on an admin URL (bookmarked, or bounced back
            # here after a magic-link login) - send them somewhere useful instead
            # of a bare access-denied error.
            return redirect(url_for('leader.dashboard'))

        flash('Admin access required.', 'error')
        return redirect(url_for('main.index'))

    return decorated_function


def require_super_admin(f):
    """Decorator to require super-admin privileges (global, cross-circle)."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))

        if session.get('user_role') == 'super_admin':
            return f(*args, **kwargs)

        flash('Super-admin access required.', 'error')
        return redirect(url_for('main.index'))

    return decorated_function


def require_leader(f):
    """Decorator to require area leader privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))

        user_role = session.get('user_role')
        if user_role not in ('admin', 'super_admin', 'leader'):
            flash('Area leader access required.', 'error')
            return redirect(url_for('main.index'))

        return f(*args, **kwargs)

    return decorated_function


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


@auth_bp.route('/login', methods=['GET'])
@limiter.limit(RATE_LIMITS['auth'])
def login():
    """Show the email-entry form to request a magic link."""
    return render_template('auth/login.html', next_url=request.args.get('next', '/'))


@auth_bp.route('/login', methods=['POST'])
@limiter.limit(RATE_LIMITS['auth'], error_message=get_rate_limit_message('auth'))
def request_magic_link():
    """Handle a request for a magic login link.

    Always shows the same confirmation regardless of whether the email is a known
    admin/leader, so this endpoint can't be used to probe which addresses have access.
    """
    email = (request.form.get('email') or '').strip().lower()
    next_url = request.form.get('next') or '/'

    if email:
        try:
            db = get_db_session()
            role = get_user_role(email, db, g.circle_slug)

            if role in ('super_admin', 'admin', 'leader'):
                raw_token = secrets.token_urlsafe(32)
                token_record = MagicLinkToken(
                    email=email,
                    token_hash=_hash_token(raw_token),
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(token_record)
                db.commit()

                verify_url = url_for('auth.verify', token=raw_token, next=next_url, _external=True)

                from services.email_service import email_service
                email_service.send_magic_link(email, verify_url)

                logger.info(f"Magic link requested for {email} (role: {role})")
            else:
                logger.info(f"Magic link requested for non-admin/leader email {email} - not sent")
        except Exception as e:
            logger.error(f"Error processing magic link request: {e}")

    return render_template('auth/login.html', link_sent=True, next_url=next_url)


@auth_bp.route('/verify/<token>')
@limiter.limit(RATE_LIMITS['auth'])
def verify(token):
    """Verify a magic link token and log the user in."""
    next_url = request.args.get('next') or '/'

    try:
        db = get_db_session()
        token_hash = _hash_token(token)

        record = db.query(MagicLinkToken).filter_by(token_hash=token_hash).first()

        if not record:
            flash('That login link is invalid. Please request a new one.', 'error')
            return redirect(url_for('auth.login'))

        if record.used_at is not None:
            flash('That login link has already been used. Please request a new one.', 'error')
            return redirect(url_for('auth.login'))

        if datetime.now(timezone.utc) > record.expires_at:
            flash('That login link has expired. Please request a new one.', 'error')
            return redirect(url_for('auth.login'))

        # Mark used (single-use) before establishing the session
        record.used_at = datetime.now(timezone.utc)
        db.commit()

        email = record.email
        user_role = get_user_role(email, db, g.circle_slug)

        session['user_email'] = email
        session['user_name'] = email
        session['user_role'] = user_role

        logger.info(f"User {email} logged in with role: {user_role}")

        if user_role == 'super_admin' and g.circle_slug is None and next_url == '/':
            # Logged in from the landing host, where there's no circle context -
            # the per-circle dashboard would silently default to Vancouver, which
            # would be a confusing landing spot after logging in from cbc.birdcount.ca.
            return redirect(url_for('admin.list_circles'))

        if user_role in ('admin', 'super_admin'):
            return redirect(next_url if next_url != '/' else url_for('admin.dashboard'))
        elif user_role == 'leader':
            return redirect(next_url if next_url != '/' else url_for('leader.dashboard'))
        else:
            return redirect(next_url)

    except Exception as e:
        logger.error(f"Magic link verification error: {e}")
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


def init_auth(app):
    """Initialize authentication for the Flask app."""
    import os

    # Set up session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production').strip()
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'cbc:'

    # Session cookie security attributes (CRITICAL for XSS/CSRF protection)
    app.config['SESSION_COOKIE_HTTPONLY'] = True      # Prevent JavaScript access to session cookie
    app.config['SESSION_COOKIE_SECURE'] = True        # Only send cookie over HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'     # Prevent CSRF while allowing magic-link redirects

    # Session timeout (security best practice for admin sessions)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)


def get_current_user():
    """Get current user information from session."""
    return {
        'email': session.get('user_email'),
        'name': session.get('user_name'),
        'role': session.get('user_role', 'public'),
        'is_authenticated': 'user_email' in session,
        'is_admin': session.get('user_role') in ('admin', 'super_admin'),
        'is_super_admin': session.get('user_role') == 'super_admin',
        'is_leader': session.get('user_role') in ['admin', 'super_admin', 'leader']
    }
