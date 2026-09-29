"""email scheduling: circle_email_schedules, email_schedule_run_log, app_settings

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-28

Storage for cron-driven per-circle email scheduling (SCHEDULER_ARCHITECTURE_PLAN.txt).
A single hourly cron entry runs `flask tick-scheduled-emails`; these tables tell
that command which (circle, email type) pairs are due, and record what it did.

- circle_email_schedules: admin-editable send times. hour is the LOCAL hour in
  the circle's own display_timezone; day_of_week is Python's date.weekday()
  convention (0=Monday ... 6=Sunday), NULL meaning every day.
- email_schedule_run_log: append-only audit trail, and the sole source of truth
  for "did this occurrence already run". schedule_id is NULL for manual
  (super-admin) runs that don't belong to a schedule row.
- app_settings: small global key/value table (first use: the From address for
  scheduler failure alerts).

Existing circles are backfilled with the default schedule so upgrading doesn't
silently mean "never sends". created_at on those rows is the migration time, and
the tick ignores any occurrence earlier than a row's created_at, so nothing
fires retroactively the moment this is deployed.
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

# (email_type, hour, day_of_week) - mirrors models/email_schedule.py's
# DEFAULT_SCHEDULE. Duplicated on purpose: a migration must keep working
# unchanged even if the application defaults are edited later.
DEFAULT_ROWS = [
    ('team_update', 7, None),
    ('team_update', 18, None),
    ('weekly_summary', 23, 4),
    ('admin_digest', 18, None),
]


def upgrade():
    op.create_table(
        'circle_email_schedules',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), sa.ForeignKey('circles.slug'), nullable=False),
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('hour', sa.Integer, nullable=False),
        sa.Column('day_of_week', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('hour >= 0 AND hour <= 23', name='ck_circle_email_schedules_hour'),
        sa.CheckConstraint('day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)',
                           name='ck_circle_email_schedules_dow'),
    )
    op.create_index('ix_circle_email_schedules_circle_slug', 'circle_email_schedules', ['circle_slug'])
    # Postgres treats NULLs as distinct in a plain UNIQUE constraint, so two
    # "every day" rows for the same hour would slip through one. COALESCE
    # folds NULL to -1 so those are caught too.
    op.execute(
        "CREATE UNIQUE INDEX uq_circle_email_schedules_slot ON circle_email_schedules "
        "(circle_slug, email_type, hour, COALESCE(day_of_week, -1))"
    )

    op.create_table(
        'email_schedule_run_log',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('circle_slug', sa.String(50), nullable=False),
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('schedule_id', sa.Integer, sa.ForeignKey('circle_email_schedules.id', ondelete='SET NULL')),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('emails_sent', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_summary', sa.Text),
        sa.Column('triggered_by', sa.String(254), nullable=False, server_default='scheduler'),
    )
    op.create_index('ix_email_schedule_run_log_circle_slug', 'email_schedule_run_log', ['circle_slug'])
    op.create_index('ix_email_schedule_run_log_schedule_id_run_at', 'email_schedule_run_log',
                    ['schedule_id', 'run_at'])

    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.String(254)),
    )

    # Backfill the default schedule for every circle that already exists.
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    schedules = sa.table(
        'circle_email_schedules',
        sa.column('circle_slug', sa.String), sa.column('email_type', sa.String),
        sa.column('hour', sa.Integer), sa.column('day_of_week', sa.Integer),
        sa.column('created_at', sa.DateTime(timezone=True)), sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    slugs = [row[0] for row in bind.execute(sa.text('SELECT slug FROM circles ORDER BY slug'))]
    rows = [
        {'circle_slug': slug, 'email_type': email_type, 'hour': hour, 'day_of_week': dow,
         'created_at': now, 'updated_at': now}
        for slug in slugs for (email_type, hour, dow) in DEFAULT_ROWS
    ]
    if rows:
        op.bulk_insert(schedules, rows)


def downgrade():
    op.drop_table('app_settings')
    op.drop_index('ix_email_schedule_run_log_schedule_id_run_at', table_name='email_schedule_run_log')
    op.drop_index('ix_email_schedule_run_log_circle_slug', table_name='email_schedule_run_log')
    op.drop_table('email_schedule_run_log')
    op.execute('DROP INDEX IF EXISTS uq_circle_email_schedules_slot')
    op.drop_index('ix_circle_email_schedules_circle_slug', table_name='circle_email_schedules')
    op.drop_table('circle_email_schedules')
