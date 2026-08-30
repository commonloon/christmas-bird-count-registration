import os

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint, create_engine, inspect
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

Base = declarative_base()

DEFAULT_CIRCLE_SLUG = 'vancouver'


class DictMixin:
    """Convert an ORM row to a plain dict, matching the shape callers already expect
    from the old Firestore-backed models (dict with an 'id' key, not an ORM object)."""

    def to_dict(self):
        return {
            column.key: getattr(self, column.key)
            for column in inspect(self).mapper.column_attrs
        }


class Participant(Base, DictMixin):
    __tablename__ = 'participants'

    id = Column(Integer, primary_key=True)
    circle_slug = Column(String(50), nullable=False, default=DEFAULT_CIRCLE_SLUG, index=True)
    year = Column(Integer, nullable=False, index=True)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(254), nullable=False, index=True)
    phone = Column(String(20))
    phone2 = Column(String(20))

    preferred_area = Column(String(10), index=True)
    status = Column(String(20), nullable=False, default='active')
    skill_level = Column(String(50))
    experience = Column(String(50))
    participation_type = Column(String(20), default='regular')

    is_leader = Column(Boolean, nullable=False, default=False, index=True)
    assigned_area_leader = Column(String(10))
    leadership_assigned_by = Column(String(254))
    leadership_assigned_at = Column(DateTime(timezone=True))
    leadership_removed_by = Column(String(254))
    leadership_removed_at = Column(DateTime(timezone=True))

    has_binoculars = Column(Boolean, default=False)
    spotting_scope = Column(Boolean, default=False)
    interested_in_scribe = Column(Boolean, default=False)
    interested_in_leadership = Column(Boolean, default=False)
    notes_to_organizers = Column(Text, default='')

    assigned_by = Column(String(254))
    assigned_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class RemovalLog(Base, DictMixin):
    __tablename__ = 'removal_log'

    id = Column(Integer, primary_key=True)
    circle_slug = Column(String(50), nullable=False, default=DEFAULT_CIRCLE_SLUG, index=True)
    year = Column(Integer, nullable=False, index=True)

    participant_name = Column(String(200))
    participant_email = Column(String(254))
    area_code = Column(String(10), index=True)
    removed_by = Column(String(254))
    reason = Column(Text)
    removed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    emailed = Column(Boolean, nullable=False, default=False)
    emailed_at = Column(DateTime(timezone=True))


class ReassignmentLog(Base, DictMixin):
    __tablename__ = 'reassignment_log'

    id = Column(Integer, primary_key=True)
    circle_slug = Column(String(50), nullable=False, default=DEFAULT_CIRCLE_SLUG, index=True)
    year = Column(Integer, nullable=False, index=True)

    participant_id = Column(Integer, ForeignKey('participants.id', ondelete='SET NULL'))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(254))
    old_area = Column(String(10))
    new_area = Column(String(10))
    changed_by = Column(String(254))
    changed_at = Column(DateTime(timezone=True), nullable=False, index=True)


class WithdrawalLog(Base, DictMixin):
    __tablename__ = 'withdrawal_log'

    id = Column(Integer, primary_key=True)
    circle_slug = Column(String(50), nullable=False, default=DEFAULT_CIRCLE_SLUG, index=True)
    year = Column(Integer, nullable=False, index=True)

    participant_id = Column(Integer, ForeignKey('participants.id', ondelete='SET NULL'))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(254))
    area_code = Column(String(10), index=True)
    status = Column(String(20), nullable=False)
    withdrawal_reason = Column(Text)
    recorded_by = Column(String(254))
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)


class AreaSignupType(Base, DictMixin):
    __tablename__ = 'area_signup_type'
    __table_args__ = (UniqueConstraint('circle_slug', 'area_code', name='uq_area_signup_type_circle_area'),)

    id = Column(Integer, primary_key=True)
    circle_slug = Column(String(50), nullable=False, default=DEFAULT_CIRCLE_SLUG, index=True)
    area_code = Column(String(10), nullable=False, index=True)
    admin_assignment_only = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    updated_by = Column(String(254))


class BlockedIP(Base, DictMixin):
    __tablename__ = 'blocked_ips'

    ip_address = Column(String(45), primary_key=True)
    blocked_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    reason = Column(String(50))
    trigger_count = Column(Integer, default=0)
    user_agent = Column(Text)
    last_violation_url = Column(String(500))
    violation_history = Column(JSON)
    total_violations = Column(Integer, default=0)
    auto_unblocked = Column(Boolean, nullable=False, default=False)


class IPViolation(Base, DictMixin):
    __tablename__ = 'ip_violations'

    ip_address = Column(String(45), primary_key=True)
    window_bucket = Column(Integer, primary_key=True)
    count = Column(Integer, nullable=False, default=0)
    last_violation_url = Column(String(500))
    last_seen = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class EmailTimestamp(Base, DictMixin):
    __tablename__ = 'email_timestamps'
    __table_args__ = (
        UniqueConstraint('circle_slug', 'year', 'area_code', 'email_type', name='uq_email_timestamps_key'),
    )

    id = Column(Integer, primary_key=True)
    circle_slug = Column(String(50), nullable=False, default=DEFAULT_CIRCLE_SLUG, index=True)
    year = Column(Integer, nullable=False, index=True)
    area_code = Column(String(10), nullable=False)
    email_type = Column(String(50), nullable=False)
    last_sent = Column(DateTime(timezone=True), nullable=False)


class MagicLinkToken(Base, DictMixin):
    __tablename__ = 'magic_link_tokens'

    id = Column(Integer, primary_key=True)
    email = Column(String(254), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False)


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError('DATABASE_URL environment variable is not set')
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = scoped_session(sessionmaker(bind=get_engine()))
    return _session_factory


def remove_session():
    """Release the current thread/request-local session. Call from Flask's teardown_appcontext."""
    if _session_factory is not None:
        _session_factory.remove()
