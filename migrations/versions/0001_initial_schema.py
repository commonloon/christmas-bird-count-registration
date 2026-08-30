"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'participants',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('phone', sa.String(20)),
        sa.Column('phone2', sa.String(20)),
        sa.Column('preferred_area', sa.String(10)),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('skill_level', sa.String(50)),
        sa.Column('experience', sa.String(50)),
        sa.Column('participation_type', sa.String(20), server_default='regular'),
        sa.Column('is_leader', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('assigned_area_leader', sa.String(10)),
        sa.Column('leadership_assigned_by', sa.String(254)),
        sa.Column('leadership_assigned_at', sa.DateTime(timezone=True)),
        sa.Column('leadership_removed_by', sa.String(254)),
        sa.Column('leadership_removed_at', sa.DateTime(timezone=True)),
        sa.Column('has_binoculars', sa.Boolean, server_default=sa.false()),
        sa.Column('spotting_scope', sa.Boolean, server_default=sa.false()),
        sa.Column('interested_in_scribe', sa.Boolean, server_default=sa.false()),
        sa.Column('interested_in_leadership', sa.Boolean, server_default=sa.false()),
        sa.Column('notes_to_organizers', sa.Text, server_default=''),
        sa.Column('assigned_by', sa.String(254)),
        sa.Column('assigned_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_participants_circle_slug', 'participants', ['circle_slug'])
    op.create_index('ix_participants_year', 'participants', ['year'])
    op.create_index('ix_participants_email', 'participants', ['email'])
    op.create_index('ix_participants_preferred_area', 'participants', ['preferred_area'])
    op.create_index('ix_participants_is_leader', 'participants', ['is_leader'])

    op.create_table(
        'removal_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('participant_name', sa.String(200)),
        sa.Column('participant_email', sa.String(254)),
        sa.Column('area_code', sa.String(10)),
        sa.Column('removed_by', sa.String(254)),
        sa.Column('reason', sa.Text),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('emailed', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('emailed_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_removal_log_circle_slug', 'removal_log', ['circle_slug'])
    op.create_index('ix_removal_log_year', 'removal_log', ['year'])
    op.create_index('ix_removal_log_area_code', 'removal_log', ['area_code'])
    op.create_index('ix_removal_log_removed_at', 'removal_log', ['removed_at'])

    op.create_table(
        'reassignment_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('participant_id', sa.Integer, sa.ForeignKey('participants.id', ondelete='SET NULL')),
        sa.Column('first_name', sa.String(100)),
        sa.Column('last_name', sa.String(100)),
        sa.Column('email', sa.String(254)),
        sa.Column('old_area', sa.String(10)),
        sa.Column('new_area', sa.String(10)),
        sa.Column('changed_by', sa.String(254)),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_reassignment_log_circle_slug', 'reassignment_log', ['circle_slug'])
    op.create_index('ix_reassignment_log_year', 'reassignment_log', ['year'])
    op.create_index('ix_reassignment_log_changed_at', 'reassignment_log', ['changed_at'])

    op.create_table(
        'withdrawal_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('participant_id', sa.Integer, sa.ForeignKey('participants.id', ondelete='SET NULL')),
        sa.Column('first_name', sa.String(100)),
        sa.Column('last_name', sa.String(100)),
        sa.Column('email', sa.String(254)),
        sa.Column('area_code', sa.String(10)),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('withdrawal_reason', sa.Text),
        sa.Column('recorded_by', sa.String(254)),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_withdrawal_log_circle_slug', 'withdrawal_log', ['circle_slug'])
    op.create_index('ix_withdrawal_log_year', 'withdrawal_log', ['year'])
    op.create_index('ix_withdrawal_log_area_code', 'withdrawal_log', ['area_code'])
    op.create_index('ix_withdrawal_log_recorded_at', 'withdrawal_log', ['recorded_at'])

    op.create_table(
        'area_signup_type',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('area_code', sa.String(10), nullable=False),
        sa.Column('admin_assignment_only', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.Column('updated_by', sa.String(254)),
        sa.UniqueConstraint('circle_slug', 'area_code', name='uq_area_signup_type_circle_area'),
    )
    op.create_index('ix_area_signup_type_circle_slug', 'area_signup_type', ['circle_slug'])
    op.create_index('ix_area_signup_type_area_code', 'area_signup_type', ['area_code'])

    op.create_table(
        'blocked_ips',
        sa.Column('ip_address', sa.String(45), primary_key=True),
        sa.Column('blocked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(50)),
        sa.Column('trigger_count', sa.Integer, server_default='0'),
        sa.Column('user_agent', sa.Text),
        sa.Column('last_violation_url', sa.String(500)),
        sa.Column('violation_history', sa.JSON),
        sa.Column('total_violations', sa.Integer, server_default='0'),
        sa.Column('auto_unblocked', sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_blocked_ips_expires_at', 'blocked_ips', ['expires_at'])

    op.create_table(
        'ip_violations',
        sa.Column('ip_address', sa.String(45), primary_key=True),
        sa.Column('window_bucket', sa.Integer, primary_key=True),
        sa.Column('count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_violation_url', sa.String(500)),
        sa.Column('last_seen', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_ip_violations_expires_at', 'ip_violations', ['expires_at'])

    op.create_table(
        'email_timestamps',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('area_code', sa.String(10), nullable=False),
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('last_sent', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('circle_slug', 'year', 'area_code', 'email_type', name='uq_email_timestamps_key'),
    )
    op.create_index('ix_email_timestamps_circle_slug', 'email_timestamps', ['circle_slug'])
    op.create_index('ix_email_timestamps_year', 'email_timestamps', ['year'])

    op.create_table(
        'magic_link_tokens',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_magic_link_tokens_email', 'magic_link_tokens', ['email'])
    op.create_index('ix_magic_link_tokens_token_hash', 'magic_link_tokens', ['token_hash'])


def downgrade():
    op.drop_table('magic_link_tokens')
    op.drop_table('email_timestamps')
    op.drop_table('ip_violations')
    op.drop_table('blocked_ips')
    op.drop_table('area_signup_type')
    op.drop_table('withdrawal_log')
    op.drop_table('reassignment_log')
    op.drop_table('removal_log')
    op.drop_table('participants')
