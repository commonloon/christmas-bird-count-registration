# Database configuration helper
from dotenv import load_dotenv

# Load .env explicitly rather than relying on flask run's automatic loading,
# so this works the same way under gunicorn, pytest, or any other launcher.
load_dotenv()

from models.db import get_session_factory, remove_session


def get_db_session():
    """Get the request-scoped SQLAlchemy session.

    Callers pass this session into model constructors, e.g. ParticipantModel(get_db_session(), year),
    the same way the old Firestore client was passed around.
    """
    return get_session_factory()()


def teardown_db_session(exception=None):
    """Release the session at the end of the request. Wire up via app.teardown_appcontext."""
    remove_session()
